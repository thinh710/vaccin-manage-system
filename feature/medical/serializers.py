from rest_framework import serializers
from .models import MedicalRecord


class MedicalRecordSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='booking.full_name', read_only=True)
    vaccine_name = serializers.CharField(source='booking.vaccine_name', read_only=True)

    class Meta:
        model = MedicalRecord
        fields = '__all__'
