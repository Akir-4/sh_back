from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import SubastaViewSet, PujaViewSet, TransaccionViewSet

router = DefaultRouter()
router.register(r'subastas', SubastaViewSet, basename='subasta')
router.register(r'pujas', PujaViewSet, basename='puja')
router.register(r'transacciones', TransaccionViewSet, basename='transaccion')

urlpatterns = [
    path('', include(router.urls)),
    
    path('pujas/subastas-usuario/<int:usuario_id>/', PujaViewSet.as_view({'get': 'get_subastas_por_usuario'}), name='subastas-usuario')
]