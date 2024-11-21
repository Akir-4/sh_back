import logging
from datetime import datetime
from django.utils.timezone import make_aware
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Usuario  # Asegúrate de que el modelo Usuario esté importado
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

    @action(detail=False, methods=['get'], url_path='usuarios-registrados-hoy')
    def get_usuarios_registrados_hoy(self, request):
        """
        Endpoint para obtener los usuarios registrados el día de hoy.
        """
        try:
            # Obtener la fecha de hoy con timezone awareness
            hoy = make_aware(datetime.now())
            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Filtrar los usuarios registrados hoy
            usuarios_hoy = Usuario.objects.filter(created_at__gte=inicio_dia, created_at__lte=fin_dia)

            # Serializar los datos
            serializer = UsuarioSerializer(usuarios_hoy, many=True)
            logger.info("Usuarios registrados hoy cargados exitosamente.")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error al cargar los usuarios registrados hoy: {str(e)}")
            return Response({"error": f"Error al cargar los usuarios registrados hoy: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
