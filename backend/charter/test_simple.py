#!/usr/bin/env python3
"""
Prueba simple para el agente Charter
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


def test_charter():
    """Prueba el agente charter con datos de portafolio simples"""

    # Crea un trabajo real en la base de datos
    db = Database()
    job_create = JobCreate(
        clerk_user_id="test_user_001", job_type="portfolio_analysis", request_payload={"test": True}
    )
    job_id = db.jobs.create(job_create.model_dump())
    print(f"Trabajo de prueba creado: {job_id}")

    test_event = {
        "job_id": job_id,
        "portfolio_data": {
            "accounts": [
                {
                    "name": "401(k)",
                    "type": "401k",
                    "cash_balance": 5000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 100,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "allocation_asset_class": {"equity": 100},
                                "allocation_regions": {"north_america": 100},
                                "allocation_sectors": {
                                    "technology": 30,
                                    "healthcare": 15,
                                    "financials": 15,
                                },
                            },
                        }
                    ],
                }
            ]
        },
    }

    print("Probando el Agente Charter...")
    print("=" * 60)

    print("A punto de llamar a lambda_handler...", flush=True)
    sys.stdout.flush()
    result = lambda_handler(test_event, None)
    print("lambda_handler ha regresado", flush=True)

    print(f"Código de estado: {result['statusCode']}")

    if result["statusCode"] == 200:
        body = json.loads(result["body"])
        print(f"Éxito: {body.get('success', False)}")
        print(f"Mensaje: {body.get('message', 'N/A')}")

        # Comprueba qué gráficos fueron creados
        job = db.jobs.find_by_id(job_id)
        if job and job.get("charts_payload"):
            print(f"\n📊 Gráficos Creados ({len(job['charts_payload'])} en total):")
            print("=" * 50)
            for chart_key, chart_data in job["charts_payload"].items():
                print(f"\n🎯 Gráfico: {chart_key}")
                print(f"   Título: {chart_data.get('title', 'N/A')}")
                print(f"   Tipo: {chart_data.get('type', 'N/A')}")
                print(f"   Descripción: {chart_data.get('description', 'N/A')}")

                data_points = chart_data.get("data", [])
                print(f"   Puntos de Datos ({len(data_points)}):")
                for i, point in enumerate(data_points):
                    name = point.get("name", "N/A")
                    value = point.get("value", 0)
                    color = point.get("color", "N/A")
                    print(f"     {i+1}. {name}: ${value:,.2f} {color}")

        else:
            print("\n❌ No se encontraron gráficos en la base de datos")
    else:
        print(f"Error: {result['body']}")

    # Limpieza - elimina el trabajo de prueba
    db.jobs.delete(job_id)
    print(f"Trabajo de prueba eliminado: {job_id}")

    print("=" * 60)


if __name__ == "__main__":
    test_charter()
