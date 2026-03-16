from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "vaccine_date", "status", "created_at")
    search_fields = ("full_name", "phone")
    list_filter = ("status", "vaccine_date", "created_at")
    ordering = ("-created_at",)