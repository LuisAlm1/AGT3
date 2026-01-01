#!/usr/bin/env python3
"""
Script para inicializar la base de datos
"""
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

from backend.database import init_db, Base, engine

def main():
    print("=" * 50)
    print("MarketingBot SaaS - Inicialización de Base de Datos")
    print("=" * 50)

    print("\nCreando tablas...")
    init_db()

    print("\nTablas creadas:")
    for table in Base.metadata.tables:
        print(f"  - {table}")

    print("\n¡Base de datos inicializada correctamente!")
    print("=" * 50)

if __name__ == "__main__":
    main()
