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
