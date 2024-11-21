import logging
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Usuario  # Asegúrate de que el modelo File esté importado
from .serializers import UsuarioSerializer
from .utils import upload_image_to_blob  # Importa la función para subir imágenes

# Configurar logging
logger = logging.getLogger(__name__)

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

    def perform_create(self, serializer):
        # Llama a la función para manejar la subida de la imagen
        imagen = self.request.FILES.get('imagen')
        if imagen:
            logger.info("Subiendo imagen para el nuevo usuario.")
            file_object = upload_image_to_blob(imagen)
            if file_object:
                logger.info("Imagen subida con éxito. URL: %s", file_object['file_url'])
                # Guarda la URL de la imagen en el modelo
                serializer.save(imagen=file_object['file_url'])
            else:
                logger.error("Fallo en la subida de la imagen.")
                return Response({"error": "Failed to upload image"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            logger.warning("No se proporcionó imagen, guardando usuario sin imagen.")
            serializer.save()  # Si no hay imagen, guarda el usuario sin la imagen

@api_view(['POST'])
def upload_image(request):
    if request.method == 'POST':
        if 'image' not in request.FILES:
            logger.error("No se proporcionó imagen en la solicitud.")
            return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES['image']
        logger.info("Subiendo imagen desde la solicitud de upload_image.")
        file_object = upload_image_to_blob(image_file)

        if file_object:
            logger.info("Imagen subida con éxito. URL: %s", file_object['file_url'])
            return Response({"file_url": file_object['file_url']}, status=status.HTTP_201_CREATED)
        else:
            logger.error("Fallo en la subida de la imagen desde upload_image.")
            return Response({"error": "Failed to upload image"}, status=status.HTTP_400_BAD_REQUEST)
