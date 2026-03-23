from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'phone', 'vaccine_name', 'vaccine_date', 'status', 'created_at')
    search_fields = ('full_name', 'phone', 'email', 'vaccine_name')
    list_filter = ('status', 'vaccine_name', 'vaccine_date')
