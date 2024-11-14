from django.urls import path
from .views import LoginTiendaView

urlpatterns = [
    path('login/tienda/', LoginTiendaView.as_view(), name='login_tienda'),
]
