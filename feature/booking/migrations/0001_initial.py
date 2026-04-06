from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=100)),
                ('phone', models.CharField(max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('vaccine_name', models.CharField(default='General Vaccine', max_length=120)),
                ('vaccine_date', models.DateField()),
                ('dose_number', models.PositiveSmallIntegerField(default=1)),
                ('note', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-id']},
        ),
    ]
