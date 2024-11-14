from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ProductoViewSet, MarcaViewSet, Tipo_PrendaViewSet, ProductoDetailView, ProductoConPujasView

router = DefaultRouter()
router.register(r'productos', ProductoViewSet)
router.register(r'marcas', MarcaViewSet)
router.register(r'tipos_prenda', Tipo_PrendaViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('producto/<slug:slug>/', ProductoDetailView.as_view(), name='producto-detail'),
    path('producto/<int:producto_id>/detalles_pujas/', ProductoConPujasView.as_view(), name='producto-con-pujas'),
]

