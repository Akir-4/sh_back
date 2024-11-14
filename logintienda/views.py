from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from tiendas.models import Tienda

class LoginTiendaView(APIView):
    def post(self, request):
        nombre_legal = request.data.get('nombre_legal')
        password = request.data.get('password')
        
        try:
            # Buscamos la tienda por nombre legal
            tienda = Tienda.objects.get(nombre_legal=nombre_legal)
            
            if tienda.password == password:  # Nota: Para mayor seguridad, utiliza hashing en la contraseña
                # Crear el token JWT usando tienda_id
                refresh = RefreshToken()
                refresh['tienda_id'] = tienda.tienda_id  # Guardamos el tienda_id en el token

                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                })
            else:
                return Response({"error": "Contraseña incorrecta"}, status=401)
        except Tienda.DoesNotExist:
            return Response({"error": "Tienda no encontrada"}, status=404)
