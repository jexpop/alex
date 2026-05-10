#!/usr/bin/env python3
"""
Empaqueta la función Lambda de Retirement usando Docker para compatibilidad con AWS.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, cwd=None):
    """Ejecuta un comando y captura la salida."""
    print(f"Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def package_lambda():
    """Empaqueta la función Lambda con todas las dependencias."""
    
    retirement_dir = Path(__file__).parent.absolute()
    backend_dir = retirement_dir.parent
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()
        
        print("Creando paquete Lambda usando Docker...")
        
        print("Exportando requisitos desde uv.lock...")
        requirements_result = run_command(
            ["uv", "export", "--no-hashes", "--no-emit-project"],
            cwd=str(retirement_dir)
        )

        filtered_requirements = []
        for line in requirements_result.splitlines():
            if line.startswith("pyperclip"):
                print(f"Excluyendo de Lambda: {line}")
                continue
            filtered_requirements.append(line)

        req_file = temp_path / "requirements.txt"
        req_file.write_text("\n".join(filtered_requirements))
        
        docker_cmd = [
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{temp_path}:/build",
            "-v", f"{backend_dir}/database:/database",
            "--entrypoint", "/bin/bash",
            "public.ecr.aws/lambda/python:3.13",
            "-c",
            """cd /build && pip install --target ./package -r requirements.txt && pip install --target ./package --no-deps /database"""
        ]
        
        run_command(docker_cmd)
        
        shutil.copy(retirement_dir / "lambda_handler.py", package_dir)
        shutil.copy(retirement_dir / "agent.py", package_dir)
        shutil.copy(retirement_dir / "templates.py", package_dir)
        shutil.copy(retirement_dir / "observability.py", package_dir)
        
        zip_path = retirement_dir / "retirement_lambda.zip"
        
        if zip_path.exists():
            zip_path.unlink()
        
        print(f"Creando archivo zip: {zip_path}")
        run_command(
            ["zip", "-r", str(zip_path), "."],
            cwd=str(package_dir)
        )
        
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Paquete creado: {zip_path} ({size_mb:.1f} MB)")
        
        return zip_path

def deploy_lambda(zip_path):
    """Despliega la función Lambda en AWS."""
    import boto3
    
    lambda_client = boto3.client('lambda')
    function_name = 'alex-retirement'
    
    print(f"Desplegando en la función Lambda: {function_name}")
    
    try:
        with open(zip_path, 'rb') as f:
            response = lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=f.read()
            )
        print(f"Función Lambda actualizada correctamente: {function_name}")
        print(f"ARN de la función: {response['FunctionArn']}")
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"La función Lambda {function_name} no encontrada. Por favor despliegue primero con Terraform.")
        sys.exit(1)
    except Exception as e:
        print(f"Error al desplegar Lambda: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Empaqueta Lambda Retirement para despliegue')
    parser.add_argument('--deploy', action='store_true', help='Despliega a AWS después de empaquetar')
    args = parser.parse_args()
    
    try:
        run_command(["docker", "--version"])
    except FileNotFoundError:
        print("Error: Docker no está instalado o no está en el PATH")
        sys.exit(1)
    
    zip_path = package_lambda()
    
    if args.deploy:
        deploy_lambda(zip_path)

if __name__ == "__main__":
    main()
