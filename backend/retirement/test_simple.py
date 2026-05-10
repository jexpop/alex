#!/usr/bin/env python3
"""
Prueba simple para el agente de jubilación
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

def test_retirement():
    """Prueba el agente de jubilación con datos simples de portafolio"""
    
    # Crea un trabajo real en la base de datos
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
                    "type": "retirement",
                    "cash_balance": 10000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 100,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "allocation_asset_class": {"equity": 100}
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    print("Probando el agente de jubilación...")
    print("=" * 60)
    
    result = lambda_handler(test_event, None)
    
    print(f"Código de estado: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        body = json.loads(result['body'])
        print(f"Éxito: {body.get('success', False)}")
        print(f"Mensaje: {body.get('message', 'N/A')}")
        
        print("\n" + "=" * 60)
        print("VERIFICANDO EL CONTENIDO DE LA BASE DE DATOS")
        print("=" * 60)
        
        job = db.jobs.find_by_id(job_id)
        if job and job.get('retirement_payload'):
            payload = job['retirement_payload']
            print(f"✅ Datos de jubilación encontrados en la base de datos")
            print(f"Claves del payload: {list(payload.keys())}")
            
            if 'analysis' in payload:
                analysis = payload['analysis']
                print(f"\nTipo de análisis: {type(analysis).__name__}")
                
                if isinstance(analysis, str):
                    print(f"Longitud del análisis: {len(analysis)} caracteres")
                    
                    reasoning_indicators = [
                        "I need to", "I will", "Let me", "First,",
                        "I should", "I'll", "Now I", "Next,",
                    ]
                    
                    contains_reasoning = any(indicator.lower() in analysis.lower() for indicator in reasoning_indicators)
                    
                    if contains_reasoning:
                        print("⚠️  ADVERTENCIA: El análisis puede contener texto de razonamiento/pensamiento")
                    else:
                        print("✅ El análisis parece ser solo salida final (no se detectó razonamiento)")
                    
                    print(f"\nPrimeros 500 caracteres:")
                    print("-" * 40)
                    print(analysis[:500])
                    print("-" * 40)
                    
                    if len(analysis) > 700:
                        print(f"\nÚltimos 200 caracteres:")
                        print("-" * 40)
                        print(analysis[-200:])
                        print("-" * 40)
                else:
                    print(f"⚠️  El análisis no es una cadena: {type(analysis)}")
                    print(f"Contenido: {str(analysis)[:200]}")
            
            print(f"\nGenerado en: {payload.get('generated_at', 'N/A')}")
            print(f"Agente: {payload.get('agent', 'N/A')}")
        else:
            print("❌ No se encontraron datos de jubilación en la base de datos")
    else:
        print(f"Error: {result['body']}")
    
    # Limpieza - elimina el trabajo de prueba
    db.jobs.delete(job_id)
    print(f"\nTrabajo de prueba eliminado: {job_id}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_retirement()
