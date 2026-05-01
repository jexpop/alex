#!/usr/bin/env python3
"""
Prueba el servicio researcher generando investigación de inversión.
Script multiplataforma para Mac/Windows/Linux.
"""

import subprocess
import sys
import requests
import argparse


def get_service_url():
    """Obtener la URL pública del servicio desde Terraform (ALB)."""
    try:
        from pathlib import Path
        import os

        terraform_dir = Path(__file__).parent.parent.parent / "terraform" / "4_researcher"
        original_dir = os.getcwd()
        try:
            os.chdir(terraform_dir)
            result = subprocess.run(
                ["terraform", "output", "-raw", "service_url"],
                capture_output=True,
                text=True,
                check=True,
            )
        finally:
            os.chdir(original_dir)

        url = result.stdout.strip()
        if not url:
            raise RuntimeError("Terraform output service_url devolvió vacío.")

        return url
    except subprocess.CalledProcessError as e:
        print(f"❌ Error obteniendo la URL del servicio desde Terraform: {e}")
        print("   Asegúrate de haber ejecutado 'terraform apply' en terraform/4_researcher.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error obteniendo la URL del servicio: {e}")
        sys.exit(1)


def test_research(topic=None):
    """Prueba el servicio researcher con un tema."""
    # Si no hay tema, dejar que el agente escoja uno
    display_topic = topic if topic else "Elección del agente (tema en tendencia)"
    
    # Obtener la URL del servicio
    print("Obteniendo la URL del servicio (ALB) desde Terraform...")
    service_url = get_service_url()
    
    if not service_url:
        print("❌ No se pudo obtener la URL del servicio")
        sys.exit(1)
    
    print(f"✅ Servicio encontrado en: {service_url}")
    
    # Probar primero el endpoint de salud
    print("\nComprobando la salud del servicio...")
    try:
        health_url = f"{service_url}/health"
        response = requests.get(health_url, timeout=10)
        response.raise_for_status()
        print("✅ El servicio está saludable")
    except requests.exceptions.RequestException as e:
        print(f"❌ Falló la comprobación de salud: {e}")
        print("   El servicio puede que todavía esté iniciando. Inténtalo de nuevo en un minuto.")
        sys.exit(1)
    
    # Llamar al endpoint de research
    print(f"\n🔬 Generando investigación para: {display_topic}")
    print("   Esto tomará 20-30 segundos mientras el agente investiga y analiza...")
    
    try:
        research_url = f"{service_url}/research"
        # Solo incluir el tema en el payload si está proporcionado
        payload = {"topic": topic} if topic else {}
        response = requests.post(
            research_url,
            json=payload,
            timeout=180  # Darle 3 minutos para la investigación
        )
        response.raise_for_status()
        
        # Analizar y mostrar el resultado
        result = response.json()
        
        print("\n✅ ¡Investigación generada exitosamente!")
        print("\n" + "="*60)
        print("RESULTADO DE LA INVESTIGACIÓN:")
        print("="*60)
        print(result)
        print("="*60)
        
        print("\n✅ La investigación ha sido almacenada automáticamente en tu base de conocimientos.")
        print("   Para verificar, ejecuta:")
        print("     cd ../ingest")
        print("     uv run test_search_s3vectors.py")
        
    except requests.exceptions.Timeout:
        print("❌ Tiempo de espera agotado. El servicio podría estar bajo alta carga.")
        print("   Inténtalo de nuevo en un momento.")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al llamar al endpoint de investigación: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Detalles del error: {error_detail}")
            except (json.JSONDecodeError, AttributeError):
                print(f"   Respuesta: {e.response.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Prueba el servicio Alex Researcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Dejar que el agente elija un tema en tendencia
  uv run test_research.py
  
  # Investigar un tema específico
  uv run test_research.py "Ventajas competitivas de Tesla"
  
  # Investigar otro tema
  uv run test_research.py "Crecimiento de ingresos de la nube de Microsoft"
        """
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Tema de inversión a investigar (opcional - el agente elegirá un tema en tendencia si no se proporciona)"
    )
    
    args = parser.parse_args()
    test_research(args.topic)


if __name__ == "__main__":
    main()