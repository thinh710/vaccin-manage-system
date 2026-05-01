import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from feature.assets.models import Supplier, Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.medical.models import (
    OnlineEligibilityReview,
    PostInjectionTracking,
    PreScreeningDeclaration,
    ScreeningResult,
    VaccinationLog,
)


class MedicalApiTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name='Flow Supplier')
        self.vaccine = Vaccine.objects.create(
            name='Flu',
            manufacturer='Flow Pharma',
            batch_number='FLOW-001',
            quantity=5,
            minimum_stock=1,
            price=Decimal('175000.00'),
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )

    def _login_as(self, user):
        session = self.client.session
        session['user_id'] = user.id
        session.save()

    def _create_ready_booking(self, vaccine_name='Flu'):
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Ready Patient',
            phone='0909000999',
            email='ready@example.com',
            vaccine_name=vaccine_name,
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_READY_TO_INJECT,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()
        return booking

    def test_standard_online_booking_lifecycle_completes_and_decrements_stock(self):
        citizen = User.objects.create(
            full_name='Citizen Flow',
            email='citizen-flow@example.com',
            phone_number='0912000111',
            password_hash='x',
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        staff = User.objects.create(
            full_name='Staff Flow',
            email='staff-flow@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        doctor = User.objects.create(
            full_name='Doctor Flow',
            email='doctor-flow@example.com',
            password_hash='x',
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )

        self._login_as(citizen)
        booking_response = self.client.post(
            reverse('booking-list-create'),
            {
                'vaccine_name': 'Flu',
                'vaccine_date': timezone.localdate() + timedelta(days=4),
                'dose_number': 1,
                'note': 'Online booking',
            },
            format='json',
        )
        self.assertEqual(booking_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(booking_response.data['status'], Booking.STATUS_AWAITING_ELIGIBILITY)
        booking_id = booking_response.data['id']

        declaration_response = self.client.post(
            reverse('medical-pre-screening', args=[booking_id]),
            {
                'has_severe_allergy': False,
                'severe_allergy_details': '',
                'has_current_health_issue': False,
                'current_health_issue_details': '',
                'had_recent_vaccination': False,
                'recent_vaccination_details': '',
                'uses_immunosuppressive_medication': False,
                'immunosuppressive_medication_details': '',
                'has_pregnancy_or_breastfeeding_consideration': False,
                'pregnancy_or_breastfeeding_details': '',
                'note': 'Declared online',
            },
            format='json',
        )
        self.assertEqual(declaration_response.status_code, status.HTTP_201_CREATED)

        self._login_as(doctor)
        eligibility_response = self.client.patch(
            reverse('booking-doctor-review', args=[booking_id]),
            {'decision': 'eligible', 'doctor_note': 'Online eligible'},
            format='json',
        )
        self.assertEqual(eligibility_response.status_code, status.HTTP_200_OK)
        self.assertEqual(eligibility_response.data['status'], Booking.STATUS_DEPOSIT_PENDING)
        self.assertTrue(OnlineEligibilityReview.objects.filter(booking_id=booking_id, decision='eligible').exists())

        self._login_as(staff)
        deposit_response = self.client.patch(
            reverse('booking-confirm-deposit', args=[booking_id]),
            {'deposit_note': 'Manual confirmation'},
            format='json',
        )
        self.assertEqual(deposit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(deposit_response.data['status'], Booking.STATUS_CONFIRMED)

        checkin_response = self.client.patch(reverse('medical-check-in', args=[booking_id]))
        self.assertEqual(checkin_response.status_code, status.HTTP_200_OK)

        self._login_as(doctor)
        screening_response = self.client.post(
            reverse('medical-screening'),
            {
                'booking': booking_id,
                'temperature': 36.7,
                'blood_pressure': '120/80',
                'decision': 'eligible',
                'doctor_note': 'Fit for vaccination',
            },
            format='json',
        )
        self.assertEqual(screening_response.status_code, status.HTTP_201_CREATED)

        self._login_as(staff)
        inject_response = self.client.post(
            reverse('medical-inject'),
            {
                'booking': booking_id,
                'injected_by': 'Staff Flow',
                'dose_number': 1,
            },
            format='json',
        )
        self.assertIn(inject_response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        monitor_response = self.client.post(
            reverse('medical-monitor'),
            {
                'booking': booking_id,
                'reaction_status': 'Normal',
                'notes': 'Observed for 30 minutes',
            },
            format='json',
        )
        self.assertEqual(monitor_response.status_code, status.HTTP_201_CREATED)

        booking = Booking.objects.get(pk=booking_id)
        self.vaccine.refresh_from_db()

        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertEqual(self.vaccine.quantity, 4)
        self.assertTrue(PreScreeningDeclaration.objects.filter(booking=booking).exists())
        self.assertTrue(ScreeningResult.objects.filter(booking=booking, decision='eligible').exists())
        self.assertTrue(VaccinationLog.objects.filter(booking=booking).exists())
        self.assertTrue(PostInjectionTracking.objects.filter(vaccination_log__booking=booking).exists())

    def test_check_in_rejects_booking_that_has_not_completed_deposit(self):
        staff = User.objects.create(
            full_name='Staff Guard',
            email='staff-guard@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Deposit Pending',
            phone='0909111222',
            email='deposit-pending@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DEPOSIT_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.save()
        self._login_as(staff)

        response = self.client.patch(reverse('medical-check-in', args=[booking.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_DEPOSIT_PENDING)

    def test_inject_rejects_explicit_vaccine_id_when_out_of_stock_or_expired(self):
        staff = User.objects.create(
            full_name='Staff Inject Guard',
            email='staff-inject-guard@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        out_of_stock = Vaccine.objects.create(
            name='Flu',
            manufacturer='Flow Pharma',
            batch_number='EMPTY-001',
            quantity=0,
            minimum_stock=1,
            price=Decimal('175000.00'),
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )
        expired = Vaccine.objects.create(
            name='Flu',
            manufacturer='Flow Pharma',
            batch_number='EXPIRED-001',
            quantity=5,
            minimum_stock=1,
            price=Decimal('175000.00'),
            expiration_date=timezone.localdate() - timedelta(days=1),
            supplier=self.supplier,
        )

        self._login_as(staff)
        booking = self._create_ready_booking()
        out_of_stock_response = self.client.post(
            reverse('medical-inject'),
            {
                'booking': booking.id,
                'vaccine': out_of_stock.id,
                'injected_by': 'Staff Inject Guard',
                'dose_number': 1,
            },
            format='json',
        )
        self.assertEqual(out_of_stock_response.status_code, status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_READY_TO_INJECT)
        self.assertFalse(VaccinationLog.objects.filter(booking=booking).exists())

        expired_response = self.client.post(
            reverse('medical-inject'),
            {
                'booking': booking.id,
                'vaccine': expired.id,
                'injected_by': 'Staff Inject Guard',
                'dose_number': 1,
            },
            format='json',
        )
        self.assertEqual(expired_response.status_code, status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_READY_TO_INJECT)
        self.assertFalse(VaccinationLog.objects.filter(booking=booking).exists())

    def test_valid_inject_decrements_once_even_when_existing_log_is_updated(self):
        staff = User.objects.create(
            full_name='Staff Inject',
            email='staff-inject@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        booking = self._create_ready_booking()
        self._login_as(staff)

        first_response = self.client.post(
            reverse('medical-inject'),
            {
                'booking': booking.id,
                'vaccine': self.vaccine.id,
                'injected_by': 'Staff Inject',
                'dose_number': 1,
            },
            format='json',
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 4)

        booking.status = Booking.STATUS_READY_TO_INJECT
        booking.save(update_fields=['status', 'updated_at'])
        second_response = self.client.post(
            reverse('medical-inject'),
            {
                'booking': booking.id,
                'vaccine': self.vaccine.id,
                'injected_by': 'Staff Inject Again',
                'dose_number': 1,
            },
            format='json',
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.vaccine.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 4)
        self.assertEqual(booking.status, Booking.STATUS_IN_OBSERVATION)

    def test_doctor_can_review_online_but_cannot_confirm_deposit_or_check_in(self):
        doctor = User.objects.create(
            full_name='Doctor Confirm Only',
            email='doctor-confirm@example.com',
            password_hash='x',
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Booking Pending',
            phone='0909000111',
            email='pending@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
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
            {'decision': 'eligible'},
            format='json',
        )
        deposit_response = self.client.patch(reverse('booking-confirm-deposit', args=[booking.id]))
        checkin_response = self.client.patch(reverse('medical-check-in', args=[booking.id]))

        self.assertEqual(eligibility_response.status_code, status.HTTP_200_OK)
        self.assertEqual(deposit_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(checkin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_view_today_bookings_list(self):
        doctor = User.objects.create(
            full_name='Doctor Viewer',
            email='doctor-viewer@example.com',
            password_hash='x',
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Booking Today',
            phone='0909000222',
            email='today@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        booking.recalculate_financials()
        booking.deposit_paid_at = timezone.now()
        booking.save()

        self._login_as(doctor)
        response = self.client.get(reverse('medical-today'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], booking.id)

    def test_doctor_online_review_can_mark_delayed_or_ineligible(self):
        doctor = User.objects.create(
            full_name='Doctor Review',
            email='doctor-review@example.com',
            password_hash='x',
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        delayed_booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Delayed Candidate',
            phone='0909000998',
            email='delayed-candidate@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate() + timedelta(days=5),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        delayed_booking.recalculate_financials()
        delayed_booking.save()
        ineligible_booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Ineligible Candidate',
            phone='0909000997',
            email='ineligible-candidate@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate() + timedelta(days=6),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        ineligible_booking.recalculate_financials()
        ineligible_booking.save()
        for booking in (delayed_booking, ineligible_booking):
            PreScreeningDeclaration.objects.create(
                booking=booking,
                has_severe_allergy=False,
                has_current_health_issue=False,
                had_recent_vaccination=False,
                uses_immunosuppressive_medication=False,
                has_pregnancy_or_breastfeeding_consideration=False,
            )

        self._login_as(doctor)
        delayed_response = self.client.patch(
            reverse('booking-doctor-review', args=[delayed_booking.id]),
            {'decision': 'delayed', 'doctor_note': 'Can theo doi them'},
            format='json',
        )
        ineligible_response = self.client.patch(
            reverse('booking-doctor-review', args=[ineligible_booking.id]),
            {'decision': 'ineligible', 'doctor_note': 'Khong phu hop'},
            format='json',
        )

        self.assertEqual(delayed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(delayed_response.data['status'], Booking.STATUS_DELAYED)
        self.assertEqual(ineligible_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ineligible_response.data['status'], Booking.STATUS_INELIGIBLE)

    def test_updating_declaration_after_online_review_resets_review_and_deposit(self):
        citizen = User.objects.create(
            full_name='Citizen Reset',
            email='citizen-reset@example.com',
            password_hash='x',
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            user=citizen,
            vaccine=self.vaccine,
            full_name='Citizen Reset',
            phone='0909000667',
            email=citizen.email,
            vaccine_name='Flu',
            vaccine_date=timezone.localdate() + timedelta(days=5),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            deposit_paid_at=timezone.now(),
            deposit_note='Paid',
            eligibility_confirmed_at=timezone.now(),
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
        OnlineEligibilityReview.objects.create(
            booking=booking,
            decision=OnlineEligibilityReview.DECISION_ELIGIBLE,
            doctor_note='Ready',
        )

        self._login_as(citizen)
        response = self.client.patch(
            reverse('medical-pre-screening', args=[booking.id]),
            {
                'has_current_health_issue': True,
                'current_health_issue_details': 'Moi bi sot',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_AWAITING_ELIGIBILITY)
        self.assertIsNone(booking.deposit_paid_at)
        self.assertIsNone(booking.eligibility_confirmed_at)
        self.assertFalse(OnlineEligibilityReview.objects.filter(booking=booking).exists())

    def test_admin_cannot_access_patient_or_medical_workflow_apis(self):
        admin = User.objects.create(
            full_name='Inventory Only Admin',
            email='inventory-only-admin@example.com',
            password_hash='x',
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
        )
        awaiting = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Awaiting Patient',
            phone='0909000333',
            email='awaiting@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        confirmed = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Confirmed Patient',
            phone='0909000444',
            email='confirmed@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        confirmed.recalculate_financials()
        confirmed.deposit_paid_at = timezone.now()
        confirmed.save()
        ready = self._create_ready_booking()
        delayed = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Delayed Patient',
            phone='0909000555',
            email='delayed@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        same_email_booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Same Email Patient',
            phone='0909000777',
            email=admin.email,
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        in_observation = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Observation Patient',
            phone='0909000666',
            email='observation@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_IN_OBSERVATION,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        VaccinationLog.objects.create(
            booking=in_observation,
            vaccine=self.vaccine,
            batch_number=self.vaccine.batch_number,
            injected_by='Staff',
            dose_number=1,
        )

        self._login_as(admin)

        self.assertEqual(self.client.get(reverse('medical-today')).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.get(reverse('medical-pre-screening', args=[same_email_booking.id])).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(reverse('booking-confirm-eligibility', args=[awaiting.id])).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(reverse('medical-check-in', args=[confirmed.id])).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                reverse('medical-screening'),
                {
                    'booking': confirmed.id,
                    'temperature': 36.8,
                    'blood_pressure': '120/80',
                    'decision': 'eligible',
                    'doctor_note': 'Blocked',
                },
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                reverse('medical-inject'),
                {
                    'booking': ready.id,
                    'vaccine': self.vaccine.id,
                    'injected_by': 'Admin',
                    'dose_number': 1,
                },
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                reverse('medical-monitor'),
                {'booking': in_observation.id, 'reaction_status': 'Normal', 'notes': 'Blocked'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                reverse('medical-walkin'),
                {
                    'full_name': 'Walkin Blocked',
                    'phone': '0911222444',
                    'email': 'walkin-blocked@example.com',
                    'vaccine_name': 'Flu',
                    'vaccine_date': str(timezone.localdate()),
                    'dose_number': 1,
                },
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                reverse('medical-reschedule', args=[delayed.id]),
                {'vaccine_date': timezone.localdate() + timedelta(days=2)},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_check_in_requires_pre_screening_before_customer_can_enter_day_of_flow(self):
        staff = User.objects.create(
            full_name='Staff Missing Declaration',
            email='staff-missing@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        doctor = User.objects.create(
            full_name='Doctor Missing Declaration',
            email='doctor-missing@example.com',
            password_hash='x',
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Khach Chua Khai Bao',
            phone='0912333444',
            email='missing@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            deposit_paid_at=timezone.now(),
        )
        booking.recalculate_financials()
        booking.save()

        self._login_as(staff)
        checkin_response = self.client.patch(reverse('medical-check-in', args=[booking.id]))
        self.assertEqual(checkin_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('khai bao', checkin_response.data['detail'].lower())

        self._login_as(doctor)
        blocked_screening_response = self.client.post(
            reverse('medical-screening'),
            {
                'booking': booking.id,
                'temperature': 36.8,
                'blood_pressure': '120/80',
                'decision': 'eligible',
                'doctor_note': 'Should be blocked first',
            },
            format='json',
        )
        self.assertEqual(blocked_screening_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pre_screening_get_returns_envelope_with_declaration_and_screening_result(self):
        citizen = User.objects.create(
            full_name='Citizen Envelope',
            email='citizen-envelope@example.com',
            password_hash='x',
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            user=citizen,
            vaccine=self.vaccine,
            full_name='Citizen Envelope',
            phone='0912555666',
            email=citizen.email,
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CHECKED_IN,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        declaration = PreScreeningDeclaration.objects.create(
            booking=booking,
            has_severe_allergy=True,
            severe_allergy_details='Di ung thanh phan A',
            has_current_health_issue=True,
            current_health_issue_details='Ho nhe',
            had_recent_vaccination=False,
            recent_vaccination_details='',
            uses_immunosuppressive_medication=True,
            immunosuppressive_medication_details='Vitamin C',
            has_pregnancy_or_breastfeeding_consideration=False,
            pregnancy_or_breastfeeding_details='',
            note='Da khai bao',
        )
        online_review = OnlineEligibilityReview.objects.create(
            booking=booking,
            decision=OnlineEligibilityReview.DECISION_ELIGIBLE,
            doctor_note='Duoc tiep tuc',
        )
        screening_result = ScreeningResult.objects.create(
            booking=booking,
            temperature=36.6,
            blood_pressure='118/78',
            decision=ScreeningResult.DECISION_ELIGIBLE,
            doctor_note='Dat dieu kien',
        )

        self._login_as(citizen)
        response = self.client.get(reverse('medical-pre-screening', args=[booking.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['booking'], booking.id)
        self.assertEqual(response.data['declaration']['id'], declaration.id)
        self.assertTrue(response.data['declaration']['has_severe_allergy'])
        self.assertEqual(response.data['declaration']['current_health_issue_details'], 'Ho nhe')
        self.assertEqual(response.data['online_review']['id'], online_review.id)
        self.assertEqual(response.data['online_review']['decision'], OnlineEligibilityReview.DECISION_ELIGIBLE)
        self.assertEqual(response.data['screening_result']['id'], screening_result.id)
        self.assertEqual(response.data['screening_result']['decision'], ScreeningResult.DECISION_ELIGIBLE)
        self.assertEqual(response.data['screening_result']['doctor_note'], 'Dat dieu kien')

    def test_pre_screening_get_returns_null_envelope_when_data_missing(self):
        citizen = User.objects.create(
            full_name='Citizen Empty Envelope',
            email='citizen-empty-envelope@example.com',
            password_hash='x',
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            user=citizen,
            vaccine=self.vaccine,
            full_name='Citizen Empty Envelope',
            phone='0912777888',
            email=citizen.email,
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )

        self._login_as(citizen)
        response = self.client.get(reverse('medical-pre-screening', args=[booking.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['booking'], booking.id)
        self.assertIsNone(response.data['declaration'])
        self.assertIsNone(response.data['online_review'])
        self.assertIsNone(response.data['screening_result'])

    def test_staff_reschedule_restarts_booking_from_awaiting_eligibility(self):
        staff = User.objects.create(
            full_name='Staff',
            email='staff@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        source = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Tran Thi B',
            phone='0911000000',
            email='b@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        PreScreeningDeclaration.objects.create(
            booking=source,
            has_current_health_issue=True,
            current_health_issue_details='Sot',
        )
        self._login_as(staff)

        response = self.client.post(
            reverse('medical-reschedule', args=[source.id]),
            {'vaccine_date': timezone.localdate() + timedelta(days=3)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_booking = Booking.objects.get(pk=response.data['id'])
        self.assertEqual(new_booking.status, Booking.STATUS_AWAITING_ELIGIBILITY)
        self.assertEqual(new_booking.booking_source, Booking.BOOKING_SOURCE_ONLINE)
        self.assertEqual(new_booking.rescheduled_from_id, source.id)
        self.assertTrue(hasattr(new_booking, 'pre_screening'))
        self.assertTrue(new_booking.pre_screening.has_current_health_issue)

    def test_reschedule_rejects_past_date(self):
        staff = User.objects.create(
            full_name='Staff Past Date',
            email='staff-past@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        source = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Tran Thi C',
            phone='0911333444',
            email='c@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        self._login_as(staff)

        response = self.client.post(
            reverse('medical-reschedule', args=[source.id]),
            {'vaccine_date': timezone.localdate() - timedelta(days=1)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('vaccine_date', response.data)

    def test_staff_reschedule_reuses_booking_validation_for_duplicate_active_booking(self):
        staff = User.objects.create(
            full_name='Staff Duplicate Guard',
            email='staff-duplicate@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        citizen = User.objects.create(
            full_name='Citizen Duplicate Guard',
            email='citizen-duplicate@example.com',
            password_hash='x',
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        target_date = timezone.localdate() + timedelta(days=5)
        source = Booking.objects.create(
            user=citizen,
            vaccine=self.vaccine,
            full_name='Citizen Duplicate Guard',
            phone='0911000111',
            email=citizen.email,
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        Booking.objects.create(
            user=citizen,
            vaccine=self.vaccine,
            full_name='Citizen Duplicate Guard',
            phone='0911000111',
            email=citizen.email,
            vaccine_name='Flu',
            vaccine_date=target_date,
            dose_number=1,
            status=Booking.STATUS_AWAITING_ELIGIBILITY,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        self._login_as(staff)

        response = self.client.post(
            reverse('medical-reschedule', args=[source.id]),
            {'vaccine_date': target_date},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)

    def test_citizen_can_reschedule_delayed_booking_matched_by_email(self):
        citizen = User.objects.create(
            full_name='Citizen',
            email='citizen@example.com',
            password_hash='x',
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        source = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Citizen',
            phone='0911222333',
            email='citizen@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        self._login_as(citizen)

        response = self.client.post(
            reverse('medical-reschedule', args=[source.id]),
            {'vaccine_date': timezone.localdate() + timedelta(days=5)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_booking = Booking.objects.get(pk=response.data['id'])
        self.assertEqual(new_booking.status, Booking.STATUS_AWAITING_ELIGIBILITY)
        self.assertEqual(new_booking.rescheduled_from_id, source.id)

    def test_reschedule_rejects_second_replacement_for_same_source(self):
        staff = User.objects.create(
            full_name='Staff Second Guard',
            email='staff-second-guard@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        source = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Tran Thi Guard',
            phone='0911444555',
            email='guard@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        self._login_as(staff)

        first_response = self.client.post(
            reverse('medical-reschedule', args=[source.id]),
            {'vaccine_date': timezone.localdate() + timedelta(days=3)},
            format='json',
        )
        second_response = self.client.post(
            reverse('medical-reschedule', args=[source.id]),
            {'vaccine_date': timezone.localdate() + timedelta(days=4)},
            format='json',
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(source.rescheduled_bookings.exists())


class MedicalCsrfTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name='CSRF Supplier')
        self.vaccine = Vaccine.objects.create(
            name='Flu',
            manufacturer='CSRF Pharma',
            batch_number='CSRF-001',
            quantity=3,
            minimum_stock=1,
            price=Decimal('90000.00'),
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )
        self.staff = User.objects.create(
            full_name='Staff CSRF',
            email='medical-staff-csrf@example.com',
            password_hash='x',
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        self.client = Client(enforce_csrf_checks=True)
        session = self.client.session
        session['user_id'] = self.staff.id
        session.save()

    def _csrf_headers(self):
        token = 'b' * 32
        self.client.cookies['csrftoken'] = token
        return {'HTTP_X_CSRFTOKEN': token}

    def test_check_in_requires_csrf_token(self):
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Checkin CSRF',
            phone='0909000111',
            email='checkin-csrf@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
            deposit_paid_at=timezone.now(),
        )
        PreScreeningDeclaration.objects.create(
            booking=booking,
            has_severe_allergy=False,
            has_current_health_issue=False,
            had_recent_vaccination=False,
            uses_immunosuppressive_medication=False,
            has_pregnancy_or_breastfeeding_consideration=False,
        )
        url = reverse('medical-check-in', args=[booking.id])

        missing = self.client.patch(url)
        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)

        ok = self.client.patch(url, **self._csrf_headers())
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

    def test_inject_requires_csrf_token(self):
        booking = Booking.objects.create(
            vaccine=self.vaccine,
            full_name='Inject CSRF',
            phone='0909000222',
            email='inject-csrf@example.com',
            vaccine_name='Flu',
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_READY_TO_INJECT,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        payload = {
            'booking': booking.id,
            'vaccine': self.vaccine.id,
            'injected_by': 'Staff CSRF',
            'dose_number': 1,
        }
        url = reverse('medical-inject')

        missing = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)

        ok = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            **self._csrf_headers(),
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)


class MedicalFrontendSecurityTests(TestCase):
    def test_medical_dashboard_does_not_embed_patient_names_in_inline_handlers(self):
        source = Path(__file__).resolve().parent / 'static' / 'medical' / 'js' / 'medical.js'
        script = source.read_text(encoding='utf-8')

        self.assertNotIn('onclick="openScreeningForm', script)
        self.assertNotIn('onclick="openInjectionForm', script)
        self.assertNotIn('onclick="openMonitoringForm', script)
        self.assertNotIn('getActionButton', script)
        self.assertIn('getActionControls', script)

    def test_patient_list_uses_sortable_paginated_table(self):
        feature_dir = Path(__file__).resolve().parent
        script = (feature_dir / 'static' / 'medical' / 'js' / 'medical.js').read_text(encoding='utf-8')
        styles = (feature_dir / 'static' / 'medical' / 'css' / 'medical.css').read_text(encoding='utf-8')
        template = (feature_dir / 'templates' / 'medical' / 'medical.html').read_text(encoding='utf-8')

        self.assertIn('const PATIENTS_PER_PAGE = 5;', script)
        self.assertIn('let currentPatientPage = 1;', script)
        self.assertIn('setupPatientSort();', script)
        self.assertIn("let currentPatientSort = { key: 'vaccine_date', direction: 'asc' };", script)
        self.assertIn('filteredBookings.slice(startIndex, startIndex + PATIENTS_PER_PAGE)', script)
        self.assertIn('renderPatientPagination', script)
        self.assertIn('renderPatientRow(booking)', script)
        self.assertIn('class="patient-table"', template)
        self.assertIn('data-sort-key="deposit_state"', template)
        self.assertIn('id="patient-pagination"', template)
        self.assertIn('.medical-page .patient-table', styles)
        self.assertIn('.medical-page .patient-sort', styles)
        self.assertIn('.medical-page .patient-pagination', styles)
        self.assertNotIn('#patient-list::-webkit-scrollbar', styles)
        self.assertNotIn('scrollbar-gutter', styles)

    def test_medical_dashboard_uses_new_declaration_questions_and_moves_online_review_into_medical(self):
        script = (Path(__file__).resolve().parent / 'static' / 'medical' / 'js' / 'medical.js').read_text(encoding='utf-8')
        template = (Path(__file__).resolve().parent / 'templates' / 'medical' / 'medical.html').read_text(encoding='utf-8')

        self.assertIn("setupMedicalDeclarationForms()", script)
        self.assertIn("prefixKey: 'severe-allergy'", script)
        self.assertIn("prefixKey: 'pregnancy-consideration'", script)
        self.assertIn("makeActionButton('Duyet online'", script)
        self.assertIn("id=\"form-doctor-review\"", template)
        self.assertNotIn('missing-prescreen-modal', template)

