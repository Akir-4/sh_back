from rest_framework import serializers
from .models import Usuario

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['usuario_id', 'nombre', 'usuario', 'contrasena', 'email', 'direccion', 'telefono', 'imagen', 'rol','region','comuna']
        extra_kwargs = {
            'contrasena': {'write_only': True} # Para que la contraseña solo se pueda escribir, no leer
        }

    def create(self, validated_data):
        # Elimina el uso de make_password, guarda la contraseña tal cual
        return super(UsuarioSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        # Elimina el uso de make_password al actualizar los datos
        return super(UsuarioSerializer, self).update(instance, validated_data)
