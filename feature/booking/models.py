from django.db import models

from feature.authentication.models import User


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_READY_TO_INJECT = 'ready_to_inject'
    STATUS_IN_OBSERVATION = 'in_observation'
    STATUS_COMPLETED = 'completed'
    STATUS_DELAYED = 'delayed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_CHECKED_IN, 'Checked In'),
        (STATUS_READY_TO_INJECT, 'Ready to Inject'),
        (STATUS_IN_OBSERVATION, 'In Observation'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DELAYED, 'Delayed'),
    ]

    ACTIVE_STATUSES = [
        STATUS_PENDING,
        STATUS_CONFIRMED,
        STATUS_CHECKED_IN,
        STATUS_READY_TO_INJECT,
        STATUS_IN_OBSERVATION,
    ]

    BOOKING_SOURCE_ONLINE = 'online'
    BOOKING_SOURCE_WALKIN = 'walkin'
    BOOKING_SOURCE_CHOICES = [
        (BOOKING_SOURCE_ONLINE, 'Online'),
        (BOOKING_SOURCE_WALKIN, 'Walk-in'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='bookings',
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    vaccine_name = models.CharField(max_length=120, default='General Vaccine')
    vaccine_date = models.DateField()
    dose_number = models.PositiveSmallIntegerField(default=1)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    booking_source = models.CharField(
        max_length=10,
        choices=BOOKING_SOURCE_CHOICES,
        default=BOOKING_SOURCE_ONLINE,
    )
    rescheduled_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rescheduled_bookings',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f'{self.full_name} - {self.vaccine_name} - {self.vaccine_date}'
