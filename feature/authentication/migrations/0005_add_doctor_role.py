from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_user_social_provider_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('citizen', 'Citizen'),
                    ('staff', 'Staff'),
                    ('doctor', 'Doctor'),
                ],
                default='citizen',
                max_length=20,
            ),
        ),
    ]
