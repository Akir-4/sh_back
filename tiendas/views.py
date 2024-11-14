from rest_framework import generics, viewsets, status
from .models import Tienda, Bodega
from .serializers import TiendaSerializer, BodegaSerializer
from compras.serializers import SubastaSerializer
from compras.models import Subasta
from rest_framework.response import Response

class TiendaListCreateView(generics.ListCreateAPIView):
    queryset = Tienda.objects.all()
    serializer_class = TiendaSerializer

class TiendaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tienda.objects.all()
    serializer_class = TiendaSerializer

class BodegaViewSet(viewsets.ModelViewSet):
    queryset = Bodega.objects.all()
    serializer_class = BodegaSerializer

class BodegaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Bodega.objects.all()
    serializer_class = BodegaSerializer

class BodegaListCreateView(generics.ListCreateAPIView):
    queryset = Bodega.objects.all()
    serializer_class = BodegaSerializer

class SubastasPorTiendaView(generics.ListAPIView):
    serializer_class = SubastaSerializer

    def get_queryset(self):
        tienda_id = self.kwargs['tienda_id']
        try:
            tienda = Tienda.objects.get(pk=tienda_id)
            # Cambiamos a tienda_id ya que es el nombre correcto del campo en Subasta
            return Subasta.objects.filter(tienda_id=tienda)
        except Tienda.DoesNotExist:
            return None

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if queryset is None:
            return Response({"detail": "Tienda no encontrada"}, status=status.HTTP_404_NOT_FOUND)
        return super().list(request, *args, **kwargs)


class BodegaPorTiendaView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener la bodega filtrada por tienda_id
    """
    
    def get(self, request, tienda_id, *args, **kwargs):
        # Filtrar las bodegas por tienda_id
        bodegas = Bodega.objects.filter(tienda_id=tienda_id)

        if bodegas.exists():
            # Serializar y devolver los resultados
            serializer = BodegaSerializer(bodegas, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Si no se encuentran bodegas
            return Response({"detail": "No se encontraron bodegas para esta tienda."}, status=status.HTTP_404_NOT_FOUND)