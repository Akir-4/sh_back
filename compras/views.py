from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Subasta, Puja, Transaccion
from tiendas.models import Tienda
from productos.models import Producto
from .serializers import SubastaSerializer, PujaSerializer, TransaccionSerializer
from django_filters.rest_framework import DjangoFilterBackend
from .filters import SubastaFilter
from transbank.webpay.webpay_plus.transaction import Transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.db.models import Count, Sum, Q
from django.utils.timezone import make_aware
from datetime import datetime, timedelta
from django.db import models
from usuario.models import Usuario


class SubastaViewSet(viewsets.ModelViewSet):
    serializer_class = SubastaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = SubastaFilter

    def get_queryset(self):
        # Finalizar subastas vencidas en una única consulta
        Subasta.objects.filter(
            fecha_termino__lte=timezone.now(),
            estado='vigente'
        ).update(estado='cerrada')

        # Obtener queryset optimizado
        queryset = Subasta.objects.filter(
            estado__in=['vigente', 'pendiente', 'cerrada']
        ).select_related(
            'producto_id__marca_id', 'producto_id__tipo_id', 'tienda_id'
        )

        # Filtrar subasta por parámetros opcionales
        producto_id = self.request.query_params.get('producto_id')
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)

        tienda_id = self.request.query_params.get('tienda_id')
        if tienda_id:
            queryset = queryset.filter(tienda_id=tienda_id)

        # Filtrar por mes y año
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        if month and year:
            try:
                month = int(month)
                year = int(year)
                start_date = make_aware(datetime(year, month, 1))
                end_date = make_aware(datetime(year + (month // 12), (month % 12) + 1, 1)) - timedelta(seconds=1)
                queryset = queryset.filter(
                    Q(fecha_inicio__gte=start_date, fecha_inicio__lte=end_date) |
                    Q(fecha_termino__gte=start_date, fecha_termino__lte=end_date)
                )
            except ValueError:
                queryset = queryset.none()

        return queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.estado == 'vigente' and instance.sub_terminada:
            instance.finalizar_subasta()
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='estadisticas')
    def get_estadisticas(self, request):
        month = request.query_params.get("month", timezone.now().month)
        year = request.query_params.get("year", timezone.now().year)

        try:
            month = int(month)
            year = int(year)
            inicio_mes = make_aware(datetime(year, month, 1))
            fin_mes = make_aware(datetime(year + (month // 12), (month % 12) + 1, 1)) - timedelta(seconds=1)
        except ValueError:
            return Response({"error": "Parámetros inválidos."}, status=status.HTTP_400_BAD_REQUEST)

        subastas_hoy = Subasta.objects.filter(fecha_inicio__date=timezone.now().date()).count()
        subastas_terminan_hoy = Subasta.objects.filter(fecha_termino__date=timezone.now().date()).count()
        subastas_mes = Subasta.objects.filter(
            fecha_inicio__gte=inicio_mes, fecha_inicio__lte=fin_mes, estado="vigente"
        ).count()

        tienda_mas_subastas = (
            Subasta.objects.filter(fecha_inicio__gte=inicio_mes, fecha_inicio__lte=fin_mes)
            .values("tienda_id__nombre_legal")
            .annotate(total_subastas=Count("subasta_id"))
            .order_by("-total_subastas")
            .first()
        )
        ingresos_totales = Subasta.objects.filter(
            estado="cerrada", fecha_termino__gte=inicio_mes, fecha_termino__lte=fin_mes
        ).aggregate(ingresos=Sum("precio_final"))["ingresos"] or 0

        usuarios_registrados = Usuario.objects.filter(
            created_at__gte=inicio_mes, created_at__lte=fin_mes
        ).count()

        usuario_mas_pujas = (
            Puja.objects.filter(fecha__gte=inicio_mes, fecha__lte=fin_mes)
            .values("usuario_id__nombre")
            .annotate(total_pujas=Count("puja_id"))
            .order_by("-total_pujas")
            .first()
        )
        usuario_mas_ganadas = (
            Puja.objects.filter(
                subasta_id__fecha_termino__gte=inicio_mes,
                subasta_id__fecha_termino__lte=fin_mes,
                subasta_id__estado="cerrada"
            )
            .values("usuario_id__nombre")
            .annotate(total_ganadas=Count("puja_id"))
            .order_by("-total_ganadas")
            .first()
        )

        response = {
            "subastas_hoy": subastas_hoy,
            "subastas_terminan_hoy": subastas_terminan_hoy,
            "subastas_mes": subastas_mes,
            "tienda_mas_subastas": tienda_mas_subastas.get("tienda_id__nombre_legal") if tienda_mas_subastas else "N/A",
            "ingresos_totales": ingresos_totales,
            "usuarios_registrados": usuarios_registrados,
            "usuario_mas_pujas": usuario_mas_pujas.get("usuario_id__nombre") if usuario_mas_pujas else "N/A",
            "usuario_mas_ganadas": usuario_mas_ganadas.get("usuario_id__nombre") if usuario_mas_ganadas else "N/A",
        }
        return Response(response)

    def create(self, request, *args, **kwargs):
        producto_id = request.data.get('producto_id')
        if Subasta.objects.filter(producto_id=producto_id, estado='vigente').exists():
            raise ValidationError({'error': 'El producto ya tiene una subasta vigente.'})
        Producto.objects.filter(producto_id=producto_id).update(subastado=True)
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def iniciar_pago(self, request, pk=None):
        subasta = self.get_object()
        if subasta.estado not in ['pendiente', 'cerrada']:
            return Response({'error': 'Estado inválido para el pago.'}, status=status.HTTP_400_BAD_REQUEST)
        puja_ganadora = subasta.puja_set.order_by('-monto').first()
        if not puja_ganadora:
            return Response({'error': 'No hay pujas para esta subasta.'}, status=status.HTTP_400_BAD_REQUEST)
        transaccion_pendiente = Transaccion.objects.filter(puja_id=puja_ganadora, estado="pendiente").first()
        if transaccion_pendiente:
            return Response({'error': 'Ya existe una transacción pendiente.'}, status=status.HTTP_400_BAD_REQUEST)
        monto = puja_ganadora.monto * 1.10
        try:
            transaction = Transaction()
            response = transaction.create(
                buy_order=f"{subasta.subasta_id}-{puja_ganadora.puja_id}",
                session_id=f"session-{subasta.subasta_id}",
                amount=monto,
                return_url='http://localhost:3000/confirmar-pago/'
            )
            Transaccion.objects.create(
                puja_id=puja_ganadora,
                estado="pendiente",
                fecha=timezone.now(),
                token_ws=response['token'],
                monto=monto
            )
            return Response({'url': response['url'] + "?token_ws=" + response['token']}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@action(detail=False, methods=['post'], url_path='confirmar_pago')
def confirmar_pago(self, request):
    token_ws = request.data.get("token_ws")
    if not token_ws:
        return Response({"error": "Token de pago no recibido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Confirmar la transacción con Transbank usando el token_ws
        response = Transaction().commit(token_ws)

        if response['status'] == "AUTHORIZED":
            # Obtener la transacción correspondiente
            transaccion = Transaccion.objects.select_related('puja_id__subasta_id').get(token_ws=token_ws)

            # Actualizar la transacción a completada
            transaccion.estado = "completado"
            transaccion.save()

            # Actualizar el estado de la subasta si estaba pendiente
            subasta = transaccion.puja_id.subasta_id
            if subasta.estado == "pendiente":
                subasta.estado = "cerrada"
                subasta.fecha_termino = timezone.now()  # Registrar la fecha de cierre
                subasta.save()

            return Response({"message": "Pago completado con éxito"}, status=status.HTTP_200_OK)

        return Response({"error": "El pago no fue autorizado"}, status=status.HTTP_400_BAD_REQUEST)

    except Transaccion.DoesNotExist:
        return Response({'error': 'Transacción no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error al confirmar el pago: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@action(detail=False, methods=['get'], url_path='ganadas-usuario/(?P<usuario_id>[^/.]+)')
def get_subastas_ganadas_por_usuario(self, request, usuario_id):
    # Obtener subastas ganadas y pendientes por usuario
    subastas_ganadas = Subasta.objects.filter(
        puja_set__usuario_id=usuario_id, estado='pendiente'
    ).distinct().select_related('producto_id', 'tienda_id')

    serializer = SubastaSerializer(subastas_ganadas, many=True)
    return Response(serializer.data)


class PujaViewSet(viewsets.ModelViewSet):
    queryset = Puja.objects.select_related('subasta_id', 'usuario_id')
    serializer_class = PujaSerializer

    def get_queryset(self):
        subasta_id = self.request.query_params.get('subasta_id')
        if subasta_id:
            return self.queryset.filter(subasta_id=subasta_id)
        return self.queryset

    @action(detail=False, methods=['get'], url_path='subastas-usuario/(?P<usuario_id>[^/.]+)')
    def get_subastas_por_usuario(self, request, usuario_id):
        # Filtrar las subastas en las que el usuario ha participado
        pujas = Puja.objects.filter(usuario_id=usuario_id).select_related('subasta_id')
        subasta_ids = pujas.values_list('subasta_id', flat=True).distinct()
        subastas = Subasta.objects.filter(subasta_id__in=subasta_ids).select_related('producto_id', 'tienda_id')

        serializer = SubastaSerializer(subastas, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        subasta_id = request.data.get('subasta_id')
        subasta = Subasta.objects.get(pk=subasta_id)

        if subasta.sub_terminada:
            return Response({'error': 'No se pueden hacer pujas en una subasta que ha finalizado.'}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)


class TransaccionViewSet(viewsets.ModelViewSet):
    queryset = Transaccion.objects.select_related('puja_id__subasta_id')
    serializer_class = TransaccionSerializer


# Método para finalizar subastas
def finalizar_subasta(self):
    puja_ganadora = self.puja_set.order_by('-monto').first()

    if puja_ganadora:
        self.precio_final = (self.precio_inicial or 0) + puja_ganadora.monto
        self.estado = "pendiente"
    else:
        self.precio_final = self.precio_inicial or 0
        self.estado = "cerrada"

    self.save()
