from pathlib import Path

from django.test import TestCase

from feature.authentication.models import User


class DashboardLocalizationTests(TestCase):
    def _login_as(self, user):
        session = self.client.session
        session["user_id"] = user.id
        session.save()

    def _create_user(self, *, role, email, full_name="Demo User"):
        return User.objects.create(
            full_name=full_name,
            email=email,
            password_hash="x",
            role=role,
            status=User.STATUS_ACTIVE,
        )

    def test_staff_dashboard_redirects_to_medical_dashboard(self):
        staff = self._create_user(
            role=User.ROLE_STAFF,
            email="staff-dashboard@example.com",
            full_name="Y ta Truc",
        )

        self._login_as(staff)
        response = self.client.get("/users/dashboard/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/medical/dashboard/")

    def test_doctor_dashboard_redirects_to_medical_dashboard(self):
        doctor = self._create_user(
            role=User.ROLE_DOCTOR,
            email="doctor-dashboard@example.com",
            full_name="Bac si Truc",
        )

        self._login_as(doctor)
        response = self.client.get("/users/dashboard/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/medical/dashboard/")

    def test_admin_dashboard_redirects_to_inventory_dashboard(self):
        admin = self._create_user(
            role=User.ROLE_ADMIN,
            email="admin-dashboard@example.com",
            full_name="Admin",
        )

        self._login_as(admin)
        response = self.client.get("/users/dashboard/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/assets/")

    def test_admin_cannot_open_medical_dashboard(self):
        admin = self._create_user(
            role=User.ROLE_ADMIN,
            email="admin-medical-dashboard@example.com",
            full_name="Admin",
        )

        self._login_as(admin)
        response = self.client.get("/medical/dashboard/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/assets/")

    def test_citizen_dashboard_stays_on_citizen_dashboard(self):
        citizen = self._create_user(
            role=User.ROLE_CITIZEN,
            email="citizen-dashboard@example.com",
            full_name="Citizen",
        )

        self._login_as(citizen)
        response = self.client.get("/users/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/dashboard.html")

        content = response.content.decode("utf-8")
        self.assertIn("dashboard-screening-question-group", content)
        self.assertIn("dashboard-online-review", content)
        self.assertNotIn("dashboard-has-fever", content)

    def test_medical_dashboard_and_script_use_utf8_vietnamese(self):
        staff = self._create_user(
            role=User.ROLE_STAFF,
            email="medical-dashboard@example.com",
            full_name="Dieu duong Truong",
        )

        self._login_as(staff)
        response = self.client.get("/medical/dashboard/")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Dashboard y khoa", content)
        self.assertIn("logoutBtn", content)
        self.assertIn("Walk-in", content)

        js_path = Path(__file__).resolve().parents[2] / "feature" / "medical" / "static" / "medical" / "js" / "medical.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("Ngay truc:", js_content)
        self.assertIn("Check-in", js_content)
        self.assertNotIn("NgÃƒÆ’", js_content)

