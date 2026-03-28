from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('authentication', '0003_user_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='auth_provider',
            field=models.CharField(
                choices=[('local', 'Local'), ('google', 'Google'), ('facebook', 'Facebook')],
                default='local',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='provider_user_id',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
