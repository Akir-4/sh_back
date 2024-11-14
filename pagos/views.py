# pagos/views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_type import IntegrationType
from django.views.decorators.csrf import csrf_exempt
import json

# Configuración para la integración en entorno de prueba
Transaction.commerce_code = "597055555532"  # Código de comercio de prueba proporcionado por Transbank
Transaction.api_key = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"  # API Key de prueba
Transaction.integration_type = IntegrationType.TEST  # Entorno de prueba

@csrf_exempt
def iniciar_transaccion(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Parsear la solicitud JSON
            subasta_id = data.get('subasta_id')
            amount = data.get('amount')  # Monto de la transacción (dinámico)

            if not subasta_id or not amount:
                return JsonResponse({"error": "Faltan parámetros: subasta_id o amount"}, status=400)

            session_id = f"sesion_{subasta_id}"
            buy_order = f"orden_de_compra_{subasta_id}"
            return_url = "http://localhost:8000/pagos/retorno/"  # URL para redireccionar al cliente después del pago

            # Crear la transacción
            response = Transaction().create(
                buy_order=buy_order,
                session_id=session_id,
                amount=amount,
                return_url=return_url
            )

            # La URL de pago es la que necesitas para redirigir al cliente
            url_redireccion = response.get("url")
            token_ws = response.get("token")

            # Devuelve la URL de redirección al cliente
            return JsonResponse({"url": url_redireccion, "token": token_ws})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Error al parsear el cuerpo de la solicitud"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método no permitido"}, status=405)

@csrf_exempt
def retorno_webpay(request):
    if request.method == "POST":
        token_ws = request.POST.get("token_ws")

        try:
            # Confirmar la transacción con el token de retorno
            response = Transaction().commit(token_ws)
            if response['status'] == 'AUTHORIZED':
                return render(request, "pagos/exito.html", {"response": response})
            else:
                return render(request, "pagos/error.html", {"error": "Transacción no autorizada"})

        except Exception as e:
            return render(request, "pagos/error.html", {"error": str(e)})

    return JsonResponse({"error": "Método no permitido"}, status=405)
