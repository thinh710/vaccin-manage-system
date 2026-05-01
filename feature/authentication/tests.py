import json

from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from feature.authentication.models import User


class RegistrationTests(APITestCase):
    def test_register_page_is_citizen_only_ui(self):
        response = self.client.get(reverse("register-page"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotContains(response, 'name="role_display"', html=False)
        self.assertNotContains(response, 'register-role-inline', html=False)
        self.assertNotContains(response, 'id="role"', html=False)

    def test_public_registration_always_creates_citizen_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "Privileged Attempt",
                "email": "attempt@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
                "role": User.ROLE_ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email="attempt@example.com")
        self.assertEqual(created_user.role, User.ROLE_CITIZEN)
        self.assertEqual(response.data["user"]["role"], User.ROLE_CITIZEN)


class AuthenticationCsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create(
            full_name="CSRF User",
            email="csrf-user@example.com",
            password_hash=make_password("secret123"),
            role=User.ROLE_CITIZEN,
            status=User.STATUS_ACTIVE,
        )

    def _csrf_headers(self):
        token = "d" * 32
        self.client.cookies["csrftoken"] = token
        return {"HTTP_X_CSRFTOKEN": token}

    def test_register_login_and_logout_require_csrf_token(self):
        register_payload = {
            "full_name": "New CSRF User",
            "email": "new-csrf-user@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        }
        missing_register = self.client.post(
            reverse("register"),
            data=json.dumps(register_payload),
            content_type="application/json",
        )
        self.assertEqual(missing_register.status_code, status.HTTP_403_FORBIDDEN)

        registered = self.client.post(
            reverse("register"),
            data=json.dumps(register_payload),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(registered.status_code, status.HTTP_201_CREATED)

        self.client = Client(enforce_csrf_checks=True)
        login_payload = {"email": self.user.email, "password": "secret123"}
        missing_login = self.client.post(
            reverse("login"),
            data=json.dumps(login_payload),
            content_type="application/json",
        )
        self.assertEqual(missing_login.status_code, status.HTTP_403_FORBIDDEN)

        logged_in = self.client.post(
            reverse("login"),
            data=json.dumps(login_payload),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(logged_in.status_code, status.HTTP_200_OK)

        missing_logout = self.client.post(reverse("logout"))
        self.assertEqual(missing_logout.status_code, status.HTTP_403_FORBIDDEN)

        logged_out = self.client.post(reverse("logout"), **self._csrf_headers())
        self.assertEqual(logged_out.status_code, status.HTTP_200_OK)
