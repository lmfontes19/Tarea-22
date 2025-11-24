# Clasificador de Gatos vs Perros - MLOps

Sistema de clasificación de imágenes distribuido con CNN desplegado en AWS EC2 usando arquitectura Master-Slave con NGINX como load balancer.

## Tabla de Contenidos

- [Prerequisitos](#prerequisitos)
- [Configuración del Proyecto](#configuración-del-proyecto)
- [Despliegue en AWS](#despliegue-en-aws)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Ejecución del Frontend](#ejecucion-del-frontend)

## Prerequisitos

### Local Development
- Python 3.8+
- Node.js 16+
- npm o yarn

### AWS Deployment
- Cuenta de AWS
- Terraform instalado
- Clave SSH (`id_rsa`) para acceso a EC2
- 7 instancias EC2 (1 Master + 6 Slaves)

## Configuración del Proyecto

### 1. Clonar el Repositorio

```bash
git clone <repository-url>
cd Tarea-22
```

### 2. Configurar Variables de Entorno

Crear el archivo `.env` en la raíz del proyecto:

```bash
# Copiar el template
cp .env.example .env
```

Editar `.env` con tus IPs de AWS EC2:

```env
# Configuración de IPs de AWS EC2

# Master Node (NGINX Load Balancer)
MASTER_IP=<tu-master-public-ip>

# Slaves Public IPs (para SSH)
SLAVE_PUBLIC_IP_1=<slave-1-public-ip>
SLAVE_PUBLIC_IP_2=<slave-2-public-ip>
SLAVE_PUBLIC_IP_3=<slave-3-public-ip>
SLAVE_PUBLIC_IP_4=<slave-4-public-ip>
SLAVE_PUBLIC_IP_5=<slave-5-public-ip>
SLAVE_PUBLIC_IP_6=<slave-6-public-ip>

# Slaves Private IPs (para NGINX upstream)
SLAVE_PRIVATE_IP_1=<slave-1-private-ip>
SLAVE_PRIVATE_IP_2=<slave-2-private-ip>
SLAVE_PRIVATE_IP_3=<slave-3-private-ip>
SLAVE_PRIVATE_IP_4=<slave-4-private-ip>
SLAVE_PRIVATE_IP_5=<slave-5-private-ip>
SLAVE_PRIVATE_IP_6=<slave-6-private-ip>
```

### 3. Configurar el Frontend

Copiar el archivo de ejemplo y editarlo:

```bash
# Windows PowerShell
cd frontend
copy .env.example .env

# Linux/Mac
cd frontend
cp .env.example .env
```

Editar `frontend/.env` con la IP del Master:

```env
VITE_MASTER_IP=<tu-master-public-ip>
```

**Nota:** El frontend de Vite requiere que el archivo `.env` esté en su propia carpeta y las variables deben tener el prefijo `VITE_`.

## Ejecucion del Frontend

```bash
# Navegar a la carpeta frontend
cd frontend

# Instalar dependencias
npm install

# Ejecutar en modo desarrollo
npm run dev
```

La aplicación estará disponible en `http://localhost:5173`

**Importante:** Para desarrollo local, actualiza `frontend/.env`:

```env
VITE_MASTER_IP=localhost:8000
```

## Despliegue en AWS

### 1. Provisionar Infraestructura con Terraform

#### Prerequisitos de AWS

Antes de ejecutar Terraform, asegúrate de tener:

1. **AWS CLI configurado** con credenciales válidas:
```bash
aws configure
```

Proporciona:
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `us-east-1`
- Default output format: `json`

2. **Terraform instalado** (versión 1.0+):
```bash
# Verificar instalación
terraform --version
```

#### Ejecutar Terraform

```bash
# Navegar a la carpeta de infraestructura
cd infrastructure

# Inicializar Terraform (descargar providers)
terraform init

# Revisar el plan de ejecución
terraform plan

# Aplicar la configuración (crear recursos)
terraform apply
```

**Nota:** Terraform te pedirá confirmación antes de crear los recursos. Escribe `yes` para continuar.

#### Recursos que se crean:

- **1 VPC** (Virtual Private Cloud) con CIDR `10.0.0.0/16`
- **1 Internet Gateway** para acceso a internet
- **1 Subnet pública** con CIDR `10.0.1.0/24`
- **1 Route Table** configurada
- **1 Security Group** con reglas para:
  - Puerto 80 (HTTP - NGINX)
  - Puerto 22 (SSH)
  - Puerto 8000 (FastAPI - solo interno)
- **1 Key Pair SSH** (generada automáticamente en `id_rsa`)
- **7 Instancias EC2 t3.micro**:
  - 1 Master (NGINX Load Balancer)
  - 6 Slaves (FastAPI + PyTorch)

#### Obtener las IPs generadas

Después de que Terraform termine, verás las IPs en el output:

```bash
# Ver outputs de nuevo
terraform output

# Salida ejemplo:
# master_public_ip = "54.210.156.47"
# slaves_private_ips = [
#   "10.0.1.145",
#   "10.0.1.234",
#   ...
# ]
# slaves_public_ips = [
#   "98.93.52.91",
#   "18.215.157.114",
#   ...
# ]
```

**Guarda estas IPs** - las necesitarás para el siguiente paso.

### 2. Actualizar Variables de Entorno

Edita el archivo `.env` en la raíz del proyecto con las IPs que Terraform generó:

```env
# Master Node
MASTER_IP=<terraform output master_public_ip>

# Slaves Public IPs
SLAVE_PUBLIC_IP_1=<primer IP de slaves_public_ips>
SLAVE_PUBLIC_IP_2=<segunda IP de slaves_public_ips>
# ... y así sucesivamente

# Slaves Private IPs
SLAVE_PRIVATE_IP_1=<primer IP de slaves_private_ips>
SLAVE_PRIVATE_IP_2=<segunda IP de slaves_private_ips>
# ... y así sucesivamente
```

También actualiza el archivo del frontend:

```bash
cd frontend

# Si no existe, copiar desde el ejemplo
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

Editar `frontend/.env` con la IP del Master de Terraform:

```env
VITE_MASTER_IP=<terraform output master_public_ip>
```

### 3. Configurar Clave SSH

Terraform genera automáticamente el archivo `infrastructure/id_rsa`. Verifica los permisos:

```bash
# Linux/Mac
chmod 600 infrastructure/id_rsa

# Windows (en PowerShell como Admin)
icacls infrastructure\id_rsa /inheritance:r
icacls infrastructure\id_rsa /grant:r "$($env:USERNAME):(R)"
```

### 4. Desplegar Aplicación

```bash
cd infrastructure

# Instalar dependencias de Python
pip install -r ../requirements.txt

# Ejecutar script de despliegue
python connector_script.py
```

Este script:
- Se conecta a cada Slave via SSH
- Instala Docker
- Sube el modelo y el código del backend
- Construye y ejecuta contenedores Docker
- Configura NGINX en el Master como load balancer

### 5. Actualizar Frontend

Edita `frontend/.env`:

```env
VITE_MASTER_IP=<tu-master-public-ip>
```

Reinicia el servidor de Vite:

```bash
cd frontend
npm run dev
```

## Destruir Infraestructura

**IMPORTANTE:** Para evitar costos en AWS, destruye los recursos cuando termines:

```bash
cd infrastructure

# Destruir todos los recursos creados
terraform destroy
```

Terraform te pedirá confirmación. Escribe `yes` para eliminar:
- Todas las instancias EC2 (Master + Slaves)
- VPC, Subnets, y configuración de red
- Security Groups
- Key Pairs

**Nota:** El archivo `id_rsa` local NO se eliminará automáticamente. Puedes borrarlo manualmente si lo deseas.

## Estructura del Proyecto

```
Tarea-22/
├── .env                          # Variables de entorno (IPs de AWS)
├── README.md                     # Este archivo
├── requirements.txt              # Dependencias Python
│
├── backend/
│   └── inference_server.py       # API FastAPI para inferencia
│
├── frontend/
│   ├── .env                      # Variables de entorno del frontend
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.vue
│       └── components/
│           └── ImageClassifier.vue  # Componente principal
│
├── infrastructure/
│   ├── main.tf                   # Configuración Terraform
│   ├── connector_script.py       # Script de despliegue automatizado
│   └── id_rsa                    # Clave SSH privada (no incluir en git)
│
└── model/
    ├── cats_vs_dogs_cnn.pth      # Modelo PyTorch entrenado
    ├── training_model.py         # Script de entrenamiento
    └── animals/
        ├── cat/                  # Dataset de gatos
        └── dog/                  # Dataset de perros
```

## roubleshooting

### Terraform: Error de autenticación AWS

**Error:** `Error: No valid credential sources found`

**Solución:**
```bash
# Configurar AWS CLI
aws configure

# O exportar credenciales temporalmente (Linux/Mac)
export AWS_ACCESS_KEY_ID="tu-access-key"
export AWS_SECRET_ACCESS_KEY="tu-secret-key"

# Windows PowerShell
$env:AWS_ACCESS_KEY_ID="tu-access-key"
$env:AWS_SECRET_ACCESS_KEY="tu-secret-key"
```

### Terraform: Error de límites de EC2

**Error:** `Error: Error launching source instance: InstanceLimitExceeded`

**Solución:** Tu cuenta AWS tiene límite de instancias. Puedes:
1. Reducir el número de slaves en `main.tf` (cambiar `count = 6` a un número menor)
2. Solicitar aumento de límite en AWS Support
3. Destruir instancias existentes: `terraform destroy`

### Terraform: Estado bloqueado

**Error:** `Error: Error acquiring the state lock`

**Solución:**
```bash
# Forzar desbloqueo (usar con cuidado)
terraform force-unlock <LOCK_ID>
```

### Frontend no encuentra la IP

**Error:** `POST http://undefined/predict_image net::ERR_NAME_NOT_RESOLVED`

**Solución:**
1. Verifica que el archivo `frontend/.env` existe y contiene `VITE_MASTER_IP`
2. Reinicia el servidor de Vite (las variables de entorno solo se cargan al inicio)
3. Limpia la caché: `rm -rf frontend/node_modules/.vite`

### Error de conexión SSH

**Error:** `Permission denied (publickey)`

**Solución:**
```bash
chmod 600 infrastructure/id_rsa
```

### Docker no arranca en Slaves

**Solución:**
```bash
# Reconectarse a la instancia slave
ssh -i infrastructure/id_rsa ec2-user@<slave-ip>

# Verificar estado de Docker
sudo systemctl status docker

# Reiniciar Docker
sudo systemctl restart docker
```

### NGINX no balancea correctamente

**Solución:**
```bash
# Conectarse al Master
ssh -i infrastructure/id_rsa ec2-user@<master-ip>

# Verificar configuración
sudo nginx -t

# Ver logs
sudo tail -f /var/log/nginx/error.log

# Reiniciar NGINX
sudo systemctl restart nginx
```

## Testing

Para probar el clasificador:
1. Abre la aplicación frontend
2. Selecciona una imagen de un gato o perro
3. Haz clic en "Predecir Imagen"
4. El resultado mostrará "Cat" o "Dog"
