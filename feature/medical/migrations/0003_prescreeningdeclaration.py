import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0002_screeningresult_vaccinationlog_postinjectiontracking_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PreScreeningDeclaration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('has_fever', models.BooleanField(default=False)),
                ('has_allergy_history', models.BooleanField(default=False)),
                ('has_chronic_condition', models.BooleanField(default=False)),
                ('recent_symptoms', models.TextField(blank=True, null=True)),
                ('current_medications', models.TextField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pre_screening', to='booking.booking')),
            ],
        ),
    ]
