from rest_framework import serializers

from .models import PostInjectionTracking, PreScreeningDeclaration, ScreeningResult, VaccinationLog


class PreScreeningDeclarationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreScreeningDeclaration
        fields = "__all__"
        read_only_fields = ["booking", "created_at", "updated_at"]


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
