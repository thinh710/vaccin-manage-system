from django.db import models

from feature.authentication.models import User
from feature.booking.models import Booking


class PreScreeningDeclaration(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="pre_screening")
    has_fever = models.BooleanField(default=False)
    has_allergy_history = models.BooleanField(default=False)
    has_chronic_condition = models.BooleanField(default=False)
    recent_symptoms = models.TextField(blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)
    has_severe_allergy = models.BooleanField(default=False)
    severe_allergy_details = models.TextField(blank=True, null=True)
    has_current_health_issue = models.BooleanField(default=False)
    current_health_issue_details = models.TextField(blank=True, null=True)
    had_recent_vaccination = models.BooleanField(default=False)
    recent_vaccination_details = models.TextField(blank=True, null=True)
    uses_immunosuppressive_medication = models.BooleanField(default=False)
    immunosuppressive_medication_details = models.TextField(blank=True, null=True)
    has_pregnancy_or_breastfeeding_consideration = models.BooleanField(default=False)
    pregnancy_or_breastfeeding_details = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pre-screening for Booking {self.booking.id}"


class OnlineEligibilityReview(models.Model):
    DECISION_ELIGIBLE = "eligible"
    DECISION_DELAYED = "delayed"
    DECISION_INELIGIBLE = "ineligible"

    DECISION_CHOICES = [
        (DECISION_ELIGIBLE, "Eligible"),
        (DECISION_DELAYED, "Delayed"),
        (DECISION_INELIGIBLE, "Ineligible"),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="online_review")
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default=DECISION_ELIGIBLE)
    doctor_note = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="online_eligibility_reviews",
    )
    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Online review for Booking {self.booking.id} - {self.decision}"


class ScreeningResult(models.Model):
    DECISION_ELIGIBLE = "eligible"
    DECISION_DELAYED = "delayed"
    DECISION_CANCELLED = "cancelled"

    DECISION_CHOICES = [
        (DECISION_ELIGIBLE, "Eligible"),
        (DECISION_DELAYED, "Delayed"),
        (DECISION_CANCELLED, "Cancelled"),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="screening_result")
    temperature = models.FloatField()
    blood_pressure = models.CharField(max_length=50)
    decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        default=DECISION_ELIGIBLE,
    )
    is_eligible = models.BooleanField(default=True)  # kept for legacy compatibility
    doctor_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Sync is_eligible from decision automatically
        self.is_eligible = (self.decision == self.DECISION_ELIGIBLE)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Screening for Booking {self.booking.id} - {self.decision}"


class VaccinationLog(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="vaccination_log")
    vaccine = models.ForeignKey(
        "assets.Vaccine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_logs",
    )
    batch_number = models.CharField(max_length=50, blank=True)
    injected_by = models.CharField(max_length=100)
    injection_time = models.DateTimeField(auto_now_add=True)
    dose_number = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"Vaccination {self.id} for Booking {self.booking.id}"


class PostInjectionTracking(models.Model):
    REACTION_NORMAL = "Normal"
    REACTION_MILD = "Mild"
    REACTION_SEVERE = "Severe"

    REACTION_CHOICES = [
        (REACTION_NORMAL, "Normal"),
        (REACTION_MILD, "Mild"),
        (REACTION_SEVERE, "Severe"),
    ]

    vaccination_log = models.OneToOneField(
        VaccinationLog,
        on_delete=models.CASCADE,
        related_name="post_tracking",
    )
    reaction_status = models.CharField(max_length=20, choices=REACTION_CHOICES, default=REACTION_NORMAL)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracking for Vaccination {self.vaccination_log.id} - {self.reaction_status}"
