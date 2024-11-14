from rest_framework import viewsets, status
from .models import Producto, Tipo_Prenda, Marca
from tiendas.models import Tienda
from compras.models import Puja, Subasta
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from django.db.models import Prefetch
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .serializers import ProductoSerializer, Tipo_PrendaSerializer, MarcaSerializer
from compras.serializers import PujaSerializer
from rest_framework.filters import OrderingFilter
from tiendas.models import Bodega


class ProductoConPujasView(generics.RetrieveAPIView):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer

    def get(self, request, *args, **kwargs):
        # Obtener el producto por su ID
        producto_id = self.kwargs['producto_id']
        producto = get_object_or_404(
            Producto.objects.prefetch_related(
                Prefetch('subasta_set__puja_set', queryset=Puja.objects.all())
            ),
            pk=producto_id
        )

        # Serializar el producto
        producto_data = ProductoSerializer(producto).data

        # También puedes devolver datos de las pujas si es necesario
        subastas = producto.subasta_set.all()
        pujas = [PujaSerializer(puja).data for subasta in subastas for puja in subasta.puja_set.all()]

        # Devolver una respuesta combinada
        return Response({
            'producto': producto_data,
            'pujas': pujas,
        })


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related('marca_id', 'tipo_id', 'tienda_id').all()
    serializer_class = ProductoSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['tienda_id', 'marca_id', 'estado', 'tamano', 'tipo_id']
    ordering_fields = ['nombre']  # Cambié a 'nombre', ya que 'precio_inicial' no está en Producto
    ordering = ['nombre']  # Ordenar por defecto por nombre ascendente

    # listar producto por nombre
    def get_queryset(self):
        queryset = Producto.objects.all()
        nombre = self.request.query_params.get('nombre', None)
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)  # Usa 'icontains' para coincidencias parciales e insensibles a mayúsculas
        return queryset


# buscar solo por el slug del producto   
class ProductoDetailView(generics.RetrieveAPIView):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    lookup_field = 'slug'  # Indica que usaremos el campo 'slug' para buscar el producto


class MarcaViewSet(viewsets.ModelViewSet):
    queryset = Marca.objects.all()
    serializer_class = MarcaSerializer


class Tipo_PrendaViewSet(viewsets.ModelViewSet):
    queryset = Tipo_Prenda.objects.all()
    serializer_class = Tipo_PrendaSerializer


class ProductoListView(generics.ListAPIView):
    serializer_class = ProductoSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['tipo_id', 'estado', 'marca_id']
    ordering_fields = ['nombre']  # Cambié a 'nombre', ya que 'precio_inicial' no está en Producto

    def get_queryset(self):
        queryset = Producto.objects.all()

        # Filtrar por tipo de prenda, estado, y marca si están presentes en la consulta
        tipo = self.request.query_params.get('tipo_id', None)
        estado = self.request.query_params.get('estado', None)
        marca = self.request.query_params.get('marca', None)

        if tipo:
            queryset = queryset.filter(tipo_id=tipo)

        if estado:
            queryset = queryset.filter(estado=estado)

        if marca:
            queryset = queryset.filter(marca_id=marca)

        # Ordenar por nombre, ya que precio_inicial no existe en Producto
        ordering = self.request.query_params.get('ordering', 'nombre')
        if ordering == 'nombre':
            queryset = queryset.order_by('nombre')
        elif ordering == '-nombre':
            queryset = queryset.order_by('-nombre')

        return queryset


class CrearProductoYAsignarABodegaView(generics.CreateAPIView):
    serializer_class = ProductoSerializer

    def create(self, request, *args, **kwargs):
        tienda_id = kwargs.get('tienda_id')  # Obtenemos el ID de la tienda desde la URL o los argumentos.
        try:
            # Verificamos si la tienda existe
            tienda = Tienda.objects.get(pk=tienda_id)
        except Tienda.DoesNotExist:
            return Response({"detail": "Tienda no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        
        # Guardamos el producto usando el serializer
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        producto = serializer.save()

        # Ahora, creamos la instancia de Bodega asociada al producto y la tienda
        Bodega.objects.create(tienda_id=tienda, producto_id=producto)  # Pasar los objetos completos, no los IDs

        # Devolvemos la respuesta con los datos del producto y la bodega creada
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
