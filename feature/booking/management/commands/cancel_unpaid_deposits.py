from django.core.management.base import BaseCommand
from django.utils import timezone

from feature.booking.models import Booking


class Command(BaseCommand):
    help = "Cancel online bookings that have passed the deposit deadline without a confirmed deposit."

    def handle(self, *args, **options):
        today = timezone.localdate()
        queryset = Booking.objects.filter(
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            status=Booking.STATUS_DEPOSIT_PENDING,
            deposit_paid_at__isnull=True,
            deposit_deadline__isnull=False,
            deposit_deadline__lt=today,
        )
        cancelled_count = queryset.update(status=Booking.STATUS_CANCELLED, updated_at=timezone.now())
        self.stdout.write(self.style.SUCCESS(f"Cancelled {cancelled_count} unpaid deposit booking(s)."))
