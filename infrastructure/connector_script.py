import time
import paramiko
import os
from pathlib import Path
from scp import SCPClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


# FUNCIONES DE CONFIGURACION
def load_slave_ips(num_slaves: int = 6) -> tuple[list[str], list[str]]:
    public_ips = []
    private_ips = []

    for i in range(1, num_slaves + 1):
        slave_public_ip = os.getenv(f"SLAVE_PUBLIC_IP_{i}")
        slave_private_ip = os.getenv(f"SLAVE_PRIVATE_IP_{i}")

        if slave_public_ip is None:
            raise ValueError(
                f"SLAVE_PUBLIC_IP_{i} no está definida en el archivo .env")

        if slave_private_ip is None:
            raise ValueError(
                f"SLAVE_PRIVATE_IP_{i} no está definida en el archivo .env")

        public_ips.append(slave_public_ip)
        private_ips.append(slave_private_ip)

    return public_ips, private_ips


# CONFIGURACION
MASTER_IP = os.getenv("MASTER_IP")
SLAVES_PUBLIC_IPS, SLAVES_PRIVATE_IPS = load_slave_ips()

KEY_PATH = "id_rsa"
USERNAME = "ec2-user"

BASE_DIR = Path(__file__).resolve().parent

MODEL_NAME = "cats_vs_dogs_cnn.pth"
MODEL_FILE = BASE_DIR.parent / "model" / MODEL_NAME

FILE_NAME = "inference_server.py"
BACKEND_FILE = BASE_DIR.parent / "backend" / FILE_NAME
API_PORT = 8000


# UTILS
def ssh_connect(ip: str) -> paramiko.SSHClient:
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"\nConectando a {ip} ...")
    ssh.connect(ip, username=USERNAME, pkey=key)
    return ssh


def run_commands(ssh: paramiko.SSHClient, commands: list[str]) -> None:
    for cmd in commands:
        print(f"Ejecutando: {cmd}")
        _, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out)

        if err:
            print(err)


def upload_files(ssh: paramiko.SSHClient, files: list[tuple[str, str]]) -> None:
    with SCPClient(ssh.get_transport()) as scp:
        for src, dest in files:
            print(f"Subiendo {src} -> {dest}")
            scp.put(src, dest)


# CONFIGURAR SLAVES
def setup_slaves() -> None:
    for ip in SLAVES_PUBLIC_IPS:
        ssh = ssh_connect(ip)

        # Subir backend + modelo
        upload_files(ssh, [
            (str(MODEL_FILE), f"/home/{USERNAME}/{MODEL_NAME}"),
            (str(BACKEND_FILE), f"/home/{USERNAME}/{FILE_NAME}"),
        ])

        # Instalar Docker
        run_commands(ssh, [
            "sudo yum update -y",
            "sudo yum install -y docker",
            "sudo systemctl start docker",
            "sudo systemctl enable docker",
            f"sudo usermod -aG docker {USERNAME}",
        ])

        time.sleep(2)

        dockerfile = f"""
FROM pytorch/pytorch:latest

WORKDIR /app

COPY {FILE_NAME} /app/{FILE_NAME}
COPY {MODEL_NAME} /app/{MODEL_NAME}

RUN pip install fastapi uvicorn pillow python-multipart

CMD ["uvicorn", "inference_server:app", "--host", "0.0.0.0", "--port", "{API_PORT}"]
""".lstrip()

        print("Subiendo Dockerfile...")
        sftp = ssh.open_sftp()
        with sftp.open(f"/home/{USERNAME}/Dockerfile", "w") as f:
            f.write(dockerfile)
        sftp.close()

        # Construir y ejecutar la app backend con restart policy
        run_commands(ssh, [
            "cd /home/ec2-user && sudo docker build -t fastapi_app .",
            "sudo docker rm -f fastapi_app || true",
            f"sudo docker run -d -p {API_PORT}:{API_PORT} --name fastapi_app --restart=always fastapi_app",
        ])

        print(f"Slave configurado correctamente: {ip}")
        ssh.close()


# CONFIGURAR MASTER
def setup_master() -> None:
    ssh = ssh_connect(MASTER_IP)

    upstream = "\n        ".join(
        [f"server {ip}:{API_PORT};" for ip in SLAVES_PRIVATE_IPS])

    nginx_conf = f"""
user nginx;
worker_processes auto;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {{
    worker_connections 1024;
}}

http {{
    upstream fastapi_app {{
        {upstream}
    }}

    server {{
        listen 80;

        location / {{
            proxy_pass http://fastapi_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
}}
""".lstrip()

    print("Subiendo configuracion de NGINX...")
    sftp = ssh.open_sftp()
    with sftp.open(f"/home/{USERNAME}/nginx.conf", "w") as f:
        f.write(nginx_conf)
    sftp.close()

    run_commands(ssh, [
        "sudo yum update -y",
        "sudo yum install -y nginx",
        "sudo systemctl start nginx",
        "sudo systemctl enable nginx",
        f"sudo mv -f /home/{USERNAME}/nginx.conf /etc/nginx/nginx.conf",
        "sudo nginx -t",
        "sudo systemctl restart nginx",
    ])

    print("Master configurado correctamente.")
    ssh.close()


if __name__ == "__main__":
    print("\n=== CONFIGURANDO SLAVES ===")
    setup_slaves()

    print("\n=== CONFIGURANDO MASTER ===")
    setup_master()

    print("\n=== CONFIGURACION COMPLETA ===\n")
