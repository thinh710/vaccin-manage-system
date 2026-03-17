from django.contrib import admin
from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'blood_group', 'is_fit_for_vaccination', 'created_at')
    search_fields = ('booking__full_name', 'emergency_contact_name', 'emergency_contact_phone')
    list_filter = ('blood_group', 'is_fit_for_vaccination')
