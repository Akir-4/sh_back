from io import BytesIO
import uuid
from pathlib import Path
from azure.storage.blob import BlobServiceClient
import logging
from django.conf import settings

# Configuración del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Extensiones permitidas para imágenes
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']

def create_blob_client():
    # Crear el BlobServiceClient usando las credenciales de configuración
    blob_service_client = BlobServiceClient(
        account_url=f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net",
        credential=settings.AZURE_ACCOUNT_KEY
    )
    # Obtener referencia al contenedor donde se almacenarán las imágenes
    container_client = blob_service_client.get_container_client(settings.AZURE_CONTAINER)
    
    return container_client

def check_file_ext(path):
    # Verificar si la extensión del archivo está permitida
    ext = Path(path).suffix
    return ext in ALLOWED_EXTENSIONS

def upload_image_to_blob(file):
    if not check_file_ext(file.name):
        logger.error("Tipo de archivo no permitido.")
        return None  # Retorna None si el tipo de archivo no es permitido

    file_prefix = uuid.uuid4().hex  # Crear un nombre único para la imagen
    ext = Path(file.name).suffix  # Obtener la extensión del archivo
    file_name = f"{file_prefix}{ext}"  # Generar el nombre del archivo
    file_content = file.read()  # Leer el contenido del archivo
    file_io = BytesIO(file_content)  # Convertir a formato de BytesIO

    try:
        # Obtener el cliente del contenedor
        container_client = create_blob_client()

        # Subir la imagen al contenedor
        blob_client = container_client.get_blob_client(file_name)
        blob_client.upload_blob(data=file_io)
        
        logger.info(f"Imagen subida con éxito: {file_name}")
        
        # Retornar la URL del archivo subido
        return {"file_url": f"https://{settings.AZURE_ACCOUNT_NAME}.blob.core.windows.net/{settings.AZURE_CONTAINER}/{file_name}"}
    except Exception as e:
        logger.error(f"Error al subir la imagen: {e}")  # Añadir logging aquí
        return None
