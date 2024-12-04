import boto3
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import os

# Configuración de AWS
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'us-east-2' # Cambia esto si tu región es diferente

# Configurar boto3
s3_client = boto3.client('s3', region_name=AWS_S3_REGION_NAME,
                         aws_access_key_id=AWS_ACCESS_KEY_ID,
                         aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

@api_view(['POST'])
def generate_presigned_url(request):
    """
    Genera una URL prefirmada para cargar archivos a S3.
    Acepta el tipo de archivo y genera la URL prefirmada.
    """
    file_type = request.data.get('file_type') # Producto, perfil, etc.
    file_name = request.data.get('file_name') # Nombre único para el archivo

    if not file_type or not file_name:
        return Response({"error": "file_type and file_name are required"}, status=status.HTTP_400_BAD_REQUEST)

    # Configurar la ruta dependiendo del tipo de archivo
    if file_type == "producto":
        file_path = f"productos/fotos/{file_name}" # Ejemplo: productos/fotos/nombre_imagen.jpg
    elif file_type == "perfil":
        file_path = f"usuarios/perfiles/{file_name}" # Ejemplo: usuarios/perfiles/foto_perfil.jpg
    else:
        return Response({"error": "Invalid file type"}, status=status.HTTP_400_BAD_REQUEST)

    # Generar la URL prefirmada para subir el archivo a S3
    try:
        # Generar la URL prefirmada para PUT (subir archivo)
        url = s3_client.generate_presigned_url('put_object',
                                               Params={'Bucket': AWS_S3_BUCKET_NAME, 'Key': file_path},
                                               ExpiresIn=3600) # Expira en 1 hora (ajustable)
        return Response({"url": url, "file_path": file_path}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)