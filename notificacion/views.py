from rest_framework import generics, status
from rest_framework.response import Response
from .models import Notificacion
from .serializers import NotificacionSerializer

# Vista para listar y crear notificaciones
class NotificacionListCreateView(generics.ListCreateAPIView):
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        # Filtra las notificaciones por el usuario en la URL
        usuario_id = self.kwargs.get('usuario_id')
        return Notificacion.objects.filter(usuario_id=usuario_id).order_by('-fecha_creacion')

# Vista para obtener, actualizar o eliminar una notificación
class NotificacionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer

    def update(self, request, *args, **kwargs):
        # Permite marcar la notificación como leída
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = {'leida': True}  # Marca la notificación como leída
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
