#!/usr/bin/env python3
"""
Empaqueta la función Lambda Planner usando Docker para compatibilidad con AWS.
Utiliza la imagen oficial de runtime de AWS Lambda Python para garantizar la compatibilidad binaria.
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, cwd=None):
    """Ejecuta un comando mostrando salida en tiempo real."""

    print(f"\nEjecutando: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # Mostrar salida en tiempo real
    for line in process.stdout:
        print(line, end="")

    process.wait()

    if process.returncode != 0:
        print(f"\n❌ Error ejecutando comando: {' '.join(cmd)}")
        sys.exit(process.returncode)


def package_lambda():
    """Empaqueta la función Lambda con todas las dependencias."""

    # Directorios
    planner_dir = Path(__file__).parent.absolute()
    backend_dir = planner_dir.parent

    # Crear directorio temporal
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()

        print("\n============================================================")
        print("CREANDO PAQUETE LAMBDA USANDO DOCKER")
        print("============================================================")

        # Exportar requirements desde uv.lock
        print("\n📦 Exportando requirements desde uv.lock...")

        requirements_file = temp_path / "requirements.txt"

        export_cmd = [
            "uv",
            "export",
            "--no-hashes",
            "--no-emit-project",
        ]

        result = subprocess.run(
            export_cmd,
            cwd=str(planner_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            print(result.stderr)
            sys.exit(1)

        # Filtrar paquetes incompatibles
        filtered_requirements = []

        for line in result.stdout.splitlines():
            if line.startswith("pyperclip"):
                print(f"⚠️ Excluyendo de Lambda: {line}")
                continue

            filtered_requirements.append(line)

        requirements_file.write_text(
            "\n".join(filtered_requirements),
            encoding="utf-8",
        )

        print(f"✅ Requirements generados: {requirements_file}")

        # Paths Docker compatibles con Windows
        temp_mount = temp_path.as_posix()
        db_mount = (backend_dir / "database").as_posix()

        print("\n🐳 Instalando dependencias dentro de Docker...")

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "-v",
            f"{temp_mount}:/build",
            "-v",
            f"{db_mount}:/database",
            "--entrypoint",
            "/bin/bash",
            "public.ecr.aws/lambda/python:3.11",
            "-c",
            (
                "cd /build && "
                "pip install -v --target ./package -r requirements.txt && "
                "pip install -v --target ./package --no-deps /database"
            ),
        ]

        run_command(docker_cmd)

        print("\n📄 Copiando archivos Lambda...")

        files_to_copy = [
            "lambda_handler.py",
            "agent.py",
            "templates.py",
            "market.py",
            "prices.py",
            "observability.py",
        ]

        for file_name in files_to_copy:
            source = planner_dir / file_name

            if source.exists():
                shutil.copy(source, package_dir)
                print(f"  ✅ {file_name}")
            else:
                print(f"  ⚠️ No encontrado: {file_name}")

        # Crear ZIP usando Python (compatible con Windows)
        zip_path = planner_dir / "planner_lambda.zip"

        if zip_path.exists():
            zip_path.unlink()

        print("\n🗜️ Creando ZIP...")

        shutil.make_archive(
            str(zip_path).replace(".zip", ""),
            "zip",
            root_dir=str(package_dir),
        )

        size_mb = zip_path.stat().st_size / (1024 * 1024)

        print("\n============================================================")
        print("✅ PAQUETE CREADO CORRECTAMENTE")
        print("============================================================")
        print(f"Archivo: {zip_path}")
        print(f"Tamaño: {size_mb:.2f} MB")

        return zip_path


def deploy_lambda(zip_path):
    """Despliega la función Lambda en AWS."""

    import boto3

    lambda_client = boto3.client("lambda")
    function_name = "alex-planner"

    print(f"\n🚀 Desplegando Lambda: {function_name}")

    try:
        with open(zip_path, "rb") as f:
            response = lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=f.read(),
            )

        print("\n✅ Lambda actualizada correctamente")
        print(f"ARN: {response['FunctionArn']}")

    except lambda_client.exceptions.ResourceNotFoundException:
        print(
            f"\n❌ La función Lambda '{function_name}' no existe."
        )
        print("Despliega primero la infraestructura con Terraform.")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error desplegando Lambda: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Empaqueta Planner Lambda para despliegue"
    )

    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Desplegar en AWS después de empaquetar",
    )

    args = parser.parse_args()

    # Verificar Docker
    print("🔍 Verificando Docker...")

    try:
        run_command(["docker", "--version"])
    except FileNotFoundError:
        print("\n❌ Docker no está instalado o no está en PATH")
        sys.exit(1)

    # Empaquetar
    zip_path = package_lambda()

    # Deploy opcional
    if args.deploy:
        deploy_lambda(zip_path)


if __name__ == "__main__":
    main()