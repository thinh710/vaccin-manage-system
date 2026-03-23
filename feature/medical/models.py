from django.db import models
from feature.booking.models import Booking

class ScreeningResult(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='screening_result')
    temperature = models.FloatField()
    blood_pressure = models.CharField(max_length=50)
    is_eligible = models.BooleanField()
    doctor_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Screening for Booking {self.booking.id} - Eligible: {self.is_eligible}"


class VaccinationLog(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='vaccination_log')
    vaccine_id = models.CharField(max_length=100)  # Mock for now
    batch_number = models.CharField(max_length=50)  # Mock for now
    injected_by = models.CharField(max_length=100)
    injection_time = models.DateTimeField(auto_now_add=True)
    dose_number = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"Vaccination {self.id} for Booking {self.booking.id}"


class PostInjectionTracking(models.Model):
    REACTION_NORMAL = 'Normal'
    REACTION_MILD = 'Mild'
    REACTION_SEVERE = 'Severe'
    
    REACTION_CHOICES = [
        (REACTION_NORMAL, 'Normal'),
        (REACTION_MILD, 'Mild'),
        (REACTION_SEVERE, 'Severe'),
    ]

    vaccination_log = models.OneToOneField(VaccinationLog, on_delete=models.CASCADE, related_name='post_tracking')
    reaction_status = models.CharField(max_length=20, choices=REACTION_CHOICES, default=REACTION_NORMAL)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracking for Vaccination {self.vaccination_log.id} - {self.reaction_status}"
