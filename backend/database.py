"""
Configuración de Base de Datos y Modelos SQLAlchemy
"""
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import StaticPool
import enum

# Configuración de la base de datos
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///marketing_saas.db')

# Para SQLite en modo async
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Obtiene una sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_uuid():
    """Genera un UUID único"""
    return str(uuid.uuid4())


class PostStatus(enum.Enum):
    """Estados posibles de un post"""
    SCHEDULED = "scheduled"
    GENERATING = "generating"
    READY = "ready"
    POSTING = "posting"
    POSTED = "posted"
    FAILED = "failed"


class RecurrenceType(enum.Enum):
    """Tipos de recurrencia"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class User(Base):
    """Modelo de Usuario"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))

    # Facebook OAuth
    facebook_id = Column(String(255), unique=True, index=True)
    facebook_access_token = Column(Text)  # Token encriptado
    facebook_token_expires_at = Column(DateTime)
    facebook_page_id = Column(String(255))
    facebook_page_name = Column(String(255))
    facebook_page_access_token = Column(Text)  # Token de página

    # OpenAI Conversation
    openai_conversation_id = Column(String(255))

    # Perfil del negocio (recopilado por el asistente)
    business_summary = Column(Text)  # Resumen del negocio
    post_style = Column(Text)  # Estilo/forma de los posts
    posting_recurrence = Column(SQLEnum(RecurrenceType), default=RecurrenceType.WEEKLY)
    custom_recurrence_days = Column(Integer, default=7)  # Para recurrencia custom
    preferred_posting_time = Column(String(5), default="10:00")  # HH:MM

    # Créditos
    credits = Column(Float, default=1.0)  # 1 crédito gratis para probar
    total_credits_purchased = Column(Float, default=0.0)
    total_credits_used = Column(Float, default=0.0)

    # Metadata
    is_active = Column(Boolean, default=True)
    is_onboarded = Column(Boolean, default=False)  # Si completó el onboarding
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)

    # Relaciones
    posts = relationship("ScheduledPost", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class ScheduledPost(Base):
    """Modelo de Posts Programados"""
    __tablename__ = "scheduled_posts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Programación
    scheduled_at = Column(DateTime, nullable=False, index=True)
    posted_at = Column(DateTime)

    # Contenido generado
    image_prompt = Column(Text)  # Prompt detallado para la imagen
    caption = Column(Text)  # Caption de Facebook
    image_url = Column(Text)  # URL de la imagen generada
    image_local_path = Column(String(500))  # Path local de la imagen

    # Estado
    status = Column(SQLEnum(PostStatus), default=PostStatus.SCHEDULED, index=True)
    error_message = Column(Text)

    # Facebook
    facebook_post_id = Column(String(255))
    facebook_post_url = Column(Text)

    # Créditos
    credits_charged = Column(Float, default=0.0)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relación
    user = relationship("User", back_populates="posts")

    def __repr__(self):
        return f"<ScheduledPost {self.id} - {self.status.value}>"


class CreditTransaction(Base):
    """Modelo de Transacciones de Créditos"""
    __tablename__ = "credit_transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Transacción
    amount = Column(Float, nullable=False)  # Positivo = compra, Negativo = uso
    balance_after = Column(Float, nullable=False)
    description = Column(String(500))

    # Referencia
    post_id = Column(String(36), ForeignKey("scheduled_posts.id"), nullable=True)
    stripe_payment_id = Column(String(255))  # Para compras

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relación
    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<CreditTransaction {self.id} - {self.amount}>"


class ChatMessage(Base):
    """Modelo de Mensajes del Chat"""
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Mensaje
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Función llamada (si aplica)
    function_name = Column(String(100))
    function_args = Column(Text)  # JSON de argumentos

    # OpenAI
    openai_response_id = Column(String(255))

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relación
    user = relationship("User", back_populates="chat_messages")

    def __repr__(self):
        return f"<ChatMessage {self.id} - {self.role}>"


def init_db():
    """Inicializa la base de datos creando todas las tablas"""
    Base.metadata.create_all(bind=engine)
    print("Base de datos inicializada correctamente")


def drop_db():
    """Elimina todas las tablas (usar con precaución)"""
    Base.metadata.drop_all(bind=engine)
    print("Base de datos eliminada")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_db()
    elif len(sys.argv) > 1 and sys.argv[1] == "drop":
        response = input("¿Estás seguro de eliminar la base de datos? (yes/no): ")
        if response.lower() == "yes":
            drop_db()
    else:
        print("Uso: python database.py [init|drop]")
