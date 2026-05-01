"""
Servicio Alex Researcher - Agente de Asesoría de Inversiones
"""

import os
import logging
from datetime import datetime, UTC
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel

# Suprimir advertencias de LiteLLM sobre dependencias opcionales
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

# Importar desde nuestros módulos
from context import get_agent_instructions, DEFAULT_RESEARCH_PROMPT
from mcp_servers import create_playwright_mcp_server
from tools import ingest_financial_document

# Cargar las variables de entorno
load_dotenv(override=True)

app = FastAPI(title="Servicio Alex Researcher")

# Configuración por variables de entorno (compatible con ECS/App Runner/local)
BEDROCK_REGION = (
    os.environ.get("AWS_REGION_NAME")
    or os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or os.environ.get("DEFAULT_AWS_REGION")
    or "us-east-1"
)

# Permite configurar el modelo sin tocar código (recomendado)
# Ejemplos:
# - bedrock/us.amazon.nova-pro-v1:0
# - bedrock/eu.amazon.nova-pro-v1:0
# - bedrock/amazon.nova-pro-v1:0 (sin perfiles de inferencia)
BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL") or "bedrock/us.amazon.nova-pro-v1:0"


# Modelo de solicitud
class ResearchRequest(BaseModel):
    topic: Optional[str] = None  # Opcional - si no se proporciona, el agente elige un tema


async def run_research_agent(topic: str = None) -> str:
    """Ejecuta el agente de investigación para generar asesoría de inversiones."""

    # Preparar la consulta del usuario
    if topic:
        query = f"Investiga este tema de inversión: {topic}"
    else:
        query = DEFAULT_RESEARCH_PROMPT

    # LiteLLM (Bedrock) requiere AWS_REGION_NAME; también seteamos las estándar de boto3
    os.environ["AWS_REGION_NAME"] = BEDROCK_REGION
    os.environ["AWS_REGION"] = BEDROCK_REGION
    os.environ["AWS_DEFAULT_REGION"] = BEDROCK_REGION

    model = LitellmModel(model=BEDROCK_MODEL)

    # Crear y ejecutar el agente con el servidor MCP
    with trace("Researcher"):
        async with create_playwright_mcp_server(timeout_seconds=60) as playwright_mcp:
            agent = Agent(
                name="Alex Investment Researcher",
                instructions=get_agent_instructions(),
                model=model,
                tools=[ingest_financial_document],
                mcp_servers=[playwright_mcp],
            )

            result = await Runner.run(agent, input=query, max_turns=15)

    return result.final_output


@app.get("/")
async def root():
    """Punto de salud (health check)."""
    return {
        "service": "Alex Researcher",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/research")
async def research(request: ResearchRequest) -> str:
    """
    Genera investigación y asesoría de inversiones.

    El agente:
    1. Navegará por sitios web financieros actuales para obtener datos
    2. Analizará la información encontrada
    3. Guardará el análisis en la base de conocimiento

    Si no se proporciona un tema, el agente elegirá uno de tendencia.
    """
    try:
        response = await run_research_agent(request.topic)
        return response
    except Exception as e:
        print(f"Error en el endpoint de investigación: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/auto")
async def research_auto():
    """
    Endpoint de investigación automática para ejecuciones programadas.
    Elige automáticamente un tema de tendencia y genera investigación.
    Usado por EventBridge Scheduler para actualizaciones periódicas de investigación.
    """
    try:
        # Siempre usar la elección del agente para ejecuciones automáticas
        response = await run_research_agent(topic=None)
        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Investigación automatizada completada",
            "preview": response[:200] + "..." if len(response) > 200 else response,
        }
    except Exception as e:
        print(f"Error en la investigación automatizada: {e}")
        return {"status": "error", "timestamp": datetime.now(UTC).isoformat(), "error": str(e)}


@app.get("/health")
async def health():
    """Chequeo de salud detallado."""
    # Detección de contenedor para depuración
    container_indicators = {
        "dockerenv": os.path.exists("/.dockerenv"),
        "containerenv": os.path.exists("/run/.containerenv"),
        "aws_execution_env": os.environ.get("AWS_EXECUTION_ENV", ""),
        "ecs_container_metadata": os.environ.get("ECS_CONTAINER_METADATA_URI", ""),
        "kubernetes_service": os.environ.get("KUBERNETES_SERVICE_HOST", ""),
    }

    return {
        "service": "Alex Researcher",
        "status": "healthy",
        "alex_api_configured": bool(os.getenv("ALEX_API_ENDPOINT") and os.getenv("ALEX_API_KEY")),
        "timestamp": datetime.now(UTC).isoformat(),
        "debug_container": container_indicators,
        "aws_region": os.environ.get("AWS_DEFAULT_REGION", "not set"),
        "bedrock_model": BEDROCK_MODEL,
    }


@app.get("/test-bedrock")
async def test_bedrock():
    """Probar la conexión con Bedrock directamente."""
    try:
        import boto3

        # Establecer TODAS las variables de región de AWS
        os.environ["AWS_REGION_NAME"] = "us-east-1"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        # Depuración: Verificar qué región usa boto3 realmente
        session = boto3.Session()
        actual_region = session.region_name

        # Intentar crear el cliente de Bedrock explícitamente en us-west-2
        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        # Depuración: Listar modelos para verificar conexión
        try:
            bedrock_client = boto3.client("bedrock", region_name="us-east-1")
            models = bedrock_client.list_foundation_models()
            openai_models = [
                m["modelId"] for m in models["modelSummaries"] if "openai" in m["modelId"].lower()
            ]
        except Exception as list_error:
            openai_models = f"Error al listar: {str(list_error)}"

        # Intentar invocación básica al modelo Nova Pro
        model = LitellmModel(model="bedrock/amazon.nova-pro-v1:0")

        agent = Agent(
            name="Agente de Prueba",
            instructions="Eres un asistente útil. Sé muy breve.",
            model=model,
        )

        result = await Runner.run(agent, input="Saluda en 5 palabras o menos", max_turns=1)

        return {
            "status": "success",
            "model": str(model.model),  # Usar el modelo real de LitellmModel
            "region": actual_region,
            "response": result.final_output,
            "debug": {
                "boto3_session_region": actual_region,
                "available_openai_models": openai_models,
            },
        }
    except Exception as e:
        import traceback

        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "debug": {
                "boto3_session_region": session.region_name if "session" in locals() else "unknown",
                "env_vars": {
                    "AWS_REGION_NAME": os.environ.get("AWS_REGION_NAME"),
                    "AWS_REGION": os.environ.get("AWS_REGION"),
                    "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION"),
                },
            },
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
