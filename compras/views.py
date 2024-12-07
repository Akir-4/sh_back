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
from django.db.models import Count, Sum, Avg, Q, Max
from django.utils.timezone import make_aware
from datetime import datetime, timedelta
from django.db import models
from usuario.models import Usuario
from tiendas.models import Tienda 
from rest_framework.decorators import api_view
from datetime import date
from usuario.serializers import UsuarioSerializer
from tiendas.serializers import TiendaSerializer 

class SubastaViewSet(viewsets.ModelViewSet):
    serializer_class = SubastaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = SubastaFilter

    def get_queryset(self):
        """Obtener las subastas y finalizar las vencidas automáticamente."""
        subastas_vencidas = Subasta.objects.filter(
            fecha_termino__lte=timezone.now(),
            estado='vigente'
        )
        for subasta in subastas_vencidas:
            subasta.finalizar_subasta()

        return Subasta.objects.filter(
            estado__in=['vigente', 'pendiente', 'cerrada']
        ).select_related('producto_id', 'tienda_id')

    def create(self, request, *args, **kwargs):
        """Crear una nueva subasta y marcar el producto como subastado."""
        producto_id = request.data.get('producto_id')

        # Verificar si el producto ya tiene una subasta vigente
        if Subasta.objects.filter(producto_id=producto_id, estado='vigente').exists():
            raise ValidationError({'error': 'El producto ya tiene una subasta vigente.'})

        # Actualizar el campo `subastado` del producto
        Producto.objects.filter(pk=producto_id).update(subastado=True)

        # Crear la subasta
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Finalizar una subasta específica."""
        subasta = self.get_object()

        if subasta.estado != 'vigente':
            return Response({'error': 'Solo se pueden finalizar subastas vigentes.'}, status=status.HTTP_400_BAD_REQUEST)

        if subasta.fecha_termino <= timezone.now():
            subasta.finalizar_subasta()
            return Response({'status': 'Subasta finalizada exitosamente.'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'La subasta no puede finalizar antes de la fecha de término.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def iniciar_pago(self, request, pk=None):
        """Iniciar el proceso de pago para la subasta."""
        subasta = self.get_object()

        if subasta.estado not in ['pendiente']:
            return Response({'error': 'La subasta no está en un estado válido para iniciar el pago.'}, status=status.HTTP_400_BAD_REQUEST)

        puja_ganadora = subasta.puja_set.order_by('-monto').first()
        if not puja_ganadora:
            return Response({'error': 'No hay pujas en esta subasta.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar si ya existe una transacción pendiente
        if Transaccion.objects.filter(puja_id=puja_ganadora, estado="pendiente").exists():
            return Response({'error': 'Ya existe una transacción pendiente para esta subasta.'}, status=status.HTTP_400_BAD_REQUEST)

        iva = puja_ganadora.monto * 0.19
        comision = puja_ganadora.monto * 0.10
        precio_final = puja_ganadora.monto + iva + comision

        # Crear la transacción con Transbank
        buy_order = f"{subasta.subasta_id}-{puja_ganadora.puja_id}"
        session_id = f"session-{subasta.subasta_id}"
        return_url = 'http://localhost:3000/confirmar-pago/'

        try:
            transaction = Transaction()
            response = transaction.create(
                buy_order=buy_order,
                session_id=session_id,
                amount=precio_final,
                return_url=return_url
            )

            # Guardar la transacción
            Transaccion.objects.create(
                puja_id=puja_ganadora,
                estado="pendiente",
                token_ws=response['token'],
                monto=precio_final,
                iva=iva,
                comision=comision
            )

            return Response({'url': response['url'] + "?token_ws=" + response['token']}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'Error al iniciar la transacción: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='confirmar_pago')
    def confirmar_pago(self, request):
        """Confirmar el pago desde Transbank."""
        token_ws = request.data.get("token_ws")
        if not token_ws:
            return Response({"error": "Token de pago no recibido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Confirmar la transacción con Transbank
            response = Transaction().commit(token_ws)
            if response['status'] == "AUTHORIZED":
                transaccion = Transaccion.objects.get(token_ws=token_ws)
                transaccion.estado = "completado"
                transaccion.save()

                subasta = transaccion.puja_id.subasta_id
                if subasta.estado == "pendiente":
                    subasta.estado = "cerrada"
                    subasta.fecha_termino = timezone.now()
                    subasta.save()

                    # Eliminar el producto si el pago fue exitoso
                    subasta.producto_id.delete()

                return Response({"message": "Pago completado con éxito, producto eliminado."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "El pago no fue autorizado."}, status=status.HTTP_400_BAD_REQUEST)
        except Transaccion.DoesNotExist:
            return Response({'error': 'Transacción no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error al confirmar el pago: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PujaViewSet(viewsets.ModelViewSet):
    queryset = Puja.objects.all()
    serializer_class = PujaSerializer

    def create(self, request, *args, **kwargs):
        """Crear una puja y actualizar el precio de la subasta."""
        subasta_id = request.data.get('subasta_id')
        subasta = Subasta.objects.get(pk=subasta_id)

        if subasta.sub_terminada:
            return Response({'error': 'No se pueden realizar pujas en una subasta finalizada.'}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)


class TransaccionViewSet(viewsets.ModelViewSet):
    queryset = Transaccion.objects.all()
    serializer_class = TransaccionSerializer


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

    
    @action(detail=False, methods=['get'], url_path='estadisticas')
    def get_estadisticas(self, request):
        

        # Obtener parámetros `month` y `year`
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        # Validar parámetros y calcular rango de fechas
        try:
            month = int(month) if month else timezone.now().month
            year = int(year) if year else timezone.now().year
            inicio_mes = make_aware(datetime(year, month, 1))
            fin_mes = make_aware(datetime(year + (month // 12), (month % 12) + 1, 1)) - timedelta(seconds=1)
        except ValueError:
            return Response({"error": "Los parámetros 'month' y 'year' deben ser números válidos."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Error al calcular las fechas: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Filtrar transacciones completadas asociadas a subastas cerradas
        transacciones_pagadas = Transaccion.objects.filter(
            puja_id__subasta_id__fecha_termino__gte=inicio_mes,
            puja_id__subasta_id__fecha_termino__lte=fin_mes,
            puja_id__subasta_id__estado="cerrada",
            estado="completado"
        )

        # Total de comisiones generadas
        total_comisiones = transacciones_pagadas.aggregate(total=Sum('comision'))['total'] or 0

        # Conteo de transacciones con comisiones
        conteo_comisiones = transacciones_pagadas.count()

        # Promedio de comisiones por subasta cerrada y pagada
        promedio_comisiones = transacciones_pagadas.aggregate(promedio=Avg('comision'))['promedio'] or 0

        # Top 3 tiendas por comisiones generadas
        top_tiendas = (
            transacciones_pagadas
            .values("puja_id__subasta_id__tienda_id__nombre_legal")
            .annotate(total_comisiones=Sum("comision"))
            .order_by("-total_comisiones")[:3]
        )

        # Subastas cerradas y pagadas en el mes
        subastas_pagadas = Subasta.objects.filter(
            estado="cerrada",
            fecha_termino__gte=inicio_mes,
            fecha_termino__lte=fin_mes,
            puja_set__transaccion__estado="completado"  # Filtrar usando la relación correcta
        ).distinct().count()

        # Construir la respuesta
        response = {
            "total_comisiones": total_comisiones,
            "conteo_comisiones": conteo_comisiones,
            "promedio_comisiones_por_subasta": promedio_comisiones,
            "top_tiendas": [
                {"nombre": tienda["puja_id__subasta_id__tienda_id__nombre_legal"], "comisiones": tienda["total_comisiones"]}
                for tienda in top_tiendas
            ],
            "subastas_pagadas": subastas_pagadas,
        }

        return Response(response, status=status.HTTP_200_OK)


    
    @action(detail=False, methods=['get'], url_path='usuarios-registrados-hoy')
    def get_usuarios_registrados_hoy(self, request):
        """
        Endpoint para obtener los usuarios registrados el día de hoy.
        """
        try:
            # Calcular el rango de fechas del día actual
            hoy = make_aware(datetime.now())
            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Filtrar los usuarios registrados hoy
            usuarios_hoy = Usuario.objects.filter(created_at__gte=inicio_dia, created_at__lte=fin_dia)

            # Serializar los datos
            serializer = UsuarioSerializer(usuarios_hoy, many=True)

            # Construir la respuesta
            response = {
                "usuarios_registrados_hoy": serializer.data,
                "total": usuarios_hoy.count(),
            }

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error al cargar los usuarios registrados hoy: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
    @action(detail=False, methods=['get'], url_path='tiendas-hoy')
    def get_tiendas_registradas_hoy(self, request):
        """
        Endpoint para obtener las tiendas registradas el día de hoy.
        """
        try:
            # Calcular el rango de fechas del día actual
            hoy = make_aware(datetime.now())
            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Filtrar las tiendas registradas hoy
            tiendas_hoy = Tienda.objects.filter(created_at__gte=inicio_dia, created_at__lte=fin_dia)

            # Serializar los datos
            serializer = TiendaSerializer(tiendas_hoy, many=True)

            # Construir la respuesta
            response = {
                "tiendas_registradas_hoy": serializer.data,
                "total": tiendas_hoy.count(),
            }

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error al cargar las tiendas registradas hoy: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
    @action(detail=False, methods=['get'], url_path='subastas-iniciadas-hoy')
    def get_subastas_iniciadas_hoy(self, request):
        """
        Endpoint para obtener las subastas que se iniciaron hoy.
        """
        try:
            # Calcular el rango de fechas del día actual
            hoy = make_aware(datetime.now())
            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Filtrar las subastas iniciadas hoy
            subastas_hoy = Subasta.objects.filter(fecha_inicio__gte=inicio_dia, fecha_inicio__lte=fin_dia)

            # Serializar los datos
            serializer = SubastaSerializer(subastas_hoy, many=True)

            # Construir la respuesta
            response = {
                "subastas_iniciadas_hoy": serializer.data,
                "total": subastas_hoy.count(),
            }

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error al cargar las subastas iniciadas hoy: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['get'], url_path='subastas-pendientes-hoy')
    def get_subastas_pendientes_hoy(self, request):
        """
        Endpoint para obtener las subastas que están en estado pendiente hoy.
        """
        try:
            # Calcular el rango de fechas del día actual
            hoy = make_aware(datetime.now())
            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Filtrar las subastas que están pendientes hoy
            subastas_pendientes_hoy = Subasta.objects.filter(
                estado='pendiente',
                fecha_termino__gte=inicio_dia,
                fecha_termino__lte=fin_dia
            )

            # Serializar los datos
            serializer = SubastaSerializer(subastas_pendientes_hoy, many=True)

            # Construir la respuesta
            response = {
                "subastas_pendientes_hoy": serializer.data,
                "total": subastas_pendientes_hoy.count(),
            }

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error al cargar las subastas pendientes de hoy: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


    @action(detail=False, methods=['get'], url_path='subastas-terminan-hoy')
    def get_subastas_terminan_hoy(self, request):
        """
        Endpoint para obtener las subastas que terminan hoy.
        """
        try:
            # Calcular el rango de fechas del día actual
            hoy = make_aware(datetime.now())
            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Filtrar las subastas que terminan hoy
            subastas_terminan_hoy = Subasta.objects.filter(fecha_termino__gte=inicio_dia, fecha_termino__lte=fin_dia)

            # Serializar los datos
            serializer = SubastaSerializer(subastas_terminan_hoy, many=True)

            # Construir la respuesta
            response = {
                "subastas_terminan_hoy": serializer.data,
                "total": subastas_terminan_hoy.count(),
            }

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error al cargar las subastas que terminan hoy: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
    @action(detail=False, methods=['get'], url_path='estadisticas-diarias')
    def get_estadisticas_diarias(self, request):
        # Fecha de hoy
        today = timezone.now().date()

        # Subastas realizadas hoy
        subastas_hoy = Subasta.objects.filter(
            fecha_inicio__date=today
        ).count()

        # Subastas que terminan hoy
        subastas_terminan_hoy = Subasta.objects.filter(
            fecha_termino__date=today
        ).count()

        # Usuarios registrados hoy
        usuarios_registrados_hoy = Usuario.objects.filter(
            created_at__date=today
        ).count()

        # Tiendas registradas hoy
        tiendas_registradas_hoy = Tienda.objects.filter(
            created_at__date=today
        ).count()

        # Construir la respuesta
        response = {
            "subastas_hoy": subastas_hoy,
            "subastas_terminan_hoy": subastas_terminan_hoy,
            "usuarios_registrados_hoy": usuarios_registrados_hoy,
            "tiendas_registradas_hoy": tiendas_registradas_hoy,
        }

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='estadisticas-tienda')
    def get_estadisticas_tienda(self, request):
        """
        Endpoint para obtener estadísticas relacionadas con las tiendas.
        """
        # Obtener parámetros month y year de los query params
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        # Validar los parámetros month y year
        try:
            month = int(month) if month else timezone.now().month
            year = int(year) if year else timezone.now().year
        except ValueError:
            return Response({"error": "Los parámetros 'month' y 'year' deben ser números válidos."}, status=status.HTTP_400_BAD_REQUEST)

        # Calcular el rango de fechas del mes y año seleccionados
        try:
            inicio_mes = make_aware(datetime(year, month, 1))
            if month == 12:
                fin_mes = make_aware(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
            else:
                fin_mes = make_aware(datetime(year, month + 1, 1)) - timedelta(seconds=1)
        except Exception as e:
            return Response({"error": f"Error al calcular las fechas: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Ingresos por tienda en el mes y año seleccionados
        ingresos_por_tienda = (
            Subasta.objects.filter(
                estado="cerrada",
                fecha_termino__gte=inicio_mes,
                fecha_termino__lte=fin_mes
            )
            .values("tienda_id__nombre_legal", "tienda_id__region", "tienda_id__comuna")
            .annotate(ingresos=Sum("precio_final"))
            .order_by("-ingresos")
        )

        # Tienda con más subastas realizadas en el mes y año seleccionados
        tienda_mas_subastas = (
            Subasta.objects.filter(
                fecha_inicio__gte=inicio_mes,
                fecha_inicio__lte=fin_mes
            )
            .values("tienda_id__nombre_legal")
            .annotate(total_subastas=Count("subasta_id"))
            .order_by("-total_subastas")
            .first()
        )

        # Comparación con el mes anterior (si existe)
        if month > 1:
            mes_anterior = month - 1
            year_anterior = year
        else:
            mes_anterior = 12
            year_anterior = year - 1

        # Calcular ingresos del mes anterior
        inicio_mes_anterior = make_aware(datetime(year_anterior, mes_anterior, 1))
        fin_mes_anterior = make_aware(datetime(year_anterior, mes_anterior + 1, 1)) - timedelta(seconds=1)
        
        ingresos_mes_anterior = (
            Subasta.objects.filter(
                estado="cerrada",
                fecha_termino__gte=inicio_mes_anterior,
                fecha_termino__lte=fin_mes_anterior
            )
            .values("tienda_id__nombre_legal")
            .annotate(ingresos=Sum("precio_final"))
        )

        # Calcular el progreso hacia la meta de incremento del 15% de ventas
        ingresos_mes_actual = {tienda["tienda_id__nombre_legal"]: tienda["ingresos"] for tienda in ingresos_por_tienda}
        ingresos_mes_anterior_dict = {tienda["tienda_id__nombre_legal"]: tienda["ingresos"] for tienda in ingresos_mes_anterior}
        
        progreso_meta = []
        for tienda, ingresos in ingresos_mes_actual.items():
            ingresos_anteriores = ingresos_mes_anterior_dict.get(tienda, 0)
            incremento = ((ingresos - ingresos_anteriores) / ingresos_anteriores) * 100 if ingresos_anteriores else 0
            meta_completada = "Sí" if incremento >= 15 else "No"
            progreso_meta.append({
                "tienda": tienda,
                "ingresos_actuales": ingresos,
                "ingresos_mes_anterior": ingresos_anteriores,
                "incremento": incremento,
                "meta_completada": meta_completada,
            })

        # Formato de respuesta para gráficos
        response = {
            "ingresos_por_tienda": list(ingresos_por_tienda),
            "tienda_mas_subastas": tienda_mas_subastas.get("tienda_id__nombre_legal") if tienda_mas_subastas else "N/A",
            "progreso_meta": progreso_meta,  # Para ver el progreso hacia la meta del 15%
            "comparacion_mes_anterior": list(ingresos_mes_anterior),  # Comparación con el mes anterior
            "ingresos_mes_actual": ingresos_mes_actual,  # Datos de ingresos del mes actual
            "ingresos_mes_anterior": ingresos_mes_anterior_dict,  # Ingresos del mes anterior
        }

        return Response(response, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], url_path='estadisticas-usuario')
    def get_estadisticas_usuarios(self, request):
        # Obtener parámetros month y year de los query params
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        # Validar los parámetros month y year
        try:
            month = int(month) if month else datetime.now().month
            year = int(year) if year else datetime.now().year
        except ValueError:
            return Response({"error": "Los parámetros 'month' y 'year' deben ser números válidos."}, status=status.HTTP_400_BAD_REQUEST)

        # Calcular el rango de fechas del mes y año seleccionados
        try:
            inicio_mes = make_aware(datetime(year, month, 1))
            if month == 12:
                fin_mes = make_aware(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
            else:
                fin_mes = make_aware(datetime(year, month + 1, 1)) - timedelta(seconds=1)
        except Exception as e:
            return Response({"error": f"Error al calcular las fechas: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Listas para almacenar los datos por mes
        usuarios_registrados_por_mes = []
        usuarios_activos_por_mes = []
        clientes_recurrentes_por_mes = []

        # Obtener usuarios registrados en el mes solicitado
        usuarios_registrados = Usuario.objects.filter(
            created_at__gte=inicio_mes,
            created_at__lte=fin_mes
        ).count()

        usuarios_registrados_por_mes.append({
            "mes": inicio_mes.strftime("%B %Y"),
            "usuarios": usuarios_registrados
        })

        # Obtener usuarios activos en el mes solicitado
        usuarios_activos = Usuario.objects.filter(
            Q(puja__subasta_id__estado='cerrada') &
            Q(puja__subasta_id__fecha_termino__gte=inicio_mes, 
              puja__subasta_id__fecha_termino__lte=fin_mes)
        ).distinct().count()

        usuarios_activos_por_mes.append({
            "mes": inicio_mes.strftime("%B %Y"),
            "usuarios": usuarios_activos
        })

        # Obtener clientes recurrentes en el mes solicitado
        clientes_recurrentes = Usuario.objects.annotate(num_subastas=Count('puja__subasta_id')) \
            .filter(num_subastas__gt=1, 
                    puja__subasta_id__fecha_termino__gte=inicio_mes, 
                    puja__subasta_id__fecha_termino__lte=fin_mes) \
            .distinct().count()

        clientes_recurrentes_por_mes.append({
            "mes": inicio_mes.strftime("%B %Y"),
            "usuarios": clientes_recurrentes
        })

        # Obtener usuarios por región
        usuarios_por_region = Usuario.objects.values('region') \
            .annotate(count=Count('usuario')) \
            .filter(created_at__gte=inicio_mes, created_at__lte=fin_mes) \
            .order_by('region')

        # Obtener usuarios por comuna
        usuarios_por_comuna = Usuario.objects.values('comuna') \
            .annotate(count=Count('usuario')) \
            .filter(created_at__gte=inicio_mes, created_at__lte=fin_mes) \
            .order_by('comuna')

        # Responder con los datos
        response = {
            "usuarios_registrados_por_mes": usuarios_registrados_por_mes,
            "usuarios_activos_por_mes": usuarios_activos_por_mes,
            "clientes_recurrentes_por_mes": clientes_recurrentes_por_mes,
            "usuarios_por_region": list(usuarios_por_region),  
            "usuarios_por_comuna": list(usuarios_por_comuna),  # Convertir el queryset a lista
        }

        return Response(response, status=status.HTTP_200_OK)



    @action(detail=False, methods=['get'], url_path='estadisticas-subasta')
    def get_estadisticas_subasta(self, request):
        """
        Endpoint para obtener estadísticas relacionadas con las subastas.
        """
        # Obtener parámetros month y year de los query params
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        # Validar los parámetros month y year
        try:
            month = int(month) if month else timezone.now().month
            year = int(year) if year else timezone.now().year
        except ValueError:
            return Response({"error": "Los parámetros 'month' y 'year' deben ser números válidos."}, status=status.HTTP_400_BAD_REQUEST)

        # Calcular el rango de fechas del mes y año seleccionados
        try:
            inicio_mes = make_aware(datetime(year, month, 1))
            if month == 12:
                fin_mes = make_aware(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
            else:
                fin_mes = make_aware(datetime(year, month + 1, 1)) - timedelta(seconds=1)
        except Exception as e:
            return Response({"error": f"Error al calcular las fechas: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Subastas por estado en el mes actual
        subastas_vigentes = Subasta.objects.filter(
            estado="vigente",
            fecha_inicio__gte=inicio_mes,
            fecha_inicio__lte=fin_mes
        ).count()

        subastas_pendientes = Subasta.objects.filter(
            estado="pendiente",
            fecha_termino__gte=inicio_mes,
            fecha_termino__lte=fin_mes
        ).count()

        subastas_cerradas = Subasta.objects.filter(
            estado="cerrada",
            fecha_termino__gte=inicio_mes,
            fecha_termino__lte=fin_mes
        ).count()

        # Estadísticas adicionales para las subastas cerradas (ganadas)
        subastas_cerradas_query = Subasta.objects.filter(
            estado="cerrada",
            fecha_termino__gte=inicio_mes,
            fecha_termino__lte=fin_mes
        )

        # Precio promedio de subastas ganadas
        precio_promedio = subastas_cerradas_query.aggregate(Avg('precio_final'))['precio_final__avg'] or 0

        # Subasta más cara
        subasta_mas_cara = subastas_cerradas_query.aggregate(Max('precio_final'))['precio_final__max'] or 0

        # Subastas por tipo de prenda (con más subastas)
        subastas_por_tipo_prenda = Subasta.objects.filter(
            fecha_inicio__gte=inicio_mes,
            fecha_inicio__lte=fin_mes
        ).values('producto_id__tipo_id__tipo').annotate(num_subastas=Count('producto_id')).order_by('-num_subastas')

        # Subastas por tipo de prenda y estado
        subastas_por_tipo_prenda_estado = Subasta.objects.filter(
            fecha_inicio__gte=inicio_mes,
            fecha_inicio__lte=fin_mes
        ).values('producto_id__tipo_id__tipo', 'estado').annotate(num_subastas=Count('producto_id')).order_by('-num_subastas')

        # Calcular fechas para el mes anterior
        mes_anterior = (month - 1) if month > 1 else 12
        anio_anterior = year if month > 1 else (year - 1)

        inicio_mes_anterior = make_aware(datetime(anio_anterior, mes_anterior, 1))
        if mes_anterior == 12:
            fin_mes_anterior = make_aware(datetime(anio_anterior + 1, 1, 1)) - timedelta(seconds=1)
        else:
            fin_mes_anterior = make_aware(datetime(anio_anterior, mes_anterior + 1, 1)) - timedelta(seconds=1)

        # Subastas por estado en el mes anterior
        subastas_vigentes_anterior = Subasta.objects.filter(
            estado="vigente",
            fecha_inicio__gte=inicio_mes_anterior,
            fecha_inicio__lte=fin_mes_anterior
        ).count()

        subastas_pendientes_anterior = Subasta.objects.filter(
            estado="pendiente",
            fecha_termino__gte=inicio_mes_anterior,
            fecha_termino__lte=fin_mes_anterior
        ).count()

        subastas_cerradas_anterior = Subasta.objects.filter(
            estado="cerrada",
            fecha_termino__gte=inicio_mes_anterior,
            fecha_termino__lte=fin_mes_anterior
        ).count()

        # Respuesta con las estadísticas
        response = {
            "subastas_vigentes": subastas_vigentes,
            "subastas_pendientes": subastas_pendientes,
            "subastas_cerradas": subastas_cerradas,
            "precio_promedio_subastas_cerradas": precio_promedio,
            "subasta_mas_cara": subasta_mas_cara,
            "subastas_por_tipo_prenda": list(subastas_por_tipo_prenda),
            "subastas_por_tipo_prenda_estado": list(subastas_por_tipo_prenda_estado),
            "comparativa_mes_anterior": {
                "subastas_vigentes": subastas_vigentes_anterior,
                "subastas_pendientes": subastas_pendientes_anterior,
                "subastas_cerradas": subastas_cerradas_anterior,
            }
        }

        return Response(response, status=status.HTTP_200_OK)







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

        # Calcular IVA y comisión
        iva = puja_ganadora.monto * 0.19
        comision = puja_ganadora.monto * 0.10
        precio_final = puja_ganadora.monto + iva + comision

        # Proceder con la creación de la transacción si no hay conflictos
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
                amount=precio_final,  # Utilizar el precio final calculado
                return_url=return_url
            )

            # Creación de la transacción en la base de datos
            Transaccion.objects.create(
                puja_id=puja_ganadora,
                estado="pendiente",
                fecha=timezone.now(),
                token_ws=response['token'],
                monto=precio_final,  # Guardar el monto con IVA y comisión incluidos
                iva=iva,
                comision=comision
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
        self.precio_final = (self.precio_inicial or 0) + puja_ganadora.monto
        self.estado = "pendiente"
        # Crear transacción asociada a la puja ganadora
        Transaccion.objects.create(
            puja_id=puja_ganadora,
            estado="pendiente",
            monto=self.precio_final,
        )
    else:
        self.precio_final = self.precio_inicial or 0
        self.estado = "cerrada"
    self.save()