import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from feature.assets.models import Supplier, Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.medical.models import OnlineEligibilityReview, PreScreeningDeclaration


class BookingApiTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name='Booking Supplier')
        self.vaccine = Vaccine.objects.create(
            name='COVID-19',
            manufacturer='Booking Pharma',
            batch_number='BOOK-001',
            quantity=30,
            minimum_stock=2,
            price=Decimal('150000.00'),
            expiration_date=timezone.localdate() + timedelta(days=60),
            supplier=self.supplier,
        )
        self.other_vaccine = Vaccine.objects.create(
            name='HPV',
            manufacturer='Booking Pharma',
            batch_number='BOOK-002',
            quantity=20,
            minimum_stock=2,
            price=Decimal('220000.00'),
            expiration_date=timezone.localdate() + timedelta(days=60),
            supplier=self.supplier,
        )
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

    def _login_as(self, user):
        session = self.client.session
        session['user_id'] = user.id
        session.save()

    def test_create_booking_sets_awaiting_eligibility_and_pricing(self):
        payload = {
            'vaccine_name': self.vaccine.name,
            'vaccine_date': str(timezone.localdate() + timedelta(days=5)),
            'dose_number': 1,
        }
        response = self.client.post(reverse('booking-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], Booking.STATUS_AWAITING_ELIGIBILITY)
        self.assertEqual(response.data['full_name'], self.user.full_name)
        self.assertEqual(response.data['user'], self.user.id)
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('150000.00'))
        self.assertEqual(Decimal(response.data['deposit_amount']), Decimal('30000.00'))
        self.assertEqual(
            response.data['deposit_deadline'],
            str(timezone.localdate() + timedelta(days=3)),
        )

    def test_citizen_cannot_create_duplicate_active_booking_same_day(self):
        payload = {
            'vaccine_name': self.vaccine.name,
            'vaccine_date': str(timezone.localdate() + timedelta(days=3)),
            'dose_number': 1,
        }
        first_response = self.client.post(reverse('booking-list-create'), payload, format='json')
        second_response = self.client.post(reverse('booking-list-create'), payload, format='json')

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_citizen_can_cancel_own_booking(self):
        booking = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=5),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()

        response = self.client.patch(
            reverse('booking-detail', kwargs={'booking_id': booking.id}),
            {'status': Booking.STATUS_CANCELLED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Booking.STATUS_CANCELLED)

    def test_confirmed_booking_vaccine_or_dose_change_returns_to_awaiting_eligibility(self):
        booking = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=5),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            deposit_paid_at=timezone.now(),
            deposit_note='Paid',
            eligibility_confirmed_at=timezone.now(),
        )
        booking.recalculate_financials()
        booking.deposit_paid_by = self.user
        booking.eligibility_confirmed_by = self.user
        booking.save()

        next_date = timezone.localdate() + timedelta(days=8)
        response = self.client.patch(
            reverse('booking-detail', kwargs={'booking_id': booking.id}),
            {
                'vaccine_name': self.other_vaccine.name,
                'vaccine_date': str(next_date),
                'dose_number': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.vaccine_name, self.other_vaccine.name)
        self.assertEqual(booking.status, Booking.STATUS_AWAITING_ELIGIBILITY)
        self.assertIsNone(booking.deposit_paid_at)
        self.assertIsNone(booking.deposit_paid_by)
        self.assertIsNone(booking.eligibility_confirmed_at)
        self.assertEqual(booking.deposit_deadline, next_date - timedelta(days=2))
        self.assertEqual(booking.deposit_amount, Decimal('44000.00'))

    def test_doctor_can_review_online_then_staff_can_confirm_deposit(self):
        staff = User.objects.create(
            full_name='Staff User',
            email='staff@example.com',
            password_hash=make_password('secret123'),
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        doctor = User.objects.create(
            full_name='Doctor User',
            email='doctor@example.com',
            password_hash=make_password('secret123'),
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=6),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()
        PreScreeningDeclaration.objects.create(
            booking=booking,
            has_severe_allergy=False,
            has_current_health_issue=False,
            had_recent_vaccination=False,
            uses_immunosuppressive_medication=False,
            has_pregnancy_or_breastfeeding_consideration=False,
        )
        self._login_as(doctor)

        eligibility_response = self.client.patch(
            reverse('booking-doctor-review', args=[booking.id]),
            {'decision': 'eligible', 'doctor_note': 'Dat coc duoc'},
            format='json',
        )
        self.assertEqual(eligibility_response.status_code, status.HTTP_200_OK)
        self.assertEqual(eligibility_response.data['status'], Booking.STATUS_DEPOSIT_PENDING)
        self.assertEqual(eligibility_response.data['online_review']['decision'], 'eligible')
        self.assertFalse(eligibility_response.data['can_doctor_review_online'])
        self.assertTrue(OnlineEligibilityReview.objects.filter(booking=booking, decision='eligible').exists())

        self._login_as(staff)

        deposit_response = self.client.patch(
            reverse('booking-confirm-deposit', args=[booking.id]),
            {'deposit_note': 'Nhan coc tai quay'},
            format='json',
        )
        self.assertEqual(deposit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(deposit_response.data['status'], Booking.STATUS_CONFIRMED)
        self.assertEqual(deposit_response.data['deposit_deadline_status'], 'paid')

    def test_citizen_cannot_access_doctor_review_or_deposit_endpoints(self):
        booking = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=5),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()
        PreScreeningDeclaration.objects.create(
            booking=booking,
            has_severe_allergy=False,
            has_current_health_issue=False,
            had_recent_vaccination=False,
            uses_immunosuppressive_medication=False,
            has_pregnancy_or_breastfeeding_consideration=False,
        )

        eligibility_response = self.client.patch(
            reverse('booking-doctor-review', args=[booking.id]),
            {'decision': 'eligible'},
            format='json',
        )
        deposit_response = self.client.patch(reverse('booking-confirm-deposit', args=[booking.id]))

        self.assertEqual(eligibility_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(deposit_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_detail_exposes_deposit_reminder_states(self):
        booking = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name=self.user.full_name,
            phone='0909000000',
            email=self.user.email,
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=3),
            dose_number=1,
            status=Booking.STATUS_DEPOSIT_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()

        response = self.client.get(reverse('booking-detail', kwargs={'booking_id': booking.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deposit_deadline_status'], 'warning')
        self.assertTrue(response.data['needs_deposit_reminder'])
        self.assertTrue(response.data['deposit_deadline_message'])

    def test_cancel_unpaid_deposits_command_cancels_only_overdue_online_bookings(self):
        overdue = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name='Overdue',
            phone='0909000123',
            email='overdue@example.com',
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=1),
            dose_number=1,
            status=Booking.STATUS_DEPOSIT_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            deposit_deadline=timezone.localdate() - timedelta(days=1),
        )
        paid = Booking.objects.create(
            user=self.user,
            vaccine=self.vaccine,
            full_name='Paid',
            phone='0909000456',
            email='paid@example.com',
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=1),
            dose_number=1,
            status=Booking.STATUS_DEPOSIT_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            deposit_deadline=timezone.localdate() - timedelta(days=1),
            deposit_paid_at=timezone.now(),
        )
        walkin = Booking.objects.create(
            full_name='Walkin',
            phone='0909000789',
            email='walkin@example.com',
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DEPOSIT_PENDING,
            booking_source=Booking.BOOKING_SOURCE_WALKIN,
            deposit_deadline=timezone.localdate() - timedelta(days=1),
        )

        call_command('cancel_unpaid_deposits')

        overdue.refresh_from_db()
        paid.refresh_from_db()
        walkin.refresh_from_db()
        self.assertEqual(overdue.status, Booking.STATUS_CANCELLED)
        self.assertEqual(paid.status, Booking.STATUS_DEPOSIT_PENDING)
        self.assertEqual(walkin.status, Booking.STATUS_DEPOSIT_PENDING)

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
        self._login_as(staff)

        response = self.client.post(
            reverse('booking-list-create'),
            {
                'full_name': 'Citizen Match',
                'phone': '0912444555',
                'email': citizen.email,
                'vaccine_name': self.vaccine.name,
                'vaccine_date': str(timezone.localdate() + timedelta(days=6)),
                'dose_number': 1,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user'], citizen.id)

    def test_admin_cannot_use_booking_patient_workflows(self):
        admin = User.objects.create(
            full_name='Inventory Admin',
            email='inventory-admin@example.com',
            password_hash=make_password('secret123'),
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            full_name='Patient Hidden From Admin',
            phone='0909000123',
            email='hidden@example.com',
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=1),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        session = self.client.session
        session['user_id'] = admin.id
        session.save()

        portal_response = self.client.get(reverse('booking-portal'))
        list_response = self.client.get(reverse('booking-list-create'))
        create_response = self.client.post(
            reverse('booking-list-create'),
            {
                'full_name': 'Admin Created Patient',
                'phone': '0911222333',
                'email': 'admin-created@example.com',
                'vaccine_name': self.vaccine.name,
                'vaccine_date': str(timezone.localdate() + timedelta(days=3)),
                'dose_number': 1,
            },
            format='json',
        )
        confirm_response = self.client.patch(reverse('booking-confirm-eligibility', args=[booking.id]))
        delete_response = self.client.delete(reverse('booking-detail', kwargs={'booking_id': booking.id}))

        self.assertEqual(portal_response.status_code, 302)
        self.assertEqual(portal_response['Location'], '/assets/')
        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(confirm_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)


class BookingCsrfTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name='CSRF Supplier')
        self.vaccine = Vaccine.objects.create(
            name='Flu',
            manufacturer='CSRF Pharma',
            batch_number='CSRF-001',
            quantity=15,
            minimum_stock=1,
            price=Decimal('125000.00'),
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )
        self.staff = User.objects.create(
            full_name='Staff CSRF',
            email='staff-csrf@example.com',
            password_hash=make_password('secret123'),
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        self.client = Client(enforce_csrf_checks=True)
        session = self.client.session
        session['user_id'] = self.staff.id
        session.save()

    def _csrf_headers(self):
        token = 'a' * 32
        self.client.cookies['csrftoken'] = token
        return {'HTTP_X_CSRFTOKEN': token}

    def test_booking_post_patch_delete_require_csrf_token(self):
        payload = {
            'full_name': 'CSRF Patient',
            'phone': '0911222333',
            'email': 'csrf-patient@example.com',
            'vaccine_name': self.vaccine.name,
            'vaccine_date': str(timezone.localdate() + timedelta(days=2)),
            'dose_number': 1,
        }

        missing_post = self.client.post(
            reverse('booking-list-create'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(missing_post.status_code, status.HTTP_403_FORBIDDEN)

        created = self.client.post(
            reverse('booking-list-create'),
            data=json.dumps(payload),
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        booking_id = created.json()['id']
        detail_url = reverse('booking-detail', kwargs={'booking_id': booking_id})

        missing_patch = self.client.patch(
            detail_url,
            data=json.dumps({'note': 'Need update'}),
            content_type='application/json',
        )
        self.assertEqual(missing_patch.status_code, status.HTTP_403_FORBIDDEN)

        patched = self.client.patch(
            detail_url,
            data=json.dumps({'note': 'Need update'}),
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)

        missing_delete = self.client.delete(detail_url)
        self.assertEqual(missing_delete.status_code, status.HTTP_403_FORBIDDEN)

        deleted = self.client.delete(detail_url, **self._csrf_headers())
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_booking_workflow_actions_require_csrf_token(self):
        self.staff.role = User.ROLE_DOCTOR
        self.staff.save(update_fields=['role'])
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Workflow Patient',
            phone='0911444555',
            email='workflow@example.com',
            vaccine_name=self.vaccine.name,
            vaccine_date=timezone.localdate() + timedelta(days=3),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()
        PreScreeningDeclaration.objects.create(
            booking=booking,
            has_severe_allergy=False,
            has_current_health_issue=False,
            had_recent_vaccination=False,
            uses_immunosuppressive_medication=False,
            has_pregnancy_or_breastfeeding_consideration=False,
        )

        eligibility_url = reverse('booking-doctor-review', args=[booking.id])
        missing_eligibility = self.client.patch(
            eligibility_url,
            data=json.dumps({'decision': 'eligible'}),
            content_type='application/json',
        )
        self.assertEqual(missing_eligibility.status_code, status.HTTP_403_FORBIDDEN)

        ok_eligibility = self.client.patch(
            eligibility_url,
            data=json.dumps({'decision': 'eligible'}),
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(ok_eligibility.status_code, status.HTTP_200_OK)

        self.staff.role = User.ROLE_STAFF
        self.staff.save(update_fields=['role'])

        deposit_url = reverse('booking-confirm-deposit', args=[booking.id])
        missing_deposit = self.client.patch(deposit_url)
        self.assertEqual(missing_deposit.status_code, status.HTTP_403_FORBIDDEN)

        ok_deposit = self.client.patch(
            deposit_url,
            data=json.dumps({'deposit_note': 'CSRF ok'}),
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(ok_deposit.status_code, status.HTTP_200_OK)


class BookingPortalSecurityTests(TestCase):
    def test_portal_table_uses_dom_text_nodes_for_booking_data(self):
        source = Path(__file__).resolve().parent / 'static' / 'booking' / 'js' / 'portal.js'
        script = source.read_text(encoding='utf-8')

        self.assertNotIn('row.innerHTML', script)
        self.assertIn('nameEl.textContent = booking.full_name', script)
        self.assertIn('phoneEl.textContent = booking.phone', script)

    def test_citizen_edit_forms_send_vaccine_and_dose_fields(self):
        portal_source = Path(__file__).resolve().parent / 'static' / 'booking' / 'js' / 'portal.js'
        dashboard_source = (
            Path(__file__).resolve().parents[1]
            / 'users'
            / 'static'
            / 'users'
            / 'js'
            / 'dashboard.js'
        )
        portal_script = portal_source.read_text(encoding='utf-8')
        dashboard_script = dashboard_source.read_text(encoding='utf-8')

        self.assertIn('vaccineNameInput.disabled = false', portal_script)
        self.assertIn('doseNumberInput.readOnly = false', portal_script)
        self.assertIn('vaccine_name: fullPayload.vaccine_name', portal_script)
        self.assertIn('dose_number: fullPayload.dose_number', portal_script)
        self.assertIn('setDashboardVaccineDisabled(!hasSelectableVaccines())', dashboard_script)
        self.assertIn('elements.doseNumber.readOnly = false', dashboard_script)
        self.assertIn('vaccine_name: payload.vaccine_name', dashboard_script)
        self.assertIn('dose_number: payload.dose_number', dashboard_script)

    def test_portal_exposes_pricing_and_reminder_hooks(self):
        template = (
            Path(__file__).resolve().parent
            / 'templates'
            / 'booking'
            / 'portal.html'
        ).read_text(encoding='utf-8')

        self.assertIn('selected-vaccine-price', template)
        self.assertIn('selected-deposit-amount', template)
        self.assertIn('selected-deposit-deadline', template)
        self.assertIn('portal-reminder', template)
        self.assertNotIn('doctor-review-form', template)
        self.assertIn('decl-severe-allergy', template)
        self.assertIn('decl-pregnancy-consideration', template)
