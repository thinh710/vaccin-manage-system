from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import models

from feature.authentication.models import User


class Booking(models.Model):
    STATUS_AWAITING_ELIGIBILITY = 'awaiting_eligibility'
    STATUS_PENDING = 'pending'
    STATUS_DEPOSIT_PENDING = 'deposit_pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_INELIGIBLE = 'ineligible'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_READY_TO_INJECT = 'ready_to_inject'
    STATUS_IN_OBSERVATION = 'in_observation'
    STATUS_COMPLETED = 'completed'
    STATUS_DELAYED = 'delayed'
    DEPOSIT_RATE = Decimal('0.20')

    STATUS_CHOICES = [
        (STATUS_AWAITING_ELIGIBILITY, 'Awaiting Eligibility'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_DEPOSIT_PENDING, 'Deposit Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_INELIGIBLE, 'Ineligible'),
        (STATUS_CHECKED_IN, 'Checked In'),
        (STATUS_READY_TO_INJECT, 'Ready to Inject'),
        (STATUS_IN_OBSERVATION, 'In Observation'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DELAYED, 'Delayed'),
    ]

    ACTIVE_STATUSES = [
        STATUS_AWAITING_ELIGIBILITY,
        STATUS_PENDING,
        STATUS_DEPOSIT_PENDING,
        STATUS_CONFIRMED,
        STATUS_INELIGIBLE,
        STATUS_CHECKED_IN,
        STATUS_READY_TO_INJECT,
        STATUS_IN_OBSERVATION,
        STATUS_DELAYED,
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
    vaccine = models.ForeignKey(
        'assets.Vaccine',
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
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit_deadline = models.DateField(null=True, blank=True)
    deposit_paid_at = models.DateTimeField(null=True, blank=True)
    deposit_paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='deposit_confirmed_bookings',
        null=True,
        blank=True,
    )
    deposit_note = models.TextField(blank=True, null=True)
    eligibility_confirmed_at = models.DateTimeField(null=True, blank=True)
    eligibility_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='eligibility_confirmed_bookings',
        null=True,
        blank=True,
    )
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

    @staticmethod
    def _to_money(value):
        amount = Decimal(value or 0)
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_deposit_amount(cls, total_amount):
        return cls._to_money(cls._to_money(total_amount) * cls.DEPOSIT_RATE)

    def recalculate_financials(self, vaccine=None, vaccine_date=None):
        vaccine_obj = vaccine if vaccine is not None else self.vaccine
        target_date = vaccine_date if vaccine_date is not None else self.vaccine_date
        total_amount = self._to_money(getattr(vaccine_obj, 'price', 0))

        self.total_amount = total_amount
        self.deposit_amount = self.calculate_deposit_amount(total_amount)
        self.deposit_deadline = target_date - timedelta(days=2) if target_date else None

    def clear_deposit_confirmation(self):
        self.deposit_paid_at = None
        self.deposit_paid_by = None
        self.deposit_note = None

    def clear_eligibility_confirmation(self):
        self.eligibility_confirmed_at = None
        self.eligibility_confirmed_by = None
