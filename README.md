# MarketingBot SaaS

Tu agencia de marketing automatizada al alcance de un clic.

## Descripción

MarketingBot es un SaaS que automatiza la creación y publicación de contenido en Facebook. Utilizando inteligencia artificial (OpenAI y Nano Banana Pro), genera imágenes profesionales y captions atractivos para tus publicaciones.

## Características

- **Login con Facebook**: Autenticación OAuth para publicar en tu nombre
- **Asistente Inteligente**: Chat conversacional para configurar tu estrategia
- **Generación de Imágenes**: Imágenes profesionales con Nano Banana Pro (Gemini 3 Pro)
- **Captions Automáticos**: Textos persuasivos generados por GPT-4.1
- **Programación Automática**: Define la frecuencia y el sistema publica por ti
- **Sistema de Créditos**: Paga solo por lo que usas
- **Calendario Visual**: Visualiza todos tus posts programados

## Requisitos

- Python 3.10+
- Nginx
- Cuenta de desarrollador de Facebook
- API Key de OpenAI
- API Key de Google (Gemini/Nano Banana Pro)

## Instalación

1. Clonar el repositorio:
```bash
git clone <repo-url>
cd AGT3
```

2. Crear entorno virtual e instalar dependencias:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

4. Inicializar la base de datos:
```bash
python init_db.py
```

5. Ejecutar la aplicación:
```bash
python run.py
```

## Configuración de Facebook

1. Crear una app en [Facebook Developers](https://developers.facebook.com/)
2. Agregar el producto "Facebook Login"
3. Configurar los permisos:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `pages_show_list`
   - `public_profile`
   - `email`
4. Agregar la URI de redirección: `https://tu-dominio.com/auth/facebook/callback`

## Configuración de Nginx

Copiar la configuración de `config/nginx.conf` a tu servidor y ajustar:
- Rutas de certificados SSL
- Nombre del dominio
- Rutas de archivos estáticos

## Estructura del Proyecto

```
AGT3/
├── backend/
│   ├── app.py              # Aplicación principal Quart
│   ├── database.py         # Modelos SQLAlchemy
│   └── services/
│       ├── facebook_service.py   # Integración Facebook
│       ├── openai_service.py     # Integración OpenAI
│       ├── nano_banana_service.py # Integración Nano Banana
│       ├── credits_service.py    # Sistema de créditos
│       └── scheduler_service.py  # Programador de posts
├── templates/
│   ├── index.html          # Landing page
│   └── dashboard.html      # Dashboard principal
├── static/
│   ├── css/
│   └── js/
├── config/
│   ├── settings.py
│   └── nginx.conf
├── requirements.txt
├── run.py
└── init_db.py
```

## Sistema de Créditos

- **Costo por post**: 1 crédito
- **Precio por crédito**: ~$0.14 USD
- **Créditos de prueba**: 1 (gratis)

Los costos se calculan basándose en:
- OpenAI GPT-4.1: ~$0.02 por post
- Nano Banana Pro: ~$0.05 por imagen
- Margen: 100% (ganamos el doble del costo)

## API Endpoints

### Autenticación
- `GET /auth/facebook` - Iniciar login con Facebook
- `GET /auth/facebook/callback` - Callback de OAuth
- `GET /auth/logout` - Cerrar sesión

### Chat
- `POST /api/chat` - Enviar mensaje al asistente
- `GET /api/chat/history` - Obtener historial del chat

### Usuario
- `GET /api/user/profile` - Obtener perfil
- `GET /api/user/pages` - Obtener páginas de Facebook
- `POST /api/user/select-page` - Seleccionar página

### Posts
- `GET /api/posts` - Obtener posts programados
- `POST /api/posts/schedule` - Programar nuevos posts
- `DELETE /api/posts/{id}/cancel` - Cancelar post
- `PUT /api/posts/{id}/reschedule` - Reprogramar post

### Créditos
- `GET /api/credits/balance` - Obtener balance
- `GET /api/credits/packages` - Obtener paquetes disponibles
- `GET /api/credits/history` - Historial de transacciones

## Licencia

Propietario - Todos los derechos reservados.
