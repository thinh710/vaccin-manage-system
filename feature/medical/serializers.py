from rest_framework import serializers
from .models import ScreeningResult, VaccinationLog, PostInjectionTracking


class ScreeningResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningResult
        fields = '__all__'


class VaccinationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaccinationLog
        fields = '__all__'


class PostInjectionTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostInjectionTracking
        fields = '__all__'
