# Generated migration for HoldingCharge model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('logistics_app', '0047_alter_load_trip_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='HoldingCharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Amount of holding charges', max_digits=14)),
                ('trip_stage', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('loaded', 'Reach Loading Point'), ('lr_uploaded', 'LR Uploaded'), ('in_transit', 'In Transit'), ('unloading', 'Reach Unloading Point'), ('pod_uploaded', 'POD Uploaded'), ('payment_completed', 'Payment Completed'), ('hold', 'Hold')], help_text='The trip stage/status at which this charge was applied', max_length=20)),
                ('reason', models.TextField(help_text='Reason for applying this holding charge')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this charge was added')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this charge was last updated')),
                ('added_by', models.ForeignKey(blank=True, help_text='Admin/user who added this charge', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='added_holding_charges', to=settings.AUTH_USER_MODEL)),
                ('load', models.ForeignKey(help_text='The load/trip this holding charge is applied to', on_delete=django.db.models.deletion.CASCADE, related_name='holding_charge_entries', to='logistics_app.load')),
            ],
            options={
                'verbose_name': 'Holding Charge',
                'verbose_name_plural': 'Holding Charges',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='holdingcharge',
            index=models.Index(fields=['load', 'created_at'], name='logistics_app_holdingcharge_load_created_idx'),
        ),
        migrations.AddIndex(
            model_name='holdingcharge',
            index=models.Index(fields=['trip_stage'], name='logistics_app_holdingcharge_trip_stage_idx'),
        ),
    ]
