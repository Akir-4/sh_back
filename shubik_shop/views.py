import boto3
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import os

# Configuración de AWS
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'us-east-2'  # Cambia esto si tu región es diferente

# Configurar boto3
s3_client = boto3.client('s3', region_name=AWS_S3_REGION_NAME,
                         aws_access_key_id=AWS_ACCESS_KEY_ID,
                         aws_secret_access_key=AWS_SECRET_ACCESS_KEY)


@api_view(['POST'])
def generate_presigned_url(request):
    """Genera una URL prefirmada para subir imágenes a S3"""
    file_name = request.data.get('file_name')
    content_type = request.data.get('content_type', 'image/jpeg')  # Puedes pasar el tipo de contenido necesario

    if not file_name:
        return Response({"error": "El nombre del archivo es requerido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Genera la URL prefirmada para cargar la imagen en S3
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': AWS_S3_BUCKET_NAME, 'Key': file_name, 'ContentType': content_type},
            ExpiresIn=3600  # La URL es válida por 1 hora
        )
        return Response({"url": url, "file_name": file_name}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)