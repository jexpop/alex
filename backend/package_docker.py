#!/usr/bin/env python3
"""
Empaqueta todas las funciones Lambda usando Docker para compatibilidad con AWS.
Ejecuta el script package_docker.py de cada agente.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_packaging(agent_name):
    """Empaqueta un agente específico."""
    agent_dir = Path(__file__).parent / agent_name
    package_script = agent_dir / "package_docker.py"

    if not package_script.exists():
        print(f"  ❌ {agent_name}: Falta package_docker.py")
        return False

    print(f"\n📦 Empaquetando agente {agent_name.upper()}...")
    print(f"  Ejecutando: cd {agent_dir} && uv run package_docker.py")

    try:
        result = subprocess.run(
            ["uv", "run", "package_docker.py"], cwd=str(agent_dir), capture_output=True, text=True
        )

        if result.returncode == 0:
            # Busca el archivo zip creado
            zip_files = list(agent_dir.glob("*.zip"))
            if zip_files:
                zip_file = zip_files[0]
                size_mb = zip_file.stat().st_size / (1024 * 1024)
                print(f"  ✅ Creado: {zip_file.name} ({size_mb:.1f} MB)")
                return True
            else:
                print(f"  ⚠️  Advertencia: No se encontró archivo zip tras empaquetar")
                return True
        else:
            print(
                f"  ❌ Error con {agent_name.upper()}:\nPuedes ignorar advertencias sobre el entorno uv:\n{result.stderr}\nSalida del script:\n{result.stdout}"
            )
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Empaqueta todas las funciones Lambda."""
    print("=" * 60)
    print("EMPAQUETANDO TODAS LAS FUNCIONES LAMBDA")
    print("=" * 60)

    agents = ["tagger", "reporter", "charter", "retirement", "planner"]
    results = {}

    for agent in agents:
        success = run_packaging(agent)
        results[agent] = success

    print("\n" + "=" * 60)
    print("RESUMEN DE EMPAQUETADO")
    print("=" * 60)

    success_count = sum(1 for s in results.values() if s)
    total_count = len(results)

    for agent, success in results.items():
        status = "✅ Éxito" if success else "❌ Fallo"
        print(f"{agent.ljust(12)}: {status}")

    print("\n" + "=" * 60)
    print(f"Empaquetado: {success_count}/{total_count}")

    if success_count == total_count:
        print("\n✅ ¡TODAS LAS FUNCIONES LAMBDA SE HAN EMPAQUETADO CORRECTAMENTE!")
        print("\nSiguientes pasos:")
        print("1. Despliega infraestructura: cd terraform/6_agents && terraform apply")
        print("2. Despliega las funciones Lambda: cd backend && uv run deploy_all_lambdas.py")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count} agentes fallaron en el empaquetado")
        return 1


if __name__ == "__main__":
    sys.exit(main())