from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from feature.authentication.models import User


class BookingApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            full_name='Citizen User',
            email='citizen@example.com',
            phone_number='0909000000',
            password_hash=make_password('secret123'),
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

    def test_create_booking(self):
        payload = {
            'vaccine_name': 'COVID-19',
            'vaccine_date': str(timezone.localdate() + timedelta(days=2)),
            'dose_number': 1,
        }
        response = self.client.post(reverse('booking-list-create'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['full_name'], self.user.full_name)
        self.assertEqual(response.data['user'], self.user.id)

    def test_citizen_cannot_create_duplicate_active_booking_same_day(self):
        payload = {
            'vaccine_name': 'COVID-19',
            'vaccine_date': str(timezone.localdate() + timedelta(days=3)),
            'dose_number': 1,
        }
        first_response = self.client.post(reverse('booking-list-create'), payload, format='json')
        second_response = self.client.post(reverse('booking-list-create'), payload, format='json')

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_citizen_can_only_cancel_own_booking(self):
        create_response = self.client.post(
            reverse('booking-list-create'),
            {
                'vaccine_name': 'HPV',
                'vaccine_date': str(timezone.localdate() + timedelta(days=5)),
                'dose_number': 2,
            },
            format='json',
        )
        booking_id = create_response.data['id']

        response = self.client.patch(
            reverse('booking-detail', kwargs={'booking_id': booking_id}),
            {'status': 'cancelled'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cancelled')
