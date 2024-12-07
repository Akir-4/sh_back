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
    precio_subasta = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    @property
    def iva(self):
        """Calcula el IVA del precio inicial."""
        return self.precio_inicial * 0.19 if self.precio_inicial else 0

    @property
    def comision(self):
        """Calcula la comisión del precio inicial."""
        return self.precio_inicial * 0.10 if self.precio_inicial else 0

    @property
    def sub_terminada(self):
        """Verifica si la subasta ha terminado."""
        return self.estado == 'vigente' and timezone.now() > self.fecha_termino

    def recalcular_precio_subasta(self, monto=None):
        """Recalcula el precio_subasta basado en el monto actual o inicial."""
        monto_base = monto if monto is not None else self.precio_inicial
        self.precio_subasta = monto_base + (monto_base * 0.19) + (monto_base * 0.10)
        self.save()

    def finalizar_subasta(self):
        """Finaliza la subasta, calcula el precio final y cambia el estado."""
        puja_ganadora = self.puja_set.order_by('-monto').first()
        if puja_ganadora:
            self.precio_final = puja_ganadora.monto  # Solo el monto puro de la puja
            self.estado = "pendiente"
            usuario_ganador = puja_ganadora.usuario_id
            if usuario_ganador and usuario_ganador.telefono:
                self.enviar_notificacion_ganador(usuario_ganador.telefono)
        else:
            self.precio_final = self.precio_inicial  # Si no hay pujas, queda el precio inicial
            self.estado = "cerrada"
        self.save()

    def enviar_notificacion_ganador(self, telefono_ganador):
        """Envía una notificación de WhatsApp al ganador de la subasta."""
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        mensaje = (
            f"¡Hola! Felicidades, has ganado la subasta del producto '{self.producto_id.nombre}' "
            f"con un precio final de ${self.precio_final:.2f} CLP. "
            "Ingresa a tu perfil para completar el pago. ¡Felicidades nuevamente!"
        )
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
        """Calcula precio_subasta al guardar una subasta."""
        if not self.pk and self.precio_inicial:
            self.recalcular_precio_subasta()
        super().save(*args, **kwargs)

    def actualizar_puja(self, monto):
        """Actualiza el precio_subasta según el monto actual de una nueva puja."""
        self.recalcular_precio_subasta(monto)


@receiver(post_save, sender=Subasta)
def verificar_estado_subasta(sender, instance, **kwargs):
    """Verifica el estado de la subasta después de guardar."""
    if instance.sub_terminada:
        instance.finalizar_subasta()

class Puja(models.Model):
    puja_id = models.AutoField(primary_key=True)
    subasta_id = models.ForeignKey('compras.Subasta', on_delete=models.CASCADE, related_name='puja_set')
    usuario_id = models.ForeignKey('usuario.Usuario', on_delete=models.CASCADE)
    monto = models.IntegerField()
    fecha = models.DateTimeField()

    def save(self, *args, **kwargs):
        """Notifica a la subasta que actualice el precio_subasta cuando se crea una nueva puja."""
        super().save(*args, **kwargs)
        self.subasta_id.actualizar_puja(self.monto)

class Transaccion(models.Model):
    transaccion_id = models.AutoField(primary_key=True)
    puja_id = models.ForeignKey(Puja, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20)
    fecha = models.DateTimeField(default=timezone.now)
    token_ws = models.CharField(max_length=100, blank=True, null=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)  # Precio final (monto total)
    iva = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    comision = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    envio = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Asocia IVA, comisión y monto desde la subasta al crear la transacción."""
        if not self.pk:  # Solo al crear
            subasta = self.puja_id.subasta_id
            self.monto = subasta.precio_final  # El precio final ya incluye IVA y comisión
            self.iva = subasta.precio_inicial * 0.19
            self.comision = subasta.precio_inicial * 0.10
        super().save(*args, **kwargs)
