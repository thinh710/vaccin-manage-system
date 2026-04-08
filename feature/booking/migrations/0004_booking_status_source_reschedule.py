from django.db import migrations, models
import django.db.models.deletion


def migrate_screened_to_ready(apps, schema_editor):
    """Đổi tất cả bản ghi status='screened' → 'ready_to_inject'."""
    Booking = apps.get_model('booking', 'Booking')
    Booking.objects.filter(status='screened').update(status='ready_to_inject')


def reverse_migrate_ready_to_screened(apps, schema_editor):
    """Rollback: 'ready_to_inject' → 'screened'."""
    Booking = apps.get_model('booking', 'Booking')
    Booking.objects.filter(status='ready_to_inject').update(status='screened')


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0003_booking_user'),
    ]

    operations = [
        # 1. Cập nhật field status để chấp nhận các giá trị mới
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('confirmed', 'Confirmed'),
                    ('cancelled', 'Cancelled'),
                    ('checked_in', 'Checked In'),
                    ('ready_to_inject', 'Ready to Inject'),
                    ('in_observation', 'In Observation'),
                    ('completed', 'Completed'),
                    ('delayed', 'Delayed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        # 2. Đổi data: screened → ready_to_inject
        migrations.RunPython(
            migrate_screened_to_ready,
            reverse_code=reverse_migrate_ready_to_screened,
        ),
        # 3. Thêm booking_source
        migrations.AddField(
            model_name='booking',
            name='booking_source',
            field=models.CharField(
                choices=[
                    ('online', 'Online'),
                    ('walkin', 'Walk-in'),
                ],
                default='online',
                max_length=10,
            ),
        ),
        # 4. Thêm rescheduled_from FK
        migrations.AddField(
            model_name='booking',
            name='rescheduled_from',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rescheduled_bookings',
                to='booking.booking',
            ),
        ),
    ]
