from django.db import models
from django.contrib.auth.hashers import check_password, make_password


class User(models.Model):
    AUTH_PROVIDER_LOCAL = 'local'
    AUTH_PROVIDER_GOOGLE = 'google'
    AUTH_PROVIDER_FACEBOOK = 'facebook'
    AUTH_PROVIDER_CHOICES = [
        (AUTH_PROVIDER_LOCAL, 'Local'),
        (AUTH_PROVIDER_GOOGLE, 'Google'),
        (AUTH_PROVIDER_FACEBOOK, 'Facebook'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('UNKNOWN', 'Unknown'),
    ]

    ROLE_ADMIN = 'admin'
    ROLE_CITIZEN = 'citizen'
    ROLE_STAFF = 'staff'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_CITIZEN, 'Citizen'),
        (ROLE_STAFF, 'Staff'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_BANNED = 'banned'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_BANNED, 'Banned'),
    ]

    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, default='UNKNOWN')
    allergies = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)
    avatar_data = models.TextField(blank=True)
    password_hash = models.CharField(max_length=255)
    auth_provider = models.CharField(
        max_length=20,
        choices=AUTH_PROVIDER_CHOICES,
        default=AUTH_PROVIDER_LOCAL,
    )
    provider_user_id = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CITIZEN)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        ordering = ['-id']

    def __str__(self):
        return self.email

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)
