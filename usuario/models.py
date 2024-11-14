from django.db import models
from django.core.exceptions import ValidationError
import re

class Usuario(models.Model):
    ROL_CHOICES = [
        ('comprador', 'Comprador'),
        ('administrador', 'Administrador'),
        ('gestor', 'Gestor'),
    ]

    usuario_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    usuario = models.CharField(max_length=100, unique=True)  # Nombre de usuario único
    contrasena = models.CharField(max_length=100)  # Recomendación: encriptar contraseñas
    email = models.EmailField(max_length=100, unique=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    comuna = models.CharField(max_length=100, null=True, blank=True)
    direccion = models.CharField(max_length=100, null=True, blank=True)
    telefono = models.CharField(max_length=100, null=True, blank=True)
    imagen = models.ImageField(upload_to='usuarios/fotos/', null=True, blank=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='comprador')

    def __str__(self):
        return self.usuario

    def es_admin(self):
        return self.rol == 'administrador'

    def es_gestor(self):
        return self.rol == 'gestor'

    def es_comprador(self):
        return self.rol == 'comprador'

    # Validador para el campo de email
    def clean_email(self):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@(hotmail|gmail)\.com$', self.email):
            raise ValidationError("El correo electrónico debe ser de dominio hotmail.com o gmail.com")

    # Validador para el campo de teléfono
    def clean_telefono(self):
        if self.telefono and not re.match(r'^\+?\d{10,15}$', self.telefono):
            raise ValidationError("El número de teléfono debe contener solo dígitos y puede incluir un prefijo '+'")

    # Método que llama a los validadores personalizados al guardar el modelo
    def clean(self):
        super().clean()  # Llama al método de limpieza de Django para validaciones predeterminadas
        self.clean_email()
        self.clean_telefono()
