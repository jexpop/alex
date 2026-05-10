#!/usr/bin/env python3
"""
Empaqueta todas las funciones Lambda usando los nuevos package_docker.py corregidos.
"""

import os
import sys
import subprocess
from pathlib import Path


AGENTS = ["tagger", "reporter", "charter", "retirement", "planner"]


def run_packaging(agent_name):
    """Ejecuta el empaquetado de un agente."""
    agent_dir = Path(__file__).parent / agent_name
    script = agent_dir / "package_docker.py"

    if not script.exists():
        print(f"  ❌ {agent_name}: Falta package_docker.py")
        return False

    print(f"\n📦 Empaquetando agente {agent_name.upper()}...")
    print(f"  Ejecutando en: {agent_dir}")

    try:
        # No capturamos stdout/stderr para evitar UnicodeDecodeError
        result = subprocess.run(
            ["uv", "run", "package_docker.py"],
            cwd=str(agent_dir)
        )

        if result.returncode != 0:
            print(f"  ❌ Error empaquetando {agent_name.upper()}")
            return False

        # Buscar ZIP generado
        zip_files = list(agent_dir.glob("*.zip"))
        if not zip_files:
            print("  ⚠️ No se encontró archivo ZIP tras empaquetar")
            return False

        zip_file = zip_files[0]
        size_mb = zip_file.stat().st_size / (1024 * 1024)
        print(f"  ✅ ZIP generado: {zip_file.name} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f"  ❌ Error inesperado: {e}")
        return False


def main():
    print("=" * 60)
    print("EMPAQUETANDO TODAS LAS FUNCIONES LAMBDA")
    print("=" * 60)

    results = {}

    for agent in AGENTS:
        results[agent] = run_packaging(agent)

    print("\n" + "=" * 60)
    print("RESUMEN DE EMPAQUETADO")
    print("=" * 60)

    ok = sum(1 for v in results.values() if v)
    total = len(results)

    for agent, success in results.items():
        status = "✅ Éxito" if success else "❌ Fallo"
        print(f"{agent.ljust(12)}: {status}")

    print("\n" + "=" * 60)
    print(f"Empaquetado: {ok}/{total}")

    if ok == total:
        print("\n🎉 ¡TODAS LAS LAMBDAS SE HAN EMPAQUETADO CORRECTAMENTE!")
        return 0
    else:
        print(f"\n⚠️ {total - ok} agentes fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
