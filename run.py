#!/usr/bin/env python3
"""
Script de inicio para MarketingBot SaaS
"""
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Importar la aplicación
from backend.app import app

if __name__ == '__main__':
    import asyncio
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    config = Config()
    config.bind = ["127.0.0.1:5000"]
    config.accesslog = "-"
    config.errorlog = "-"
    config.use_reloader = os.environ.get('DEBUG', 'False').lower() == 'true'

    print("=" * 50)
    print("MarketingBot SaaS - Starting...")
    print("=" * 50)
    print(f"Server: http://127.0.0.1:5000")
    print("=" * 50)

    asyncio.run(serve(app, config))
