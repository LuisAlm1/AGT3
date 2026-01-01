"""
Servicio de programación y ejecución de posts
"""
import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import logging

from backend.database import SessionLocal, User, ScheduledPost, PostStatus, RecurrenceType
from backend.services.openai_service import openai_service
from backend.services.nano_banana_service import nano_banana_service
from backend.services.facebook_service import facebook_service
from backend.services.credits_service import CreditsService

logger = logging.getLogger(__name__)

SCHEDULER_TIMEZONE = os.environ.get('SCHEDULER_TIMEZONE', 'America/Mexico_City')


class SchedulerService:
    """Servicio para programar y ejecutar posts automáticos"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=SCHEDULER_TIMEZONE)
        self.is_running = False

    def start(self):
        """Inicia el scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Scheduler iniciado")

            # Programar job para verificar posts pendientes cada minuto
            self.scheduler.add_job(
                self.check_pending_posts,
                CronTrigger(minute='*'),  # Cada minuto
                id='check_pending_posts',
                replace_existing=True
            )

    def stop(self):
        """Detiene el scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler detenido")

    async def check_pending_posts(self):
        """Verifica y procesa posts pendientes"""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)

            # Buscar posts programados que deberían ejecutarse
            pending_posts = (
                db.query(ScheduledPost)
                .filter(
                    ScheduledPost.status == PostStatus.SCHEDULED,
                    ScheduledPost.scheduled_at <= now
                )
                .all()
            )

            for post in pending_posts:
                logger.info(f"Procesando post {post.id} programado para {post.scheduled_at}")
                asyncio.create_task(self.process_post(post.id))

        except Exception as e:
            logger.error(f"Error verificando posts pendientes: {e}")
        finally:
            db.close()

    async def process_post(self, post_id: str):
        """
        Procesa un post: genera contenido, imagen, y publica

        Args:
            post_id: ID del post a procesar
        """
        db = SessionLocal()
        try:
            post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
            if not post:
                logger.error(f"Post no encontrado: {post_id}")
                return

            user = post.user
            credits_service = CreditsService(db)

            # Verificar créditos
            if not credits_service.has_sufficient_credits(user.id):
                post.status = PostStatus.FAILED
                post.error_message = "Créditos insuficientes"
                db.commit()
                logger.warning(f"Post {post_id} cancelado: sin créditos")
                return

            # Cambiar estado a generando
            post.status = PostStatus.GENERATING
            db.commit()

            try:
                # 1. Generar contenido con OpenAI
                logger.info(f"Generando contenido para post {post_id}")
                content = await openai_service.generate_post_content(
                    business_summary=user.business_summary,
                    post_style=user.post_style,
                    post_number=db.query(ScheduledPost).filter(
                        ScheduledPost.user_id == user.id,
                        ScheduledPost.status == PostStatus.POSTED
                    ).count() + 1
                )

                post.image_prompt = content['image_prompt']
                post.caption = content['caption']
                db.commit()

                # 2. Generar imagen con Nano Banana Pro
                logger.info(f"Generando imagen para post {post_id}")
                image_result = await nano_banana_service.generate_post_image(
                    image_prompt=content['image_prompt'],
                    post_id=post_id
                )

                post.image_local_path = image_result.get('image_path')
                post.image_url = image_result.get('image_url')
                post.status = PostStatus.READY
                db.commit()

                # 3. Publicar en Facebook
                logger.info(f"Publicando post {post_id} en Facebook")
                post.status = PostStatus.POSTING
                db.commit()

                fb_result = await facebook_service.post_to_page(
                    page_id=user.facebook_page_id,
                    page_access_token=user.facebook_page_access_token,
                    message=content['caption'],
                    image_path=post.image_local_path
                )

                post.facebook_post_id = fb_result['post_id']
                post.facebook_post_url = fb_result['post_url']
                post.status = PostStatus.POSTED
                post.posted_at = datetime.now(timezone.utc)
                db.commit()

                # 4. Cobrar créditos
                success, _ = credits_service.charge_for_post(user.id, post_id)
                if success:
                    post.credits_charged = 1.0
                    db.commit()

                logger.info(f"Post {post_id} publicado exitosamente: {fb_result['post_url']}")

            except Exception as e:
                logger.error(f"Error procesando post {post_id}: {e}")
                post.status = PostStatus.FAILED
                post.error_message = str(e)
                db.commit()

        except Exception as e:
            logger.error(f"Error general procesando post {post_id}: {e}")
        finally:
            db.close()

    def schedule_posts_for_user(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        """
        Programa posts futuros para un usuario basado en su recurrencia

        Args:
            user_id: ID del usuario
            db: Sesión de base de datos

        Returns:
            Lista de posts programados
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_onboarded:
            return []

        # Calcular fechas basadas en recurrencia
        now = datetime.now(timezone.utc)
        dates = self._calculate_schedule_dates(
            recurrence=user.posting_recurrence,
            custom_days=user.custom_recurrence_days,
            preferred_time=user.preferred_posting_time,
            start_from=now,
            count=10  # Programar los próximos 10 posts
        )

        scheduled = []
        for date in dates:
            # Verificar que no exista ya un post para esa fecha
            existing = (
                db.query(ScheduledPost)
                .filter(
                    ScheduledPost.user_id == user_id,
                    ScheduledPost.scheduled_at == date,
                    ScheduledPost.status.in_([PostStatus.SCHEDULED, PostStatus.POSTED])
                )
                .first()
            )

            if not existing:
                post = ScheduledPost(
                    user_id=user_id,
                    scheduled_at=date,
                    status=PostStatus.SCHEDULED
                )
                db.add(post)
                scheduled.append({
                    "id": post.id,
                    "scheduled_at": date.isoformat(),
                    "status": "scheduled"
                })

        db.commit()
        return scheduled

    def _calculate_schedule_dates(
        self,
        recurrence: RecurrenceType,
        custom_days: int,
        preferred_time: str,
        start_from: datetime,
        count: int = 10
    ) -> List[datetime]:
        """
        Calcula las fechas de publicación basadas en la recurrencia

        Args:
            recurrence: Tipo de recurrencia
            custom_days: Días para recurrencia custom
            preferred_time: Hora preferida (HH:MM)
            start_from: Fecha desde la cual calcular
            count: Cantidad de fechas a calcular

        Returns:
            Lista de fechas programadas
        """
        dates = []
        try:
            hour, minute = map(int, preferred_time.split(':'))
        except:
            hour, minute = 10, 0

        # Calcular intervalo en días
        if recurrence == RecurrenceType.DAILY:
            interval_days = 1
        elif recurrence == RecurrenceType.WEEKLY:
            interval_days = 7
        elif recurrence == RecurrenceType.BIWEEKLY:
            interval_days = 14
        elif recurrence == RecurrenceType.MONTHLY:
            interval_days = 30
        else:
            interval_days = custom_days or 7

        current = start_from.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Asegurar que la primera fecha sea en el futuro
        if current <= start_from:
            current += timedelta(days=1)

        for _ in range(count):
            dates.append(current)
            current += timedelta(days=interval_days)

        return dates

    def get_scheduled_posts(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        """
        Obtiene los posts programados de un usuario

        Args:
            user_id: ID del usuario
            db: Sesión de base de datos

        Returns:
            Lista de posts con su información
        """
        posts = (
            db.query(ScheduledPost)
            .filter(ScheduledPost.user_id == user_id)
            .order_by(ScheduledPost.scheduled_at.asc())
            .all()
        )

        return [
            {
                "id": p.id,
                "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
                "posted_at": p.posted_at.isoformat() if p.posted_at else None,
                "status": p.status.value,
                "caption": p.caption,
                "image_url": p.image_url,
                "facebook_post_url": p.facebook_post_url,
                "error_message": p.error_message,
                "credits_charged": p.credits_charged
            }
            for p in posts
        ]

    def cancel_post(self, post_id: str, db: Session) -> bool:
        """
        Cancela un post programado

        Args:
            post_id: ID del post
            db: Sesión de base de datos

        Returns:
            True si se canceló exitosamente
        """
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post:
            return False

        if post.status == PostStatus.SCHEDULED:
            db.delete(post)
            db.commit()
            return True

        return False

    def reschedule_post(self, post_id: str, new_date: datetime, db: Session) -> bool:
        """
        Reprograma un post

        Args:
            post_id: ID del post
            new_date: Nueva fecha
            db: Sesión de base de datos

        Returns:
            True si se reprogramó exitosamente
        """
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post:
            return False

        if post.status == PostStatus.SCHEDULED:
            post.scheduled_at = new_date
            db.commit()
            return True

        return False


# Instancia global
scheduler_service = SchedulerService()
