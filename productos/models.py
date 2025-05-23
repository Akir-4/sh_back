from django.db import models
from django.utils.text import slugify
from tiendas.models import Tienda

# Modelos para PRODUCTOS

# Modelo de Donación
class Donacion(models.Model):
    """Modelo para registrar donaciones a ONGs."""
    donacion_id = models.AutoField(primary_key=True)
    nombre_ong = models.CharField(max_length=200)  # Nombre de la ONG
    descripcion = models.TextField()  # Descripción de la donación o detalles
    ubicacion = models.CharField(max_length=200)  # Ubicación de la ONG
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Fecha de creación de la donación

    def __str__(self):
        return f"Donación a {self.nombre_ong}"

class Material(models.Model):
    """Modelo para el tipo de material del producto."""
    material_id = models.AutoField(primary_key=True)
    material = models.CharField(max_length=100)

    def __str__(self):
        return self.material

class Marca(models.Model):
    """Modelo para marcas de productos."""
    marca_id = models.AutoField(primary_key=True)
    marca = models.CharField(max_length=100)

    def __str__(self):
        return self.marca


class Tipo_Prenda(models.Model):
    """Modelo para tipos de prendas."""
    tipo_id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo


class Producto(models.Model):
    """Modelo para productos."""
    producto_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    marca_id = models.ForeignKey(Marca, on_delete=models.CASCADE)  # Relación con Marca
    tipo_id = models.ForeignKey(Tipo_Prenda, on_delete=models.CASCADE)  # Relación con Tipo_Prenda
    ESTADOS = [(i, i) for i in range(1, 8)]
    estado = models.IntegerField(choices=ESTADOS, default=1)
    tienda_id = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name="productos")  # Usar tienda_id para la relación del producto
    TALLAS = (
        ('XS', 'XS'),
        ('S', 'S'),
        ('M', 'M'),
        ('L', 'L'),
        ('XL', 'XL'),
        ('XXL', 'XXL'),
        ('XXXL', 'XXXL'),
    )
    tamano = models.CharField(max_length=4, choices=TALLAS, null=False, blank=False)
    imagen_1 = models.ImageField(upload_to='productos/fotos/', null=True, blank=True)
    imagen_2 = models.ImageField(upload_to='productos/fotos/', null=True, blank=True, default=None)
    imagen_3 = models.ImageField(upload_to='productos/fotos/', null=True, blank=True, default=None)
    imagen_4 = models.ImageField(upload_to='productos/fotos/', null=True, blank=True, default=None)
    slug = models.SlugField(default='', null=False, blank=True)  # Permitir blank para auto-generar
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    subastado = models.BooleanField(default=False)
    donacion = models.ForeignKey(Donacion, on_delete=models.SET_NULL, null=True, blank=True)  # Relación opcional con Donación
    def __str__(self):
        return self.nombre

    # Sobrescribir el método save para generar automáticamente el slug
    def save(self, *args, **kwargs):
        if not self.slug:  # Si el slug no está definido, se genera
            self.slug = slugify(self.nombre)
        super(Producto, self).save(*args, **kwargs)  # Llamada al método original
