from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class BookingApiTests(APITestCase):
    def test_create_booking(self):
        payload = {
            'full_name': 'Nguyen Van A',
            'phone': '0909000000',
            'email': 'a@example.com',
            'vaccine_name': 'COVID-19',
            'vaccine_date': '2026-03-20',
            'dose_number': 1,
            'status': 'pending',
        }
        response = self.client.post(reverse('booking-list-create'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['full_name'], payload['full_name'])
