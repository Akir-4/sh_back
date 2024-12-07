from django.db import models

class Comentarios(models.Model):
    TIPO_OPCIONES = [
        ('reclamo', 'Reclamo'),
        ('sugerencia', 'Sugerencia'),
        ('otro', 'Otro'),
    ]
    
    nombre = models.CharField(max_length=255, blank=True, null=True)
    correo = models.EmailField()
    tipo = models.CharField(max_length=20, choices=TIPO_OPCIONES)
    categoria = models.CharField(max_length=255, blank=True, null=True)
    mensaje = models.TextField()
    adjunto = models.FileField(upload_to='comentarios_adjuntos/', blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo.capitalize()} - {self.creado_en.date()}"
