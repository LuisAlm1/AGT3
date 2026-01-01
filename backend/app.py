"""
Aplicación principal del SaaS Marketing Automation
Backend con Quart (Flask asíncrono)
"""
import os
import secrets
import json
from datetime import datetime, timezone, timedelta
from functools import wraps

from quart import Quart, request, jsonify, redirect, url_for, session, render_template
from quart_cors import cors

from backend.database import SessionLocal, User, ScheduledPost, ChatMessage, init_db
from backend.services.facebook_service import facebook_service
from backend.services.openai_service import openai_service
from backend.services.credits_service import CreditsService
from backend.services.scheduler_service import scheduler_service

import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear aplicación Quart
app = Quart(__name__,
            static_folder='../static',
            template_folder='../templates')

# Configuración
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Habilitar CORS
app = cors(app, allow_origin="*")


# ============================================
# HELPERS Y DECORADORES
# ============================================

def get_db():
    """Obtiene una sesión de base de datos"""
    return SessionLocal()


def login_required(f):
    """Decorador para requerir autenticación"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "No autenticado"}), 401
        return await f(*args, **kwargs)
    return decorated_function


def get_current_user(db):
    """Obtiene el usuario actual de la sesión"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


# ============================================
# RUTAS DE PÁGINAS
# ============================================

@app.route('/')
async def index():
    """Página principal"""
    return await render_template('index.html')


@app.route('/dashboard')
async def dashboard():
    """Dashboard del usuario"""
    if 'user_id' not in session:
        return redirect('/auth/facebook')
    return await render_template('dashboard.html')


# ============================================
# AUTENTICACIÓN CON FACEBOOK
# ============================================

@app.route('/auth/facebook')
async def facebook_login():
    """Inicia el flujo de OAuth con Facebook"""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    login_url = facebook_service.get_login_url(state=state)
    return redirect(login_url)


@app.route('/auth/facebook/callback')
async def facebook_callback():
    """Callback de OAuth de Facebook"""
    db = get_db()
    try:
        # Verificar state para prevenir CSRF
        state = request.args.get('state')
        if state != session.get('oauth_state'):
            logger.warning("State mismatch en OAuth callback")
            return redirect('/?error=invalid_state')

        # Obtener código de autorización
        code = request.args.get('code')
        if not code:
            error = request.args.get('error_description', 'Error de autenticación')
            logger.error(f"Error en OAuth: {error}")
            return redirect(f'/?error={error}')

        # Intercambiar código por token
        token_data = await facebook_service.exchange_code_for_token(code)
        short_token = token_data['access_token']

        # Obtener token de larga duración
        long_token_data = await facebook_service.get_long_lived_token(short_token)
        access_token = long_token_data['access_token']
        expires_in = long_token_data.get('expires_in', 5184000)  # 60 días por defecto

        # Obtener información del usuario
        user_info = await facebook_service.get_user_info(access_token)
        fb_id = user_info['id']
        name = user_info.get('name', '')
        email = user_info.get('email', f'{fb_id}@facebook.com')

        # Buscar o crear usuario
        user = db.query(User).filter(User.facebook_id == fb_id).first()

        if not user:
            # Crear nuevo usuario
            user = User(
                email=email,
                name=name,
                facebook_id=fb_id,
                facebook_access_token=access_token,
                facebook_token_expires_at=facebook_service.calculate_token_expiry(expires_in),
                credits=1.0  # 1 crédito gratis de prueba
            )
            db.add(user)
            logger.info(f"Nuevo usuario creado: {email}")
        else:
            # Actualizar token
            user.facebook_access_token = access_token
            user.facebook_token_expires_at = facebook_service.calculate_token_expiry(expires_in)
            user.last_login = datetime.now(timezone.utc)

        db.commit()

        # Obtener páginas del usuario
        pages = await facebook_service.get_user_pages(access_token)
        if pages:
            # Por simplicidad, usar la primera página
            page = pages[0]
            user.facebook_page_id = page['id']
            user.facebook_page_name = page['name']
            user.facebook_page_access_token = page['access_token']
            db.commit()

        # Guardar sesión
        session['user_id'] = user.id
        session.permanent = True

        # Redirigir al dashboard
        return redirect('/dashboard')

    except Exception as e:
        logger.error(f"Error en Facebook callback: {e}")
        return redirect(f'/?error=auth_failed')
    finally:
        db.close()


@app.route('/auth/logout')
async def logout():
    """Cierra la sesión del usuario"""
    session.clear()
    return redirect('/')


# ============================================
# API DEL CHAT (OpenAI)
# ============================================

@app.route('/api/chat', methods=['POST'])
@login_required
async def chat():
    """Procesa mensajes del chat con OpenAI"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        data = await request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({"error": "Mensaje vacío"}), 400

        # Guardar mensaje del usuario
        chat_msg = ChatMessage(
            user_id=user.id,
            role='user',
            content=user_message
        )
        db.add(chat_msg)
        db.commit()

        # Enviar a OpenAI
        if user.openai_conversation_id:
            # Continuar conversación existente
            response = await openai_service.continue_conversation(
                user_message=user_message,
                conversation_id=user.openai_conversation_id
            )
        else:
            # Crear nueva conversación
            response = await openai_service.send_message(
                user_message=user_message
            )
            # Guardar ID de conversación
            if response.get('conversation_id'):
                user.openai_conversation_id = response['conversation_id']
                db.commit()

        # Procesar function calls si existen
        function_results = []
        for func_call in response.get('function_calls', []):
            result = await process_function_call(user, func_call, db)
            function_results.append(result)

        # Guardar respuesta del asistente
        assistant_msg = ChatMessage(
            user_id=user.id,
            role='assistant',
            content=response.get('text', ''),
            openai_response_id=response.get('response_id')
        )
        db.add(assistant_msg)
        db.commit()

        return jsonify({
            "message": response.get('text', ''),
            "function_calls": response.get('function_calls', []),
            "function_results": function_results,
            "is_onboarded": user.is_onboarded
        })

    except Exception as e:
        logger.error(f"Error en chat: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


async def process_function_call(user: User, func_call: dict, db) -> dict:
    """
    Procesa una llamada de función del asistente

    Args:
        user: Usuario actual
        func_call: Datos de la función llamada
        db: Sesión de base de datos

    Returns:
        Resultado de la función
    """
    name = func_call.get('name')
    args = func_call.get('arguments', {})

    logger.info(f"Procesando función: {name} con args: {args}")

    if name == 'save_business_profile':
        user.business_summary = args.get('business_summary')
        user.post_style = args.get('post_style')

        recurrence = args.get('recurrence', 'weekly')
        from backend.database import RecurrenceType
        recurrence_map = {
            'daily': RecurrenceType.DAILY,
            'weekly': RecurrenceType.WEEKLY,
            'biweekly': RecurrenceType.BIWEEKLY,
            'monthly': RecurrenceType.MONTHLY
        }
        user.posting_recurrence = recurrence_map.get(recurrence, RecurrenceType.WEEKLY)

        if args.get('preferred_time'):
            user.preferred_posting_time = args.get('preferred_time')

        user.is_onboarded = True
        db.commit()

        # Programar posts
        scheduled = scheduler_service.schedule_posts_for_user(user.id, db)

        return {
            "success": True,
            "message": "Perfil guardado correctamente",
            "posts_scheduled": len(scheduled)
        }

    elif name == 'update_business_summary':
        user.business_summary = args.get('business_summary')
        db.commit()
        return {"success": True, "message": "Resumen actualizado"}

    elif name == 'update_post_style':
        user.post_style = args.get('post_style')
        db.commit()
        return {"success": True, "message": "Estilo actualizado"}

    elif name == 'update_recurrence':
        recurrence = args.get('recurrence', 'weekly')
        from backend.database import RecurrenceType
        recurrence_map = {
            'daily': RecurrenceType.DAILY,
            'weekly': RecurrenceType.WEEKLY,
            'biweekly': RecurrenceType.BIWEEKLY,
            'monthly': RecurrenceType.MONTHLY
        }
        user.posting_recurrence = recurrence_map.get(recurrence, RecurrenceType.WEEKLY)

        if args.get('preferred_time'):
            user.preferred_posting_time = args.get('preferred_time')

        db.commit()

        # Reprogramar posts
        scheduled = scheduler_service.schedule_posts_for_user(user.id, db)

        return {
            "success": True,
            "message": "Recurrencia actualizada",
            "posts_scheduled": len(scheduled)
        }

    return {"success": False, "message": "Función no reconocida"}


@app.route('/api/chat/history', methods=['GET'])
@login_required
async def chat_history():
    """Obtiene el historial del chat"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == user.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        return jsonify({
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat()
                }
                for m in messages
            ]
        })

    finally:
        db.close()


# ============================================
# API DE USUARIO Y PERFIL
# ============================================

@app.route('/api/user/profile', methods=['GET'])
@login_required
async def get_profile():
    """Obtiene el perfil del usuario"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        return jsonify({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "facebook_page_name": user.facebook_page_name,
            "business_summary": user.business_summary,
            "post_style": user.post_style,
            "posting_recurrence": user.posting_recurrence.value if user.posting_recurrence else None,
            "preferred_posting_time": user.preferred_posting_time,
            "credits": user.credits,
            "is_onboarded": user.is_onboarded
        })

    finally:
        db.close()


@app.route('/api/user/pages', methods=['GET'])
@login_required
async def get_user_pages():
    """Obtiene las páginas de Facebook del usuario"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        pages = await facebook_service.get_user_pages(user.facebook_access_token)
        return jsonify({"pages": pages})

    except Exception as e:
        logger.error(f"Error obteniendo páginas: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route('/api/user/select-page', methods=['POST'])
@login_required
async def select_page():
    """Selecciona una página de Facebook para publicar"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        data = await request.get_json()
        page_id = data.get('page_id')

        if not page_id:
            return jsonify({"error": "page_id requerido"}), 400

        # Obtener las páginas para verificar y obtener el token
        pages = await facebook_service.get_user_pages(user.facebook_access_token)
        page = next((p for p in pages if p['id'] == page_id), None)

        if not page:
            return jsonify({"error": "Página no encontrada"}), 404

        user.facebook_page_id = page['id']
        user.facebook_page_name = page['name']
        user.facebook_page_access_token = page['access_token']
        db.commit()

        return jsonify({
            "success": True,
            "page_name": page['name']
        })

    except Exception as e:
        logger.error(f"Error seleccionando página: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================
# API DE CRÉDITOS
# ============================================

@app.route('/api/credits/balance', methods=['GET'])
@login_required
async def credits_balance():
    """Obtiene el balance de créditos"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        credits_service = CreditsService(db)

        return jsonify({
            "balance": user.credits,
            "total_purchased": user.total_credits_purchased,
            "total_used": user.total_credits_used
        })

    finally:
        db.close()


@app.route('/api/credits/packages', methods=['GET'])
async def credits_packages():
    """Obtiene los paquetes de créditos disponibles"""
    packages = CreditsService.get_credit_packages()
    return jsonify({"packages": packages})


@app.route('/api/credits/history', methods=['GET'])
@login_required
async def credits_history():
    """Obtiene el historial de transacciones de créditos"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        credits_service = CreditsService(db)
        history = credits_service.get_transaction_history(user.id)

        return jsonify({"history": history})

    finally:
        db.close()


# ============================================
# API DE POSTS PROGRAMADOS
# ============================================

@app.route('/api/posts', methods=['GET'])
@login_required
async def get_posts():
    """Obtiene los posts programados del usuario"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        posts = scheduler_service.get_scheduled_posts(user.id, db)
        return jsonify({"posts": posts})

    finally:
        db.close()


@app.route('/api/posts/schedule', methods=['POST'])
@login_required
async def schedule_posts():
    """Programa nuevos posts basados en la configuración del usuario"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        if not user.is_onboarded:
            return jsonify({"error": "Complete el onboarding primero"}), 400

        scheduled = scheduler_service.schedule_posts_for_user(user.id, db)
        return jsonify({
            "success": True,
            "posts_scheduled": len(scheduled),
            "posts": scheduled
        })

    except Exception as e:
        logger.error(f"Error programando posts: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route('/api/posts/<post_id>/cancel', methods=['DELETE'])
@login_required
async def cancel_post(post_id):
    """Cancela un post programado"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Verificar que el post pertenece al usuario
        post = db.query(ScheduledPost).filter(
            ScheduledPost.id == post_id,
            ScheduledPost.user_id == user.id
        ).first()

        if not post:
            return jsonify({"error": "Post no encontrado"}), 404

        success = scheduler_service.cancel_post(post_id, db)
        return jsonify({"success": success})

    finally:
        db.close()


@app.route('/api/posts/<post_id>/reschedule', methods=['PUT'])
@login_required
async def reschedule_post(post_id):
    """Reprograma un post"""
    db = get_db()
    try:
        user = get_current_user(db)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        data = await request.get_json()
        new_date_str = data.get('scheduled_at')

        if not new_date_str:
            return jsonify({"error": "scheduled_at requerido"}), 400

        # Verificar que el post pertenece al usuario
        post = db.query(ScheduledPost).filter(
            ScheduledPost.id == post_id,
            ScheduledPost.user_id == user.id
        ).first()

        if not post:
            return jsonify({"error": "Post no encontrado"}), 404

        new_date = datetime.fromisoformat(new_date_str.replace('Z', '+00:00'))
        success = scheduler_service.reschedule_post(post_id, new_date, db)

        return jsonify({"success": success})

    finally:
        db.close()


# ============================================
# HEALTH CHECK
# ============================================

@app.route('/health')
async def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ============================================
# INICIALIZACIÓN
# ============================================

@app.before_serving
async def startup():
    """Inicialización antes de servir"""
    # Inicializar base de datos
    init_db()
    # Iniciar scheduler
    scheduler_service.start()
    logger.info("Aplicación iniciada")


@app.after_serving
async def shutdown():
    """Limpieza al cerrar"""
    scheduler_service.stop()
    logger.info("Aplicación cerrada")


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = ["127.0.0.1:5001"]

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
