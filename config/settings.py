"""
Configuración del SaaS Marketing Automation
"""
import os
from datetime import timedelta

# ===========================================
# CONFIGURACIÓN BASE
# ===========================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///marketing_saas.db')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# ===========================================
# FACEBOOK OAUTH
# ===========================================
FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')
FACEBOOK_REDIRECT_URI = os.environ.get('FACEBOOK_REDIRECT_URI', 'https://agathoscreative.com/auth/facebook/callback')

# Permisos necesarios para postear
FACEBOOK_PERMISSIONS = [
    'pages_manage_posts',
    'pages_read_engagement',
    'pages_show_list',
    'public_profile',
    'email'
]

# ===========================================
# OPENAI CONFIGURATION
# ===========================================
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1')

# ===========================================
# GOOGLE/NANO BANANA PRO CONFIGURATION
# ===========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
NANO_BANANA_MODEL = 'gemini-3-pro-image-preview'
NANO_BANANA_ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent'

# ===========================================
# SISTEMA DE CRÉDITOS
# ===========================================
# Costos estimados por post (en USD)
COST_OPENAI_PER_POST = 0.02  # ~1000 tokens input + 500 output con GPT-4.1
COST_NANO_BANANA_PER_POST = 0.05  # Por imagen 1K/2K
TOTAL_COST_PER_POST = COST_OPENAI_PER_POST + COST_NANO_BANANA_PER_POST

# Precio por crédito (ganamos el doble)
CREDITS_PER_POST = 1
PRICE_PER_CREDIT_USD = TOTAL_COST_PER_POST * 2  # $0.14 por crédito

# Créditos de prueba (para 1 post)
FREE_TRIAL_CREDITS = 1

# ===========================================
# SCHEDULER
# ===========================================
SCHEDULER_TIMEZONE = os.environ.get('SCHEDULER_TIMEZONE', 'America/Mexico_City')

# ===========================================
# SESSION
# ===========================================
SESSION_LIFETIME = timedelta(days=30)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
