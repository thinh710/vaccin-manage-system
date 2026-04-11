from django.test import TestCase
from django.utils import timezone

from feature.authentication.models import User
from feature.booking.models import Booking


class DashboardLocalizationTests(TestCase):
    def _login_as(self, user):
        session = self.client.session
        session["user_id"] = user.id
        session.save()

    def test_staff_dashboard_renders_vietnamese_copy(self):
        staff = User.objects.create(
            full_name="Y ta Truc",
            email="staff-dashboard@example.com",
            password_hash="x",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )

        self._login_as(staff)
        response = self.client.get("/users/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Đăng xuất")

    def test_staff_dashboard_context_includes_pending_count_for_today(self):
        staff = User.objects.create(
            full_name="Y ta Pending",
            email="staff-pending@example.com",
            password_hash="x",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )
        Booking.objects.create(
            full_name="Khach Pending",
            phone="0912888999",
            email="pending-booking@example.com",
            vaccine_name="Flu",
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_PENDING,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )
        Booking.objects.create(
            full_name="Khach Confirmed",
            phone="0912777666",
            email="confirmed-booking@example.com",
            vaccine_name="Flu",
            vaccine_date=timezone.localdate(),
            dose_number=1,
            status=Booking.STATUS_CONFIRMED,
            booking_source=Booking.BOOKING_SOURCE_ONLINE,
        )

        self._login_as(staff)
        response = self.client.get("/users/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pending_count"], 1)

    def test_medical_dashboard_renders_server_side_vietnamese(self):
        staff = User.objects.create(
            full_name="Dieu duong Truong",
            email="medical-dashboard@example.com",
            password_hash="x",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
        )

        self._login_as(staff)
        response = self.client.get("/medical/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard y khoa không dùng JavaScript")
        self.assertContains(response, "Đăng xuất")
        self.assertContains(response, "Tiếp nhận walk-in")
