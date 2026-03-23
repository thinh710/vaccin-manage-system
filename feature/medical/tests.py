from feature.booking.models import Booking
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class MedicalApiTests(APITestCase):
    def test_create_medical_record(self):
        booking = Booking.objects.create(
            full_name='Tran Thi B',
            phone='0911000000',
            email='b@example.com',
            vaccine_name='Flu',
            vaccine_date='2026-03-21',
            dose_number=1,
        )
        payload = {
            'booking': booking.id,
            'blood_group': 'O+',
            'allergies': 'Penicillin',
            'medical_history': 'No major surgery',
            'is_fit_for_vaccination': True,
        }
        response = self.client.post(reverse('medical-record-list-create'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['booking'], booking.id)
