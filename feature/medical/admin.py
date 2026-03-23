from django.contrib import admin
from .models import ScreeningResult, VaccinationLog, PostInjectionTracking

@admin.register(ScreeningResult)
class ScreeningResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'temperature', 'blood_pressure', 'is_eligible', 'created_at')
    search_fields = ('booking__full_name',)
    list_filter = ('is_eligible',)

@admin.register(VaccinationLog)
class VaccinationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'vaccine_id', 'batch_number', 'injected_by', 'injection_time', 'dose_number')
    search_fields = ('booking__full_name', 'vaccine_id', 'batch_number', 'injected_by')

@admin.register(PostInjectionTracking)
class PostInjectionTrackingAdmin(admin.ModelAdmin):
    list_display = ('id', 'vaccination_log', 'reaction_status', 'created_at')
    search_fields = ('vaccination_log__booking__full_name',)
    list_filter = ('reaction_status',)
