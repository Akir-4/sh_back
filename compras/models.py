from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from twilio.rest import Client
from django.conf import settings

class Subasta(models.Model):
    subasta_id = models.AutoField(primary_key=True)
    tienda_id = models.ForeignKey('tiendas.Tienda', on_delete=models.CASCADE)
    producto_id = models.ForeignKey('productos.Producto', on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField()
    fecha_termino = models.DateTimeField()

    ESTADO_OPCIONES = [
        ('vigente', 'Vigente'),
        ('pendiente', 'Pendiente'),
        ('cerrada', 'Cerrada'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_OPCIONES, default='vigente')
    precio_inicial = models.IntegerField(null=True, blank=True)
    precio_final = models.IntegerField(null=True, blank=True)

    @property
    def sub_terminada(self):
        return self.estado == 'vigente' and timezone.now() > self.fecha_termino

    def finalizar_subasta(self):
        puja_ganadora = self.puja_set.order_by('-monto').first()
        if puja_ganadora:
            self.precio_final = puja_ganadora.monto * 1.10
            self.estado = "pendiente"
            # Enviar notificación al ganador
            usuario_ganador = puja_ganadora.usuario_id
            if usuario_ganador and usuario_ganador.telefono:
                self.enviar_notificacion_ganador(usuario_ganador.telefono)
        else:
            self.estado = "cerrada"
            self.precio_final = self.precio_inicial or 0
        super().save()

    def enviar_notificacion_ganador(self, telefono_ganador):
        """Envía una notificación de WhatsApp al ganador de la subasta."""
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        mensaje = f"¡Hola! Felicidades, has ganado la subasta del producto '{self.producto_id.nombre}' con un precio final de ${self.precio_final} CLP. Ahora solo necesitas completar el pago. Ingresa a tu perfil para finalizar la compra. ¡Te felicitamos nuevamente!"

        
        try:
            message = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_NUMBER,
                body=mensaje,
                to=f'whatsapp:{telefono_ganador}'
            )
            print("Notificación enviada al ganador:", message.sid)
        except Exception as e:
            print(f"Error al enviar la notificación de WhatsApp: {e}")

    def save(self, *args, **kwargs):
        if self.sub_terminada:
            self.finalizar_subasta()
        super().save(*args, **kwargs)

@receiver(post_save, sender=Subasta)
def verificar_estado_subasta(sender, instance, **kwargs):
    if instance.sub_terminada:
        instance.finalizar_subasta()

class Puja(models.Model):
    puja_id = models.AutoField(primary_key=True)
    subasta_id = models.ForeignKey('compras.Subasta', on_delete=models.CASCADE, related_name='puja_set')
    usuario_id = models.ForeignKey('usuario.Usuario', on_delete=models.CASCADE)
    monto = models.IntegerField()
    fecha = models.DateTimeField()

class Transaccion(models.Model):
    transaccion_id = models.AutoField(primary_key=True)
    puja_id = models.ForeignKey(Puja, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20)
    fecha = models.DateTimeField(default=timezone.now)
    token_ws = models.CharField(max_length=100, blank=True, null=True)
    monto = models.IntegerField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.estado == "completado":
            subasta = self.puja_id.subasta_id
            if subasta.estado == 'pendiente':
                subasta.estado = "cerrada"
                subasta.save()
