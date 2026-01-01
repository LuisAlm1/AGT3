"""
Servicio de gestión de créditos
"""
import os
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

# Configuración de costos y precios
COST_OPENAI_PER_POST = float(os.environ.get('COST_OPENAI_PER_POST', '0.02'))
COST_NANO_BANANA_PER_POST = float(os.environ.get('COST_NANO_BANANA_PER_POST', '0.05'))
TOTAL_COST_PER_POST = COST_OPENAI_PER_POST + COST_NANO_BANANA_PER_POST  # $0.07

# Ganamos el doble
CREDITS_PER_POST = 1
PRICE_PER_CREDIT_USD = TOTAL_COST_PER_POST * 2  # $0.14 por crédito

# Créditos de prueba
FREE_TRIAL_CREDITS = 1


class CreditsService:
    """Servicio para gestionar créditos de usuarios"""

    def __init__(self, db: Session):
        self.db = db

    def get_balance(self, user_id: str) -> float:
        """
        Obtiene el balance de créditos del usuario

        Args:
            user_id: ID del usuario

        Returns:
            Balance actual de créditos
        """
        from backend.database import User
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"Usuario no encontrado: {user_id}")
        return user.credits

    def has_sufficient_credits(self, user_id: str, amount: float = 1.0) -> bool:
        """
        Verifica si el usuario tiene suficientes créditos

        Args:
            user_id: ID del usuario
            amount: Cantidad requerida

        Returns:
            True si tiene suficientes créditos
        """
        balance = self.get_balance(user_id)
        return balance >= amount

    def charge_for_post(self, user_id: str, post_id: str) -> Tuple[bool, float]:
        """
        Cobra los créditos por un post

        Args:
            user_id: ID del usuario
            post_id: ID del post

        Returns:
            Tuple (éxito, nuevo_balance)
        """
        from backend.database import User, CreditTransaction

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"Usuario no encontrado: {user_id}")

        if user.credits < CREDITS_PER_POST:
            logger.warning(f"Usuario {user_id} sin créditos suficientes")
            return False, user.credits

        # Descontar créditos
        user.credits -= CREDITS_PER_POST
        user.total_credits_used += CREDITS_PER_POST

        # Registrar transacción
        transaction = CreditTransaction(
            user_id=user_id,
            amount=-CREDITS_PER_POST,
            balance_after=user.credits,
            description=f"Post publicado: {post_id[:8]}...",
            post_id=post_id
        )
        self.db.add(transaction)
        self.db.commit()

        logger.info(f"Cobrados {CREDITS_PER_POST} créditos al usuario {user_id}. Nuevo balance: {user.credits}")
        return True, user.credits

    def add_credits(
        self,
        user_id: str,
        amount: float,
        description: str = "Compra de créditos",
        stripe_payment_id: Optional[str] = None
    ) -> float:
        """
        Agrega créditos al usuario

        Args:
            user_id: ID del usuario
            amount: Cantidad de créditos a agregar
            description: Descripción de la transacción
            stripe_payment_id: ID del pago de Stripe (opcional)

        Returns:
            Nuevo balance
        """
        from backend.database import User, CreditTransaction

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"Usuario no encontrado: {user_id}")

        user.credits += amount
        user.total_credits_purchased += amount

        # Registrar transacción
        transaction = CreditTransaction(
            user_id=user_id,
            amount=amount,
            balance_after=user.credits,
            description=description,
            stripe_payment_id=stripe_payment_id
        )
        self.db.add(transaction)
        self.db.commit()

        logger.info(f"Agregados {amount} créditos al usuario {user_id}. Nuevo balance: {user.credits}")
        return user.credits

    def grant_trial_credits(self, user_id: str) -> float:
        """
        Otorga créditos de prueba a un nuevo usuario

        Args:
            user_id: ID del usuario

        Returns:
            Balance con créditos de prueba
        """
        return self.add_credits(
            user_id=user_id,
            amount=FREE_TRIAL_CREDITS,
            description="Créditos de prueba gratuitos"
        )

    def get_transaction_history(
        self,
        user_id: str,
        limit: int = 50
    ) -> list:
        """
        Obtiene el historial de transacciones

        Args:
            user_id: ID del usuario
            limit: Número máximo de transacciones

        Returns:
            Lista de transacciones
        """
        from backend.database import CreditTransaction

        transactions = (
            self.db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": t.id,
                "amount": t.amount,
                "balance_after": t.balance_after,
                "description": t.description,
                "created_at": t.created_at.isoformat()
            }
            for t in transactions
        ]

    @staticmethod
    def calculate_price(credits: int) -> float:
        """
        Calcula el precio en USD para una cantidad de créditos

        Args:
            credits: Cantidad de créditos

        Returns:
            Precio en USD
        """
        return credits * PRICE_PER_CREDIT_USD

    @staticmethod
    def get_credit_packages() -> list:
        """
        Retorna los paquetes de créditos disponibles

        Returns:
            Lista de paquetes con nombre, créditos y precio
        """
        packages = [
            {"name": "Básico", "credits": 10, "posts": 10},
            {"name": "Emprendedor", "credits": 30, "posts": 30},
            {"name": "Profesional", "credits": 100, "posts": 100},
            {"name": "Agencia", "credits": 500, "posts": 500},
        ]

        for pkg in packages:
            pkg["price_usd"] = round(pkg["credits"] * PRICE_PER_CREDIT_USD, 2)
            # Descuento por volumen
            if pkg["credits"] >= 100:
                pkg["price_usd"] = round(pkg["price_usd"] * 0.85, 2)  # 15% descuento
            elif pkg["credits"] >= 30:
                pkg["price_usd"] = round(pkg["price_usd"] * 0.90, 2)  # 10% descuento

        return packages


def get_credits_service(db: Session) -> CreditsService:
    """Factory para obtener el servicio de créditos"""
    return CreditsService(db)
