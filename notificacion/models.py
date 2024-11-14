from django.db import models

# Create your models here.
class Notificacion(models.Model):
    TIPOS_NOTIFICACION = (
        ('INFO', 'Información'),
        ('WARN', 'Advertencia'),
        ('ERROR', 'Error'),
    )
    tipo = models.CharField(max_length=10, choices=TIPOS_NOTIFICACION, default='INFO')
    usuario = models.ForeignKey('usuario.Usuario', on_delete=models.CASCADE, related_name='notificaciones')
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        return self.mensaje