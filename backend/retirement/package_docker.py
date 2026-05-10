import subprocess
import sys
import os
import shutil
import tempfile
import zipfile
from pathlib import Path


def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=False)
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0:
        print("❌ ERROR EJECUTANDO:", cmd)
        print(stderr)
        raise RuntimeError(stderr)
    return stdout, stderr


def create_zip(zip_path, folder):
    folder = Path(folder)
    zip_path = Path(zip_path)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for file in files:
                full = Path(root) / file
                rel = full.relative_to(folder)
                z.write(full, rel)


def package_lambda():
    print("📦 Empaquetando agente RETIREMENT")

    base = Path(__file__).resolve().parent
    package_dir = base / "package"
    database_dir = base.parent / "database"

    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()

    tmp = tempfile.mkdtemp()

    stdout, _ = run_command(["uv", "export", "--no-hashes", "--no-emit-project"])

    cleaned = []
    for line in stdout.splitlines():
        if "database" in line.lower():
            print("⚠️ Eliminando dependencia local:", line)
            continue
        cleaned.append(line)
    stdout = "\n".join(cleaned)

    req = Path(tmp) / "requirements.txt"
    req.write_text(stdout)

    run_command([
        "docker", "run", "--rm",
        "--platform", "linux/amd64",
        "-v", f"{tmp}:/build",
        "--entrypoint", "/bin/bash",
        "public.ecr.aws/lambda/python:3.13",
        "-c", "cd /build && pip install --target ./package -r requirements.txt"
    ])

    shutil.copytree(Path(tmp) / "package", package_dir, dirs_exist_ok=True)
    shutil.copytree(database_dir, package_dir / "database", dirs_exist_ok=True)

    zip_path = base / "retirement_lambda.zip"
    create_zip(zip_path, package_dir)
    print("✅ ZIP generado:", zip_path)
    return zip_path


def main():
    try:
        package_lambda()
    except Exception as e:
        print("❌ ERROR EN RETIREMENT")
        print(e)


if __name__ == "__main__":
    main()
