from django.urls import path
from . import views

urlpatterns = [
    path('iniciar/', views.iniciar_transaccion, name='iniciar_transaccion'),
    path('retorno/', views.retorno_webpay, name='retorno_webpay'),
]
