from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from feature.authentication.models import User


class RegistrationTests(APITestCase):
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
