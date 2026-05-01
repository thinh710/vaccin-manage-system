from rest_framework import serializers

from .models import (
    OnlineEligibilityReview,
    PostInjectionTracking,
    PreScreeningDeclaration,
    ScreeningResult,
    VaccinationLog,
)


class PreScreeningDeclarationSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        severe_allergy = attrs.get("has_severe_allergy", getattr(self.instance, "has_severe_allergy", False))
        severe_allergy_details = attrs.get(
            "severe_allergy_details",
            getattr(self.instance, "severe_allergy_details", ""),
        )
        current_health_issue = attrs.get(
            "has_current_health_issue",
            getattr(self.instance, "has_current_health_issue", False),
        )
        current_health_issue_details = attrs.get(
            "current_health_issue_details",
            getattr(self.instance, "current_health_issue_details", ""),
        )
        recent_vaccination = attrs.get(
            "had_recent_vaccination",
            getattr(self.instance, "had_recent_vaccination", False),
        )
        recent_vaccination_details = attrs.get(
            "recent_vaccination_details",
            getattr(self.instance, "recent_vaccination_details", ""),
        )
        immunosuppressive_medication = attrs.get(
            "uses_immunosuppressive_medication",
            getattr(self.instance, "uses_immunosuppressive_medication", False),
        )
        immunosuppressive_medication_details = attrs.get(
            "immunosuppressive_medication_details",
            getattr(self.instance, "immunosuppressive_medication_details", ""),
        )
        pregnancy_or_breastfeeding = attrs.get(
            "has_pregnancy_or_breastfeeding_consideration",
            getattr(self.instance, "has_pregnancy_or_breastfeeding_consideration", False),
        )
        pregnancy_or_breastfeeding_details = attrs.get(
            "pregnancy_or_breastfeeding_details",
            getattr(self.instance, "pregnancy_or_breastfeeding_details", ""),
        )

        detail_pairs = [
            (severe_allergy, severe_allergy_details, "severe_allergy_details"),
            (current_health_issue, current_health_issue_details, "current_health_issue_details"),
            (recent_vaccination, recent_vaccination_details, "recent_vaccination_details"),
            (
                immunosuppressive_medication,
                immunosuppressive_medication_details,
                "immunosuppressive_medication_details",
            ),
            (
                pregnancy_or_breastfeeding,
                pregnancy_or_breastfeeding_details,
                "pregnancy_or_breastfeeding_details",
            ),
        ]
        for checked, details, field_name in detail_pairs:
            if checked and not str(details or "").strip():
                raise serializers.ValidationError({field_name: "Vui long bo sung mo ta cho lua chon nay."})
        return attrs

    def _sync_legacy_fields(self, validated_data):
        current_health_issue_details = validated_data.get("current_health_issue_details") or ""
        immunosuppressive_details = validated_data.get("immunosuppressive_medication_details") or ""

        validated_data["has_allergy_history"] = validated_data.get("has_severe_allergy", False)
        validated_data["has_fever"] = validated_data.get("has_current_health_issue", False)
        validated_data["has_chronic_condition"] = validated_data.get("has_current_health_issue", False)
        validated_data["recent_symptoms"] = current_health_issue_details
        validated_data["current_medications"] = immunosuppressive_details
        return validated_data

    def create(self, validated_data):
        return super().create(self._sync_legacy_fields(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._sync_legacy_fields(validated_data))

    class Meta:
        model = PreScreeningDeclaration
        fields = "__all__"
        read_only_fields = ["booking", "created_at", "updated_at"]


class OnlineEligibilityReviewSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OnlineEligibilityReview
        fields = "__all__"
        read_only_fields = ["booking", "reviewed_by", "reviewed_at", "reviewed_by_name"]

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.full_name if obj.reviewed_by else ""


class ScreeningResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningResult
        fields = "__all__"


class VaccinationLogSerializer(serializers.ModelSerializer):
    vaccine_name = serializers.SerializerMethodField()

    class Meta:
        model = VaccinationLog
        fields = "__all__"

    def get_vaccine_name(self, obj):
        return obj.vaccine.name if obj.vaccine else None


class PostInjectionTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostInjectionTracking
        fields = "__all__"
