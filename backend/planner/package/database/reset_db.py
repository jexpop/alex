#!/usr/bin/env python3
"""
Script de Reinicio de la Base de Datos
Elimina todas las tablas, recrea el esquema y carga datos semilla
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import subprocess
import argparse
from src.client import DataAPIClient
from src.models import Database
from src.schemas import UserCreate, AccountCreate, PositionCreate
from decimal import Decimal


def drop_all_tables(db: DataAPIClient):
    """Elimina todas las tablas en el orden correcto (respetando claves foráneas)"""
    print("🗑️  Eliminando tablas existentes...")
    
    tables_to_drop = ['positions', 'accounts', 'jobs', 'instruments', 'users']
    
    for table in tables_to_drop:
        try:
            db.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"   ✅ Tabla eliminada {table}")
        except Exception as e:
            print(f"   ⚠️  Error al eliminar {table}: {e}")
    
    try:
        db.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")
        print(f"   ✅ Función update_updated_at_column eliminada")
    except Exception as e:
        print(f"   ⚠️  Error al eliminar la función: {e}")


def create_test_data(db_models: Database):
    """Crear usuario de prueba con portafolio de muestra"""
    print("\n👤 Creando usuario de prueba y portafolio...")
    
    user_data = UserCreate(
        clerk_user_id='test_user_001',
        display_name='Test User',
        years_until_retirement=25,
        target_retirement_income=Decimal('100000')
    )
    
    existing = db_models.users.find_by_clerk_id('test_user_001')
    if existing:
        print("   ℹ️  El usuario de prueba ya existe")
    else:
        validated = user_data.model_dump()
        db_models.users.create_user(
            clerk_user_id=validated['clerk_user_id'],
            display_name=validated['display_name'],
            years_until_retirement=validated['years_until_retirement'],
            target_retirement_income=validated['target_retirement_income']
        )
        print("   ✅ Usuario de prueba creado")
    
    accounts = [
        AccountCreate(
            account_name='401(k)',
            account_purpose='Ahorro principal para la jubilación',
            cash_balance=Decimal('5000'),
            cash_interest=Decimal('0.045')
        ),
        AccountCreate(
            account_name='Roth IRA',
            account_purpose='Ahorro para jubilación libre de impuestos',
            cash_balance=Decimal('1000'),
            cash_interest=Decimal('0.04')
        ),
        AccountCreate(
            account_name='Taxable Brokerage',
            account_purpose='Cuenta de inversión general',
            cash_balance=Decimal('2500'),
            cash_interest=Decimal('0.035')
        )
    ]
    
    user_accounts = db_models.accounts.find_by_user('test_user_001')
    
    if user_accounts:
        print(f"   ℹ️  El usuario ya tiene {len(user_accounts)} cuentas")
        account_ids = [acc['id'] for acc in user_accounts]
    else:
        account_ids = []
        for acc_data in accounts:
            validated = acc_data.model_dump()
            acc_id = db_models.accounts.create_account(
                'test_user_001',
                account_name=validated['account_name'],
                account_purpose=validated['account_purpose'],
                cash_balance=validated['cash_balance'],
                cash_interest=validated['cash_interest']
            )
            account_ids.append(acc_id)
            print(f"   ✅ Cuenta creada: {validated['account_name']}")
    
    if account_ids:
        positions = [
            ('SPY', Decimal('100')),
            ('QQQ', Decimal('50')),
            ('BND', Decimal('200')),
            ('VEA', Decimal('150')),
            ('GLD', Decimal('25')),
        ]
        
        account_id = account_ids[0]
        existing_positions = db_models.positions.find_by_account(account_id)
        
        if existing_positions:
            print(f"   ℹ️  La cuenta ya tiene {len(existing_positions)} posiciones")
        else:
            for symbol, quantity in positions:
                position = PositionCreate(
                    account_id=account_id,
                    symbol=symbol,
                    quantity=quantity
                )
                validated = position.model_dump()
                db_models.positions.add_position(
                    validated['account_id'],
                    validated['symbol'],
                    validated['quantity']
                )
                print(f"   ✅ Posición agregada: {quantity} acciones de {symbol}")


def main():
    parser = argparse.ArgumentParser(description='Reiniciar la base de datos de Alex')
    parser.add_argument('--with-test-data', action='store_true',
                       help='Crear usuario de prueba con portafolio de muestra')
    parser.add_argument('--skip-drop', action='store_true',
                       help='Omitir eliminación de tablas (solo recargar datos)')
    args = parser.parse_args()
    
    print("🚀 Script de Reinicio de la Base de Datos")
    print("=" * 50)
    
    db = DataAPIClient()
    db_models = Database()
    
    if not args.skip_drop:
        drop_all_tables(db)
        
        print("\n📝 Ejecutando migraciones...")
        result = subprocess.run(
            ['uv', 'run', 'run_migrations.py'],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode != 0:
            print("❌ ¡Migración fallida!")
            print(result.stderr)
            sys.exit(1)
        else:
            print("✅ Migraciones completadas")
    
    print("\n🌱 Cargando datos semilla...")
    result = subprocess.run(
        ['uv', 'run', 'seed_data.py'],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.returncode != 0:
        print("❌ ¡Error al cargar los datos semilla!")
        print(result.stderr)
        sys.exit(1)
    else:
        if result.stdout and '22/22 instruments loaded' in result.stdout:
            print("✅ 22 instrumentos cargados")
        else:
            print("✅ Datos semilla cargados")
    
    if args.with_test_data:
        create_test_data(db_models)
    
    print("\n🔍 Verificación final...")
    tables = ['users', 'instruments', 'accounts', 'positions', 'jobs']
    for table in tables:
        result = db.query(f"SELECT COUNT(*) as count FROM {table}")
        count = result[0]['count'] if result else 0
        print(f"   • {table}: {count} registros")
    
    print("\n" + "=" * 50)
    print("✅ ¡Reinicio de la base de datos completo!")
    
    if args.with_test_data:
        print("\n📝 Usuario de prueba creado:")
        print("   • ID de usuario: test_user_001")
        print("   • 3 cuentas (401k, Roth IRA, Taxable)")
        print("   • 5 posiciones en la cuenta 401k")


if __name__ == "__main__":
    main()
