from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockexport',
            name='export_type',
            field=models.CharField(
                choices=[
                    ('transfer', 'Xuất chuyển'),
                    ('disposal', 'Xuất hủy'),
                    ('expired', 'Hủy hết hạn'),
                ],
                default='transfer',
                max_length=20,
                verbose_name='Loại xuất',
            ),
        ),
    ]
