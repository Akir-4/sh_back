from django.urls import path
from .views import ComentariosView

urlpatterns = [
    path('comentarios/', ComentariosView.as_view(), name='comentarios'),
]