#!/usr/bin/env python3
"""
Prueba simple para el agente Reporter
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import json
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database
from src.schemas import JobCreate
from lambda_handler import lambda_handler

def test_reporter():
    """Prueba el agente reporter con datos de portafolio simples"""
    
    # Crear un trabajo real en la base de datos
    db = Database()
    job_create = JobCreate(
        clerk_user_id="test_user_001",
        job_type="portfolio_analysis",
        request_payload={"test": True}
    )
    job_id = db.jobs.create(job_create.model_dump())
    print(f"Trabajo de prueba creado: {job_id}")
    
    test_event = {
        "job_id": job_id,
        "portfolio_data": {
            "accounts": [
                {
                    "name": "401(k)",
                    "cash_balance": 5000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 100,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "asset_class": "equity"
                            }
                        }
                    ]
                }
            ]
        },
        "user_data": {
            "years_until_retirement": 25,
            "target_retirement_income": 75000
        }
    }
    
    print("Probando el agente Reporter...")
    print("=" * 60)
    
    result = lambda_handler(test_event, None)
    
    print(f"Código de estado: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        body = json.loads(result['body'])
        print(f"Éxito: {body.get('success', False)}")
        print(f"Mensaje: {body.get('message', 'N/A')}")
        
        # Verificar lo que realmente se guardó en la base de datos
        print("\n" + "=" * 60)
        print("REVISANDO CONTENIDO DE LA BASE DE DATOS")
        print("=" * 60)
        
        job = db.jobs.find_by_id(job_id)
        if job and job.get('report_payload'):
            payload = job['report_payload']
            print(f"✅ Datos del informe encontrados en la base de datos")
            print(f"Claves de payload: {list(payload.keys())}")
            
            if 'content' in payload:
                content = payload['content']
                print(f"\nTipo de contenido: {type(content).__name__}")
                
                if isinstance(content, str):
                    print(f"Longitud del informe: {len(content)} caracteres")
                    
                    reasoning_indicators = [
                        "I need to", "I will", "Let me", "First,",
                        "I should", "I'll", "Now I", "Next,",
                    ]
                    
                    contains_reasoning = any(indicator.lower() in content.lower() for indicator in reasoning_indicators)
                    
                    if contains_reasoning:
                        print("⚠️  ADVERTENCIA: El informe puede contener texto de razonamiento/pensamiento")
                    else:
                        print("✅ El informe parece ser solo la salida final (no se detectó razonamiento)")
                    
                    print(f"\nPrimeros 500 caracteres:")
                    print("-" * 40)
                    print(content[:500])
                    print("-" * 40)
                    
                    if len(content) > 700:
                        print(f"\nÚltimos 200 caracteres:")
                        print("-" * 40)
                        print(content[-200:])
                        print("-" * 40)
                else:
                    print(f"⚠️  El contenido no es una cadena: {type(content)}")
                    print(f"Contenido: {str(content)[:200]}")
            
            print(f"\nGenerado en: {payload.get('generated_at', 'N/A')}")
            print(f"Agente: {payload.get('agent', 'N/A')}")
        else:
            print("❌ No se encontraron datos del informe en la base de datos")
    else:
        print(f"Error: {result['body']}")
    
    # Limpieza - eliminar el trabajo de prueba
    db.jobs.delete(job_id)
    print(f"\nTrabajo de prueba eliminado: {job_id}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_reporter()
