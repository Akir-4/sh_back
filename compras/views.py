from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Subasta, Puja, Transaccion
from tiendas.models import Tienda
from productos.models import Producto
from .serializers import SubastaSerializer, PujaSerializer, TransaccionSerializer
from django_filters.rest_framework import DjangoFilterBackend
from .filters import SubastaFilter  # Importar el filtro
from transbank.webpay.webpay_plus.transaction import Transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.db.models import Count, Sum
from django.utils.timezone import make_aware
from datetime import datetime, timedelta
from django.db import models
from usuario.models import Usuario
from rest_framework.decorators import api_view
from datetime import date
from django.db.models import Sum, Count, Q

class SubastaViewSet(viewsets.ModelViewSet):
    serializer_class = SubastaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = SubastaFilter

    def get_queryset(self):
        # Finalizar subastas que ya han terminado automáticamente
        subastas_vencidas = Subasta.objects.filter(
            fecha_termino__lte=timezone.now(),
            estado='vigente'
        )
        for subasta in subastas_vencidas:
            subasta.finalizar_subasta()

        # Obtener el queryset de subastas incluyendo las vigentes, pendientes y cerradas
        queryset = Subasta.objects.filter(
            estado__in=['vigente', 'pendiente', 'cerrada']
        ).select_related('producto_id__marca_id', 'producto_id__tipo_id', 'tienda_id')

        # Filtrar subasta por producto si se pasa como parámetro
        producto_id = self.request.query_params.get('producto_id', None)
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)

        # Filtrar subasta por tienda si se pasa como parámetro
        tienda_id = self.request.query_params.get('tienda_id', None)
        if tienda_id:
            queryset = queryset.filter(tienda_id=tienda_id)

        # Filtrar subastas que comenzaron o terminarán en un mes específico
        month = self.request.query_params.get('month', None)
        year = self.request.query_params.get('year', None)
        if month and year:
            try:
                month = int(month)
                year = int(year)
                start_date = make_aware(datetime(year, month, 1))
                if month == 12:
                    end_date = make_aware(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
                else:
                    end_date = make_aware(datetime(year, month + 1, 1)) - timedelta(seconds=1)
                queryset = queryset.filter(
                    models.Q(fecha_inicio__gte=start_date, fecha_inicio__lte=end_date) |
                    models.Q(fecha_termino__gte=start_date, fecha_termino__lte=end_date)
                )
            except ValueError:
                queryset = queryset.none()

        return queryset

    def retrieve(self, request, *args, **kwargs):
        # Verificar si la subasta debe cerrarse antes de devolver los detalles
        instance = self.get_object()
        if instance.sub_terminada and instance.estado == 'vigente':
            instance.finalizar_subasta()
        return super().retrieve(request, *args, **kwargs)

    @api_view(["GET"])
    def estadisticas_administrador(request):
        hoy = date.today()

        # Subastas activas hoy
        subastas_activas = Subasta.objects.filter(
            Q(fecha_inicio__lte=hoy) & Q(fecha_termino__gte=hoy)
        ).count()

        # Subastas que terminan hoy
        subastas_terminan_hoy = Subasta.objects.filter(fecha_termino__date=hoy).count()

        # Usuarios registrados hoy
        usuarios_registrados_hoy = Usuario.objects.filter(created_at__date=hoy).count()

        # Subastas sin pujas
        subastas_sin_pujas = Subasta.objects.annotate(
            total_pujas=Count('puja_set')
        ).filter(total_pujas=0).count()

        # Subastas pendientes de pago
        subastas_pendientes_pago = Subasta.objects.filter(estado="pendiente").count()

        data = {
            "subastas_activas": subastas_activas,
            "subastas_terminan_hoy": subastas_terminan_hoy,
            "usuarios_registrados_hoy": usuarios_registrados_hoy,
            "subastas_sin_pujas": subastas_sin_pujas,
            "subastas_pendientes_pago": subastas_pendientes_pago,
        }
        return Response(data)


    @api_view(["GET"])
    def estadisticas_gerente(request):
        hoy = date.today()
        primer_dia_mes = hoy.replace(day=1)

        # Ingresos totales del mes
        ingresos_totales = Subasta.objects.filter(
            estado="cerrada", fecha_termino__gte=primer_dia_mes, fecha_termino__lte=hoy
        ).aggregate(total=Sum('precio_final'))["total"] or 0

        # Usuarios activos este mes
        usuarios_activos = Usuario.objects.filter(
            Q(puja__fecha__gte=primer_dia_mes) | Q(subastas_ganadas__fecha_termino__gte=primer_dia_mes)
        ).distinct().count()

        # Tienda más activa del mes
        tienda_mas_activa = (
            Tienda.objects.annotate(
                total_subastas=Count("subastas", filter=Q(subastas__fecha_termino__gte=primer_dia_mes))
            )
            .order_by("-total_subastas")
            .values("nombre")
            .first()
        )
        tienda_mas_activa_nombre = tienda_mas_activa["nombre"] if tienda_mas_activa else "N/A"

        # Crecimiento mensual de usuarios
        usuarios_mes = Usuario.objects.filter(created_at__gte=primer_dia_mes).count()
        usuarios_mes_anterior = Usuario.objects.filter(
            created_at__gte=primer_dia_mes - timedelta(days=30), created_at__lt=primer_dia_mes
        ).count()

        crecimiento = (
            ((usuarios_mes - usuarios_mes_anterior) / usuarios_mes_anterior) * 100
            if usuarios_mes_anterior > 0
            else 0
        )

        data = {
            "ingresos_totales": ingresos_totales,
            "usuarios_activos": usuarios_activos,
            "tienda_mas_activa": tienda_mas_activa_nombre,
            "crecimiento_usuarios": crecimiento,
        }
        


    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        subasta = self.get_object()
        if subasta.estado != 'vigente':
            return Response({'error': 'Solo se pueden finalizar subastas vigentes'}, status=status.HTTP_400_BAD_REQUEST)

        if subasta.fecha_termino <= timezone.now():
            subasta.finalizar_subasta()
            return Response({'status': 'Subasta finalizada exitosamente'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'La subasta no puede finalizar antes de la fecha y hora de término'}, status=status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        # Obtener el ID del producto del request
        producto_id = request.data.get('producto_id')

        # Verificar si ya existe una subasta vigente para este producto
        if Subasta.objects.filter(producto_id=producto_id, estado='vigente').exists():
            raise ValidationError({'error': 'El producto ya tiene una subasta vigente y no puede ser subastado nuevamente.'})

        # Actualizar el campo `subastado` del producto para marcarlo como subastado
        Producto.objects.filter(producto_id=producto_id).update(subastado=True)

        # Proceder con la creación de la subasta si no hay conflictos
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def iniciar_pago(self, request, pk=None):
        subasta = self.get_object()

        # Verificar si la subasta está en estado pendiente o cerrada
        if subasta.estado not in ['pendiente', 'cerrada']:
            return Response({'error': 'La subasta no está en un estado válido para iniciar el pago.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar si ya existe una transacción pendiente para la puja ganadora
        puja_ganadora = subasta.puja_set.order_by('-monto').first()
        if not puja_ganadora:
            return Response({'error': 'No hay pujas para esta subasta.'}, status=status.HTTP_400_BAD_REQUEST)

        transaccion_pendiente = Transaccion.objects.filter(puja_id=puja_ganadora, estado="pendiente").first()
        if transaccion_pendiente:
            # Aquí podrías decidir reiniciar la transacción si no ha sido completada
            # Por ejemplo, cancelar la transacción anterior o permitir un nuevo intento
            return Response({'error': 'Ya existe una transacción pendiente para esta subasta'}, status=status.HTTP_400_BAD_REQUEST)

        # Proceder con la creación de la transacción si no hay conflictos
        monto = puja_ganadora.monto * 1.10
        buy_order = f"{subasta.subasta_id}-{puja_ganadora.puja_id}"
        session_id = f"session-{subasta.subasta_id}"

        # URL a la cual Transbank redirigirá tras completar el pago
        return_url = 'http://localhost:3000/confirmar-pago/'

        try:
            # Crear una instancia de Transaction
            transaction = Transaction()
            response = transaction.create(
                buy_order=buy_order,
                session_id=session_id,
                amount=monto,
                return_url=return_url
            )

            # Creación de la transacción en la base de datos
            Transaccion.objects.create(
                puja_id=puja_ganadora,
                estado="pendiente",
                fecha=timezone.now(),
                token_ws=response['token'],
                monto=monto
            )

            # Retornar la URL generada por Transbank para redirigir al usuario
            return Response({'url': response['url'] + "?token_ws=" + response['token']}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'Error al iniciar la transacción: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['post'], url_path='confirmar_pago')
    def confirmar_pago(self, request):
        # Obtener el token_ws del cuerpo de la solicitud
        token_ws = request.data.get("token_ws")

        if not token_ws:
            return Response({"error": "Token de pago no recibido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Confirmar la transacción con Transbank usando el token_ws
            response = Transaction().commit(token_ws)

            # Verificar si el pago fue autorizado
            if response['status'] == "AUTHORIZED":
                # Obtener la transacción correspondiente usando el token_ws
                transaccion = Transaccion.objects.get(token_ws=token_ws)
                
                # Cambiar el estado de la transacción a "completado"
                transaccion.estado = "completado"
                transaccion.save()

                # Obtener la subasta asociada a la transacción
                subasta = transaccion.puja_id.subasta_id
                
                # Cambiar el estado de la subasta a "cerrada" si estaba en "pendiente"
                if subasta.estado == "pendiente":
                    subasta.estado = "cerrada"
                    subasta.fecha_termino = timezone.now()  # Puedes actualizar la fecha de término a la actual
                    subasta.save()

                    # Eliminar el producto asociado a la subasta, ya que la transacción fue completada
                    producto = subasta.producto_id
                    producto.delete()

                return Response({"message": "Pago completado con éxito, producto eliminado"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "El pago no fue autorizado"}, status=status.HTTP_400_BAD_REQUEST)
        
        except Transaccion.DoesNotExist:
            return Response({'error': 'Transacción no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error al confirmar el pago: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['get'], url_path='ganadas-usuario/(?P<usuario_id>[^/.]+)')
    def get_subastas_ganadas_por_usuario(self, request, usuario_id):
        # Filtrar las subastas que el usuario ha ganado y están pendientes de pago
        subastas_ganadas = Subasta.objects.filter(puja_set__usuario_id=usuario_id, estado='pendiente').distinct()
        serializer = SubastaSerializer(subastas_ganadas, many=True)
        return Response(serializer.data)

class PujaViewSet(viewsets.ModelViewSet):
    queryset = Puja.objects.all()
    serializer_class = PujaSerializer

    def get_queryset(self):
        queryset = self.queryset
        # Obtenemos el subasta_id de los parámetros de la URL
        subasta_id = self.request.query_params.get('subasta_id', None)
        if subasta_id is not None:
            # Filtramos las pujas por subasta_id
            queryset = queryset.filter(subasta_id=subasta_id)
        return queryset

    @action(detail=False, methods=['get'], url_path='subastas-usuario/(?P<usuario_id>[^/.]+)')
    def get_subastas_por_usuario(self, request, usuario_id):
        # Filtrar las pujas por el usuario
        pujas = Puja.objects.filter(usuario_id=usuario_id)
        # Obtener los IDs de subasta únicos de esas pujas
        subasta_ids = pujas.values_list('subasta_id', flat=True).distinct()
        # Obtener las subastas únicas
        subastas = Subasta.objects.filter(subasta_id__in=subasta_ids)
        # Serializar las subastas
        serializer = SubastaSerializer(subastas, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        subasta_id = request.data.get('subasta_id')
        subasta = Subasta.objects.get(pk=subasta_id)

        # Verificar que la subasta esté activa y no haya terminado
        if subasta.sub_terminada:
            return Response({'error': 'No se pueden hacer pujas en una subasta que ha finalizado.'}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

class TransaccionViewSet(viewsets.ModelViewSet):
    queryset = Transaccion.objects.all()
    serializer_class = TransaccionSerializer

# Modificación en el modelo Subasta para finalizar incluso si no hay pujas
def finalizar_subasta(self):
    """Finaliza la subasta actualizando el estado y el precio final."""
    puja_ganadora = self.puja_set.order_by('-monto').first()
    if puja_ganadora:
        # El precio final es el precio inicial más el monto de la puja ganadora
        self.precio_final = (self.precio_inicial or 0) + puja_ganadora.monto
        self.estado = "pendiente"  # Cambiar estado a "pendiente" si hay pujas
    else:
        # Si no hay pujas, establecer el precio final como el precio inicial
        self.precio_final = self.precio_inicial or 0
        self.estado = "cerrada"  # Cambiar estado a "cerrada" si no hubo pujas
    self.save()