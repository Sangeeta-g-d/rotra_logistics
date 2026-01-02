# Auto migration to ensure holding_charges_added_at and holding_charges_added_at_status exist
from django.db import migrations, models
from decimal import Decimal

class Migration(migrations.Migration):

    dependencies = [
        ('logistics_app', '0047_alter_load_trip_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='load',
            name='holding_charges_added_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Holding Charges Added At', help_text='When the holding charges were added'),
        ),
        migrations.AddField(
            model_name='load',
            name='holding_charges_added_at_status',
            field=models.CharField(blank=True, null=True, max_length=20, verbose_name='Trip Status When Charges Added', help_text='The trip status at which first holding charge was added'),
        ),
    ]
