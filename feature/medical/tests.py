from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from feature.assets.models import Supplier, Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.medical.models import PostInjectionTracking, PreScreeningDeclaration, ScreeningResult, VaccinationLog


class MedicalApiTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="Flow Supplier")
        self.vaccine = Vaccine.objects.create(
            name="Flu",
            manufacturer="Flow Pharma",
            batch_number="FLOW-001",
            quantity=5,
            minimum_stock=1,
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )

    def _login_as(self, user):
        session = self.client.session
        session["user_id"] = user.id
        session.save()

    def test_standard_online_booking_lifecycle_completes_and_decrements_stock(self):
        citizen = User.objects.create(
            full_name="Citizen Flow",
            email="citizen-flow@example.com",
            phone_number="0912000111",
            password_hash="x",
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        staff = User.objects.create(
            full_name="Staff Flow",
            email="staff-flow@example.com",
            password_hash="x",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        doctor = User.objects.create(
            full_name="Doctor Flow",
            email="doctor-flow@example.com",
            password_hash="x",
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )

        self._login_as(citizen)
        booking_response = self.client.post(
            reverse("booking-list-create"),
            {
                "vaccine_name": "Flu",
                "vaccine_date": timezone.localdate(),
                "dose_number": 1,
                "note": "Online booking",
            },
            format="json",
        )
        self.assertEqual(booking_response.status_code, status.HTTP_201_CREATED)
        booking_id = booking_response.data["id"]

        declaration_response = self.client.post(
            reverse("medical-pre-screening", args=[booking_id]),
            {
                "has_fever": False,
                "has_allergy_history": False,
                "has_chronic_condition": False,
                "recent_symptoms": "",
                "current_medications": "",
                "note": "Declared online",
            },
            format="json",
        )
        self.assertEqual(declaration_response.status_code, status.HTTP_201_CREATED)

        self._login_as(staff)
        confirm_response = self.client.patch(
            reverse("booking-detail", args=[booking_id]),
            {"status": Booking.STATUS_CONFIRMED},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        checkin_response = self.client.patch(reverse("medical-check-in", args=[booking_id]))
        self.assertEqual(checkin_response.status_code, status.HTTP_200_OK)
        self.assertTrue(checkin_response.data["has_pre_screening"])

        self._login_as(doctor)
        screening_response = self.client.post(
            reverse("medical-screening"),
            {
                "booking": booking_id,
                "temperature": 36.7,
                "blood_pressure": "120/80",
                "decision": "eligible",
                "doctor_note": "Fit for vaccination",
            },
            format="json",
        )
        self.assertEqual(screening_response.status_code, status.HTTP_201_CREATED)

        self._login_as(staff)
        inject_response = self.client.post(
            reverse("medical-inject"),
            {
                "booking": booking_id,
                "injected_by": "Staff Flow",
                "dose_number": 1,
            },
            format="json",
        )
        self.assertIn(inject_response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        monitor_response = self.client.post(
            reverse("medical-monitor"),
            {
                "booking": booking_id,
                "reaction_status": "Normal",
                "notes": "Observed for 30 minutes",
            },
            format="json",
        )
        self.assertEqual(monitor_response.status_code, status.HTTP_201_CREATED)

        booking = Booking.objects.get(pk=booking_id)
        self.vaccine.refresh_from_db()

        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertEqual(self.vaccine.quantity, 4)
        self.assertTrue(PreScreeningDeclaration.objects.filter(booking=booking).exists())
        self.assertTrue(ScreeningResult.objects.filter(booking=booking, decision="eligible").exists())
        self.assertTrue(VaccinationLog.objects.filter(booking=booking).exists())
        self.assertTrue(PostInjectionTracking.objects.filter(vaccination_log__booking=booking).exists())

    def test_doctor_can_confirm_but_cannot_check_in(self):
        doctor = User.objects.create(
            full_name="Doctor Confirm Only",
            email="doctor-confirm@example.com",
            password_hash="x",
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            full_name="Booking Pending",
            phone="0909000111",
            email="pending@example.com",
            vaccine_name="Flu",
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )

        self._login_as(doctor)
        confirm_response = self.client.patch(
            reverse("booking-detail", args=[booking.id]),
            {"status": Booking.STATUS_CONFIRMED},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        checkin_response = self.client.patch(reverse("medical-check-in", args=[booking.id]))
        self.assertEqual(checkin_response.status_code, status.HTTP_403_FORBIDDEN)

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)

    def test_staff_must_fill_pre_screening_after_check_in_when_customer_skipped_it(self):
        staff = User.objects.create(
            full_name="Staff Missing Declaration",
            email="staff-missing@example.com",
            password_hash="x",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        doctor = User.objects.create(
            full_name="Doctor Missing Declaration",
            email="doctor-missing@example.com",
            password_hash="x",
            role=User.ROLE_DOCTOR,
            status=User.STATUS_ACTIVE,
        )
        booking = Booking.objects.create(
            full_name="Khach Chua Khai Bao",
            phone="0912333444",
            email="missing@example.com",
            vaccine_name="Flu",
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )

        self._login_as(staff)
        checkin_response = self.client.patch(reverse("medical-check-in", args=[booking.id]))
        self.assertEqual(checkin_response.status_code, status.HTTP_200_OK)
        self.assertFalse(checkin_response.data["has_pre_screening"])

        self._login_as(doctor)
        blocked_screening_response = self.client.post(
            reverse("medical-screening"),
            {
                "booking": booking.id,
                "temperature": 36.8,
                "blood_pressure": "120/80",
                "decision": "eligible",
                "doctor_note": "Should be blocked first",
            },
            format="json",
        )
        self.assertEqual(blocked_screening_response.status_code, status.HTTP_400_BAD_REQUEST)

        self._login_as(staff)
        declaration_response = self.client.post(
            reverse("medical-pre-screening", args=[booking.id]),
            {
                "has_fever": False,
                "has_allergy_history": False,
                "has_chronic_condition": False,
                "recent_symptoms": "",
                "current_medications": "",
                "note": "Bo sung boi y ta luc check-in",
            },
            format="json",
        )
        self.assertIn(declaration_response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        self._login_as(doctor)
        screening_response = self.client.post(
            reverse("medical-screening"),
            {
                "booking": booking.id,
                "temperature": 36.8,
                "blood_pressure": "120/80",
                "decision": "eligible",
                "doctor_note": "Now allowed",
            },
            format="json",
        )
        self.assertEqual(screening_response.status_code, status.HTTP_201_CREATED)

    def test_staff_reschedule_restarts_booking_from_pending(self):
        staff = User.objects.create(
            full_name="Staff",
            email="staff@example.com",
            password_hash="x",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        source = Booking.objects.create(
            full_name="Tran Thi B",
            phone="0911000000",
            email="b@example.com",
            vaccine_name="Flu",
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        PreScreeningDeclaration.objects.create(
            booking=source,
            has_fever=True,
            recent_symptoms="Sot",
        )
        self._login_as(staff)

        response = self.client.post(
            reverse("medical-reschedule", args=[source.id]),
            {"vaccine_date": timezone.localdate() + timedelta(days=3)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_booking = Booking.objects.get(pk=response.data["id"])
        self.assertEqual(new_booking.status, Booking.STATUS_PENDING)
        self.assertEqual(new_booking.booking_source, Booking.BOOKING_SOURCE_ONLINE)
        self.assertEqual(new_booking.rescheduled_from_id, source.id)
        self.assertTrue(hasattr(new_booking, "pre_screening"))
        self.assertTrue(new_booking.pre_screening.has_fever)

    def test_citizen_can_reschedule_delayed_booking_matched_by_email(self):
        citizen = User.objects.create(
            full_name="Citizen",
            email="citizen@example.com",
            password_hash="x",
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )
        source = Booking.objects.create(
            full_name="Citizen",
            phone="0911222333",
            email="citizen@example.com",
            vaccine_name="Flu",
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_DELAYED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        self._login_as(citizen)

        response = self.client.post(
            reverse("medical-reschedule", args=[source.id]),
            {"vaccine_date": timezone.localdate() + timedelta(days=5)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_booking = Booking.objects.get(pk=response.data["id"])
        self.assertEqual(new_booking.status, Booking.STATUS_PENDING)
        self.assertEqual(new_booking.rescheduled_from_id, source.id)
