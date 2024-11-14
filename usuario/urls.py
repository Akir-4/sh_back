from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import UsuarioViewSet, upload_image  # Asegúrate de importar la nueva vista

# Registrar el ViewSet usando DefaultRouter
router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)

# Incluir las rutas generadas por el router
urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', upload_image, name='upload_image'),  # Agregar la ruta para subir imágenes
]
