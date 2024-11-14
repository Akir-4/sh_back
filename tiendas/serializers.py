from rest_framework import serializers
from .models import Tienda, Bodega

class TiendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tienda
        fields = '__all__'
        ref_name = 'TiendaTiendaSerializer'  # Nombre único para este serializer
    
    nombre_legal = serializers.CharField(required=False)
    rut = serializers.CharField(required=False)
    password = serializers.CharField(required=False)
    direccion_fisica = serializers.CharField(required=False)
    telefono_principal = serializers.CharField(required=False)


class BodegaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bodega
        fields = '__all__'