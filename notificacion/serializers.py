from rest_framework import serializers
from .models import Notificacion

class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ['id', 'tipo', 'usuario', 'mensaje', 'fecha_creacion', 'leida']
        read_only_fields = ['fecha_creacion']  # Para que la fecha de creación sea solo de lectura
