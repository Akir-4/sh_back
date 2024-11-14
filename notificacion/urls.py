from django.urls import path
from .views import NotificacionListCreateView, NotificacionDetailView

urlpatterns = [
    # Listar todas las notificaciones de un usuario y permitir crear nuevas
    path('usuarios/<int:usuario_id>/notificaciones/', NotificacionListCreateView.as_view(), name='notificacion-list-create'),

    # Obtener, actualizar o eliminar una notificación específica
    path('notificaciones/<int:pk>/', NotificacionDetailView.as_view(), name='notificacion-detail'),
]
