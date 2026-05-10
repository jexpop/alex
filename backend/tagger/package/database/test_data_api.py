#!/usr/bin/env python3
"""
Prueba de conexión a Aurora Data API
Este script verifica que Aurora Serverless v2 está configurado correctamente y con Data API habilitada.
"""

import boto3
import json
import os
import sys
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

def get_current_region():
    """Obtener la región actual de AWS desde la sesión"""
    session = boto3.Session()
    return session.region_name or os.getenv('DEFAULT_AWS_REGION', 'us-east-1')

def get_cluster_details(region):
    """Obtener el ARN del cluster de Aurora y el ARN del secreto desde las variables de entorno, o verifica que existan"""
    
    # Primero intentar obtener de las variables de entorno
    cluster_arn = os.getenv('AURORA_CLUSTER_ARN')
    secret_arn = os.getenv('AURORA_SECRET_ARN')
    
    if cluster_arn and secret_arn:
        print(f"📋 Usando configuración de archivo .env")
        
        # Verificar que el cluster existe y que Data API está habilitada
        rds_client = boto3.client('rds', region_name=region)
        try:
            cluster_id = cluster_arn.split(':')[-1]
            response = rds_client.describe_db_clusters(
                DBClusterIdentifier=cluster_id
            )
            
            if response['DBClusters']:
                cluster = response['DBClusters'][0]
                if not cluster.get('HttpEndpointEnabled', False):
                    print("❌ Data API no está habilitado en el clúster de Aurora")
                    print("💡 Ejecuta: aws rds modify-db-cluster --db-cluster-identifier alex-aurora-cluster --enable-http-endpoint --apply-immediately")
                    return None, None
            else:
                print(f"❌ No se encontró el clúster de Aurora '{cluster_id}'")
                return None, None
                
        except ClientError as e:
            print(f"⚠️  No se pudo verificar el estado del clúster: {e}")
            # Continuar de todos modos - el clúster podría existir aunque no podamos describirlo
        
        return cluster_arn, secret_arn
    
    # En caso de que no esté en .env, intentar auto-descubrir
    print("⚠️  No se encontró AURORA_CLUSTER_ARN o AURORA_SECRET_ARN en el archivo .env")
    print("💡 Después de ejecutar 'terraform apply', agrega estos valores a tu archivo .env:")
    print("   AURORA_CLUSTER_ARN=<tu-cluster-arn>")
    print("   AURORA_SECRET_ARN=<tu-secret-arn>")
    print("\nIntentando autodescubrir recursos de Aurora...")
    
    rds_client = boto3.client('rds', region_name=region)
    secrets_client = boto3.client('secretsmanager', region_name=region)
    
    try:
        # Obtener ARN del clúster
        response = rds_client.describe_db_clusters(
            DBClusterIdentifier='alex-aurora-cluster'
        )
        
        if not response['DBClusters']:
            print("❌ No se encontró clúster de Aurora 'alex-aurora-cluster'")
            return None, None
        
        cluster = response['DBClusters'][0]
        cluster_arn = cluster['DBClusterArn']
        
        # Comprobar si Data API está habilitado
        if not cluster.get('HttpEndpointEnabled', False):
            print("❌ Data API no está habilitado en el clúster de Aurora")
            print("💡 Ejecuta: aws rds modify-db-cluster --db-cluster-identifier alex-aurora-cluster --enable-http-endpoint --apply-immediately")
            return None, None
        
        # Buscar el secreto de aurora de alex más recientemente creado
        secrets = secrets_client.list_secrets()
        aurora_secrets = []
        
        for secret in secrets['SecretList']:
            if 'aurora' in secret['Name'].lower() and 'alex' in secret['Name'].lower():
                aurora_secrets.append(secret)
        
        if not aurora_secrets:
            print("❌ No se pudieron encontrar credenciales de Aurora en Secrets Manager")
            print("💡 Busca un secreto que contenga 'aurora' en el nombre")
            return None, None
        
        # Ordenar por fecha de creación y tomar el más reciente
        aurora_secrets.sort(key=lambda x: x.get('CreatedDate', ''), reverse=True)
        secret_arn = aurora_secrets[0]['ARN']
        
        print(f"\n📝 Se han encontrado recursos de Aurora. Agrega estos valores a tu archivo .env:")
        print(f"AURORA_CLUSTER_ARN={cluster_arn}")
        print(f"AURORA_SECRET_ARN={secret_arn}")
        
        return cluster_arn, secret_arn
        
    except ClientError as e:
        print(f"❌ Error accediendo a recursos de AWS: {e}")
        return None, None

def test_data_api(cluster_arn, secret_arn, region):
    """Probar la conexión a Data API"""
    client = boto3.client('rds-data', region_name=region)
    
    print(f"\n🔍 Probando la conexión Data API")
    print(f"   Región: {region}")
    print(f"   Cluster ARN: {cluster_arn}")
    print(f"   Secret ARN: {secret_arn}")
    print("-" * 50)
    
    # Prueba 1: SELECT simple
    print("\n1️⃣ Probando un SELECT básico...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database='alex',
            sql='SELECT 1 as test_connection, current_timestamp as server_time'
        )
        
        if response['records']:
            test_val = response['records'][0][0].get('longValue')
            server_time = response['records'][0][1].get('stringValue')
            print(f"   ✅ ¡Conexión exitosa!")
            print(f"   Hora del servidor: {server_time}")
        else:
            print("   ❌ Consulta ejecutada pero sin resultados")
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'BadRequestException':
            # Esto podría significar que la base de datos aún no existe
            print(f"   ⚠️  Es posible que la base de datos 'alex' no exista o las credenciales sean incorrectas")
            print(f"   Error: {e.response['Error']['Message']}")
            
            # Intentar sin especificar base de datos
            print("\n   Reintentando sin el parámetro de base de datos...")
            try:
                response = client.execute_statement(
                    resourceArn=cluster_arn,
                    secretArn=secret_arn,
                    sql='SELECT current_database()'
                )
                print(f"   ✅ Conexión exitosa (pero podría no existir la base de datos 'alex')")
                return True
            except:
                pass
        else:
            print(f"   ❌ Error: {e}")
        return False
    
    # Prueba 2: Comprobar tablas existentes
    print("\n2️⃣ Comprobando tablas existentes...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database='alex',
            sql="""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """
        )
        
        tables = [record[0].get('stringValue') for record in response.get('records', [])]
        
        if tables:
            print(f"   ✅ Se encontraron {len(tables)} tablas:")
            for table in tables:
                print(f"      - {table}")
        else:
            print("   ℹ️  No se encontraron tablas (la base de datos está vacía)")
            print("   💡 Ejecuta el script de migración para crear tablas")
            
    except ClientError as e:
        print(f"   ⚠️  No se pudieron listar las tablas: {e}")
    
    # Prueba 3: Comprobar tamaño de la base de datos
    print("\n3️⃣ Comprobando información de la base de datos...")
    try:
        response = client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database='alex',
            sql="SELECT pg_database_size('alex') as size_bytes"
        )
        
        if response['records']:
            size_bytes = response['records'][0][0].get('longValue', 0)
            size_mb = size_bytes / (1024 * 1024)
            print(f"   ✅ Tamaño de la base de datos: {size_mb:.2f} MB")
            
    except:
        pass
    
    print("\n" + "=" * 50)
    print("✅ ¡Data API funciona correctamente!")
    print("\n📝 Siguientes pasos:")
    print("1. Ejecuta migraciones para crear tablas: uv run migrate.py")
    print("2. Carga datos semilla: uv run seed_data.py")
    print("3. Prueba el paquete de base de datos: uv run test_db.py")
    
    return True

def main():
    """Función principal"""
    print("🚀 Prueba de conexión a Aurora Data API")
    print("=" * 50)
    
    # Obtener región actual
    region = get_current_region()
    print(f"📍 Usando la región de AWS: {region}")
    
    # Obtener ARNs del clúster y secreto
    cluster_arn, secret_arn = get_cluster_details(region)
    
    if not cluster_arn or not secret_arn:
        print("\n❌ No se pudo encontrar el clúster Aurora o las credenciales")
        print("\n💡 Asegúrate de que hayas:")
        print("   1. Creado el clúster de Aurora con 'terraform apply'")
        print("   2. Habilitado Data API en el clúster")
        print("   3. Creado credenciales en Secrets Manager")
        sys.exit(1)
    
    # Probar Data API
    success = test_data_api(cluster_arn, secret_arn, region)
    
    if not success:
        print("\n❌ Falló la prueba de Data API")
        print("\n💡 Solución de problemas:")
        print("   1. Verifica que la instancia de Aurora esté 'available'")
        print("   2. Verifica que Data API esté habilitado")
        print("   3. Revisa los permisos IAM para rds-data:ExecuteStatement")
        sys.exit(1)
    
    # Guardar detalles de conexión para otros scripts
    print(f"\n✅ ¡Prueba de Data API exitosa!")

if __name__ == "__main__":
    main()