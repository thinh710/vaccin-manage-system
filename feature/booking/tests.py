from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from feature.authentication.models import User
from feature.booking.models import Booking


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

    def test_citizen_can_update_allowed_booking_fields(self):
        booking = Booking.objects.create(
            user=self.user,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name='COVID-19',
            vaccine_date=timezone.localdate() + timedelta(days=2),
            dose_number=1,
            status=Booking.STATUS_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )

        next_date = timezone.localdate() + timedelta(days=4)
        response = self.client.patch(
            reverse('booking-detail', kwargs={'booking_id': booking.id}),
            {
                'phone': '0911222333',
                'vaccine_date': str(next_date),
                'note': 'Doi lich ca nhan',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.phone, '0911222333')
        self.assertEqual(booking.vaccine_date, next_date)
        self.assertEqual(booking.note, 'Doi lich ca nhan')
        self.assertEqual(response.data['full_name'], self.user.full_name)

    def test_booking_detail_can_reschedule_turns_false_after_replacement_exists(self):
        source = Booking.objects.create(
            user=self.user,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name='COVID-19',
            vaccine_date=timezone.localdate() + timedelta(days=2),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )

        detail_url = reverse('booking-detail', kwargs={'booking_id': source.id})
        first_response = self.client.get(detail_url)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data['can_reschedule'])

        Booking.objects.create(
            user=self.user,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name='COVID-19',
            vaccine_date=timezone.localdate() + timedelta(days=5),
            dose_number=1,
            status=Booking.STATUS_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            rescheduled_from=source,
        )

        second_response = self.client.get(detail_url)

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertFalse(second_response.data['can_reschedule'])

    def test_staff_created_booking_without_matching_citizen_is_not_owned_by_staff(self):
        staff = User.objects.create(
            full_name='Staff User',
            email='staff@example.com',
            password_hash=make_password('secret123'),
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        session = self.client.session
        session['user_id'] = staff.id
        session.save()

        response = self.client.post(
            reverse('booking-list-create'),
            {
                'full_name': 'Guest Patient',
                'phone': '0911222333',
                'email': 'guest@example.com',
                'vaccine_name': 'Flu',
                'vaccine_date': str(timezone.localdate() + timedelta(days=4)),
                'dose_number': 1,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['user'])

    def test_staff_created_booking_links_matching_citizen_by_email(self):
        staff = User.objects.create(
            full_name='Staff User',
            email='staff-2@example.com',
            password_hash=make_password('secret123'),
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        citizen = User.objects.create(
            full_name='Citizen Match',
            email='citizen-match@example.com',
            phone_number='0912444555',
            password_hash=make_password('secret123'),
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        session = self.client.session
        session['user_id'] = staff.id
        session.save()

        response = self.client.post(
            reverse('booking-list-create'),
            {
                'full_name': 'Citizen Match',
                'phone': '0912444555',
                'email': citizen.email,
                'vaccine_name': 'Flu',
                'vaccine_date': str(timezone.localdate() + timedelta(days=6)),
                'dose_number': 1,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user'], citizen.id)
