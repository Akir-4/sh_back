from rest_framework import serializers
from .models import Producto, Tipo_Prenda, Marca
from tiendas.models import Tienda

class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = ['marca_id', 'marca']

class Tipo_PrendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tipo_Prenda
        fields = ['tipo', 'tipo_id']

class TiendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tienda
        fields = ['nombre_legal', 'tienda_id']
        ref_name = 'ProductoTiendaSerializer'  # Nombre único para este serializer

class ProductoSerializer(serializers.ModelSerializer):
    marca = MarcaSerializer(read_only=True, source='marca_id')  # Solo para leer los detalles completos de Marca
    tipo_prenda = Tipo_PrendaSerializer(read_only=True, source='tipo_id')  # Solo para leer los detalles completos de Tipo Prenda
    tienda = TiendaSerializer(read_only=True, source='tienda_id')  # Solo para leer los detalles completos de Tienda

    # Campos para aceptar entradas al crear el producto
    marca_id = serializers.PrimaryKeyRelatedField(queryset=Marca.objects.all(), write_only=True)
    tipo_id = serializers.PrimaryKeyRelatedField(queryset=Tipo_Prenda.objects.all(), write_only=True)
    tienda_id = serializers.PrimaryKeyRelatedField(queryset=Tienda.objects.all(), write_only=True)

    class Meta:
        model = Producto
        fields = [
            'producto_id',
            'nombre',
            'marca',  # Detalles completos de la marca
            'tipo_prenda',  # Detalles completos de tipo prenda
            'tienda',  # Detalles completos de la tienda
            'marca_id',  # Campo para aceptar marca_id al crear
            'tipo_id',  # Campo para aceptar tipo_id al crear
            'tienda_id',  # Campo para aceptar tienda_id al crear
            'estado',
            'tamano',
            'imagen_1',
            'imagen_2',
            'imagen_3',
            'imagen_4',
            'slug',
            'descripcion'
        ]

    def validate_tamano(self, value):
        # Verificar si la talla proporcionada es válida
        valid_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL']
        if value not in valid_sizes:
            raise serializers.ValidationError(f"Tamaño '{value}' no es válido. Seleccione una talla válida.")
        return value

    def create(self, validated_data):
        # Aquí extraemos los campos relacionales como IDs
        marca_id = validated_data.pop('marca_id')
        tipo_id = validated_data.pop('tipo_id')
        tienda_id = validated_data.pop('tienda_id')

        # Creamos el objeto Producto usando los IDs correctos
        producto = Producto.objects.create(
            marca_id=marca_id,  # Pasamos el ID de Marca
            tipo_id=tipo_id,  # Pasamos el ID de Tipo Prenda
            tienda_id=tienda_id,  # Pasamos el ID de Tienda
            **validated_data  # Pasamos los demás datos restantes
        )

        return producto
