from django.db import models
from django.core.exceptions import ValidationError
import re

class Tienda(models.Model):
    """Modelo para representar una tienda o empresa."""

    tienda_id = models.AutoField(primary_key=True)
    nombre_legal = models.CharField(max_length=255)
    razon_social = models.CharField(max_length=255, blank=True)
    rut = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=50)
    direccion_fisica = models.TextField()
    telefono_principal = models.CharField(max_length=20)
    correo_electronico = models.EmailField()
    logo = models.ImageField(upload_to='usuarios/fotos/', null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    comuna = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.nombre_legal

    def clean_rut(self):
        """Valida que el RUT sea correcto según el dígito verificador."""
        # Remover puntos y guiones del RUT
        clean_rut = self.rut.replace(".", "").replace("-", "")
        rut_number = clean_rut[:-1]  # Número del RUT sin el dígito verificador
        verifier = clean_rut[-1].upper()  # Dígito verificador

        # Validación del RUT con el cálculo del dígito verificador (Módulo 11)
        try:
            sum = 0
            multiplier = 2

            # Recorre los dígitos del RUT de derecha a izquierda
            for digit in reversed(rut_number):
                sum += int(digit) * multiplier
                multiplier = 3 if multiplier == 7 else multiplier + 1

            remainder = 11 - (sum % 11)
            calculated_verifier = '0' if remainder == 11 else 'K' if remainder == 10 else str(remainder)

            if calculated_verifier != verifier:
                raise ValidationError("El RUT ingresado no es válido.")

        except ValueError:
            raise ValidationError("El RUT ingresado contiene caracteres no válidos.")

    def clean_correo_electronico(self):
        """Valida que el correo electrónico tenga un dominio específico."""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@(hotmail|gmail)\.com$', self.correo_electronico):
            raise ValidationError("El correo electrónico debe ser de dominio hotmail.com o gmail.com")

    def clean_telefono_principal(self):
        """Valida el formato del número de teléfono."""
        if not re.match(r'^\+?\d{10,15}$', self.telefono_principal):
            raise ValidationError("El número de teléfono debe contener solo dígitos y puede incluir un prefijo '+'")

    def clean(self):
        """Método de limpieza general para validaciones adicionales."""
        super().clean()  # Llama a la validación predeterminada de Django
        self.clean_rut()
        self.clean_correo_electronico()
        self.clean_telefono_principal()


class Bodega(models.Model):
    """Modelo para representar una bodega."""

    bodega_id = models.AutoField(primary_key=True)
    tienda_id = models.ForeignKey(Tienda, on_delete=models.CASCADE)
    producto_id = models.ForeignKey('productos.Producto', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f'{self.tienda_id.nombre_legal} - Producto: {self.producto_id.nombre if self.producto_id else "Sin producto"}'
