from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Comentarios
from .serializers import ComentariosSerializer

class ComentariosView(APIView):
    def get(self, request):
        comentarios = Comentarios.objects.all()  # Obtiene todos los comentarios
        serializer = ComentariosSerializer(comentarios, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ComentariosSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Gracias por tu comunicación. La hemos recibido.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
