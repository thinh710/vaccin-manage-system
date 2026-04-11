from django.test import TestCase

from feature.authentication.models import User


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
