#!/usr/bin/env python3
"""
Despliega el servicio researcher en AWS ECS (Fargate + ALB)
Script de despliegue multiplataforma para Mac/Windows/Linux
"""

import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv(override=True)


def run_command(cmd, capture_output=False, shell=False, stdin_text=None):
    """Ejecuta un comando y maneja errores."""
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            shell=shell,
            capture_output=capture_output,
            text=True,
            input=stdin_text,
            check=True,
        )
        if capture_output:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar el comando: {e}")
        if e.stderr:
            print(f"Detalles del error: {e.stderr}")
        sys.exit(1)


def terraform_output(terraform_dir: Path, name: str) -> str:
    """Leer un output de Terraform desde terraform/4_researcher."""
    original_dir = os.getcwd()
    try:
        os.chdir(terraform_dir)
        try:
            return run_command(["terraform", "output", "-raw", name], capture_output=True)
        except SystemExit:
            # Si el output no existe aún en el state, devolvemos vacío para permitir fallback.
            return ""
    finally:
        os.chdir(original_dir)


def parse_region_from_ecr_url(ecr_url: str) -> str:
    """
    Ejemplo URL: 123456789012.dkr.ecr.us-east-1.amazonaws.com/alex-researcher
    """
    host = ecr_url.split("/")[0]
    parts = host.split(".")
    # account.dkr.ecr.<region>.amazonaws.com
    return parts[3]


def main():
    print("Servicio Alex Researcher - Despliegue Docker")
    print("===========================================")

    # Obtener el ID de cuenta de AWS
    print("\nObteniendo detalles de la cuenta AWS...")
    account_id = run_command(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True,
    )

    ecr_repository = "alex-researcher"

    print(f"Cuenta AWS: {account_id}")

    # Obtener la URL del repositorio ECR desde Terraform
    print("\nObteniendo URL del repositorio ECR...")
    terraform_dir = Path(__file__).parent.parent.parent / "terraform" / "4_researcher"
    ecr_url = terraform_output(terraform_dir, "ecr_repository_url")

    if not ecr_url:
        print("Error: Repositorio ECR no encontrado. Ejecuta 'terraform apply' primero.")
        sys.exit(1)

    region = parse_region_from_ecr_url(ecr_url)
    print(f"Región: {region}")
    print(f"Repositorio ECR: {ecr_url}")

    # Iniciar sesión en ECR
    print("\nIniciando sesión en ECR...")
    password = run_command(
        ["aws", "ecr", "get-login-password", "--region", region], capture_output=True
    )

    ecr_registry = ecr_url.split("/")[0]
    run_command(
        ["docker", "login", "--username", "AWS", "--password-stdin", ecr_registry],
        capture_output=True,
        stdin_text=password,
    )

    print("¡Inicio de sesión exitoso!")

    # Generar un tag único usando timestamp
    import time

    timestamp = int(time.time())
    image_tag = f"deploy-{timestamp}"

    # Construir la imagen Docker
    print(f"\nConstruyendo imagen Docker para linux/amd64 con la etiqueta: {image_tag}")
    print("(Esto asegura compatibilidad con AWS ECS/Fargate)")
    run_command(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            f"{ecr_repository}:{image_tag}",
            # Eliminado --no-cache para usar caching de capas Docker y acelerar builds
            ".",
        ]
    )

    # Etiquetar para ECR con tag único y latest
    print("\nEtiquetando imagen para ECR...")
    run_command(["docker", "tag", f"{ecr_repository}:{image_tag}", f"{ecr_url}:{image_tag}"])
    run_command(["docker", "tag", f"{ecr_repository}:{image_tag}", f"{ecr_url}:latest"])

    # Subir a ECR
    print("\nSubiendo imagen a ECR...")
    run_command(["docker", "push", f"{ecr_url}:{image_tag}"])
    run_command(["docker", "push", f"{ecr_url}:latest"])

    print("\n✅ ¡Imagen Docker subida exitosamente!")

    # Si el servicio ECS ya existe, forzar un nuevo despliegue (el task definition usa :latest)
    print("\nForzando un nuevo despliegue en ECS (si existe)...")
    try:
        # Los outputs pueden no existir si no has hecho terraform apply desde que se añadieron.
        cluster_name = terraform_output(terraform_dir, "ecs_cluster_name") or "alex-researcher"
        service_name = terraform_output(terraform_dir, "ecs_service_name") or "alex-researcher"
        service_url = terraform_output(terraform_dir, "service_url") or "(service_url no disponible)"

        run_command(
            [
                "aws",
                "ecs",
                "update-service",
                "--region",
                region,
                "--cluster",
                cluster_name,
                "--service",
                service_name,
                "--force-new-deployment",
            ],
            capture_output=True,
        )

        print("✅ Update-service lanzado (ECS descargará :latest y reiniciará tasks).")
        print("\n🚀 Servicio:")
        print(f"   {service_url}")
        print("\nPrueba con:")
        print(f"   curl {service_url}/health")
    except Exception as e:
        print(f"\n⚠️ No pude forzar el despliegue en ECS automáticamente: {e}")
        print("Si aún no has creado la infraestructura, ejecuta:")
        print("  cd terraform/4_researcher && terraform apply")
        print("\nSi el servicio ya existe, puedes forzar redeploy con:")
        print("  aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment")


if __name__ == "__main__":
    main()
