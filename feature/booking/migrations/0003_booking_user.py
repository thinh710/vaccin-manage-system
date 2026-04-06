from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_user_social_provider_fields'),
        ('booking', '0002_alter_booking_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='bookings',
                to='authentication.user',
            ),
        ),
    ]
