from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_user_full_name_and_citizen_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='allergies',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='avatar_data',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='blood_group',
            field=models.CharField(
                choices=[
                    ('A+', 'A+'),
                    ('A-', 'A-'),
                    ('B+', 'B+'),
                    ('B-', 'B-'),
                    ('AB+', 'AB+'),
                    ('AB-', 'AB-'),
                    ('O+', 'O+'),
                    ('O-', 'O-'),
                    ('UNKNOWN', 'Unknown'),
                ],
                default='UNKNOWN',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='gender',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='medical_history',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
