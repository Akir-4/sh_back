from django.urls import path
from .views import TiendaListCreateView, TiendaDetailView, BodegaListCreateView, BodegaDetailView, SubastasPorTiendaView,BodegaPorTiendaView
from productos.views import CrearProductoYAsignarABodegaView

urlpatterns = [
    path('tiendas/', TiendaListCreateView.as_view(), name='tiendas-list'),
    path('tiendas/<int:pk>/', TiendaDetailView.as_view(), name='tienda-detail'),
    path('bodegas/', BodegaListCreateView.as_view(), name='bodegas-list'),  
    path('bodegas/<int:tienda_id>/', BodegaPorTiendaView.as_view(), name='bodegas-por-tienda'),
    path('tiendas/<int:tienda_id>/subastas/', SubastasPorTiendaView.as_view(), name='subastas-por-tienda'),
    path('tiendas/<int:tienda_id>/productos/', CrearProductoYAsignarABodegaView.as_view(), name='crear-producto-bodega'),# Endpoint para crear un producto y asignarlo a la bodega de la tienda
]
