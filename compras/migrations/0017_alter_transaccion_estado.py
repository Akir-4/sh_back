# Generated by Django 5.1.1 on 2024-11-08 08:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0016_alter_transaccion_fecha'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaccion',
            name='estado',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('completado', 'Completado')], default='pendiente', max_length=20),
        ),
    ]
