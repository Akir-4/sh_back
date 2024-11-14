from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from usuario.models import Usuario

class LoginView(APIView):
    def post(self, request):
        usuario = request.query_params.get('usuario')
        contrasena = request.query_params.get('contrasena')
                
        try:
            user = Usuario.objects.get(usuario=usuario)
                        
            # Compara la contraseña en texto plano
            if user.contrasena == contrasena:
                # Crear el token JWT manualmente usando usuario_id
                refresh = RefreshToken()
                refresh['user_id'] = user.usuario_id  # Establecemos usuario_id en lugar de id

                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'rol': user.rol  # Añadir el rol del usuario
                })
            else:
                return Response({"error": "Contraseña incorrecta"}, status=401)
        except Usuario.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=404)
