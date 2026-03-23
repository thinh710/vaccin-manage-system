from django.db import models


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_SCREENED = 'screened'
    STATUS_COMPLETED = 'completed'
    STATUS_DELAYED = 'delayed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_CHECKED_IN, 'Checked In'),
        (STATUS_SCREENED, 'Screened'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DELAYED, 'Delayed'),
    ]

    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    vaccine_name = models.CharField(max_length=120, default='General Vaccine')
    vaccine_date = models.DateField()
    dose_number = models.PositiveSmallIntegerField(default=1)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f'{self.full_name} - {self.vaccine_name} - {self.vaccine_date}'
