import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from feature.assets.models import StockAdjustment, StockExport, StockImport, StorageLocation, Supplier, Vaccine
from feature.authentication.models import User as AppUser
from feature.assets.management.commands.reset_demo_data_vn import (
    APP_DEMO_PASSWORD,
    DJANGO_ADMIN_PASSWORD,
    DJANGO_ADMIN_USERNAME,
)


class InventoryPermissionTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="ACME")
        Vaccine.objects.create(
            name="Flu",
            manufacturer="ACME",
            batch_number="BATCH-001",
            quantity=10,
            minimum_stock=2,
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )
        self.doctor = AppUser.objects.create(
            full_name="Doctor",
            email="doctor@example.com",
            password_hash="x",
            role=AppUser.ROLE_DOCTOR,
            status=AppUser.STATUS_ACTIVE,
        )

    def _login_as(self, user):
        session = self.client.session
        session["user_id"] = user.id
        session.save()

    def test_doctor_can_manage_inventory_transactions(self):
        self._login_as(self.doctor)

        vaccine_response = self.client.get(reverse("vaccine-list"))
        export_response = self.client.get(reverse("stock-export-list"))
        dashboard_response = self.client.get(reverse("inventory-dashboard-page"))

        self.assertEqual(vaccine_response.status_code, status.HTTP_200_OK)
        self.assertEqual(export_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)


class StockTransactionDeltaTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="Delta Supplier")
        self.vaccine = Vaccine.objects.create(
            name="Flu",
            manufacturer="Delta Pharma",
            batch_number="DELTA-001",
            quantity=10,
            minimum_stock=2,
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )
        self.admin = AppUser.objects.create(
            full_name="Admin Delta",
            email="admin-delta@example.com",
            password_hash="x",
            role=AppUser.ROLE_ADMIN,
            status=AppUser.STATUS_ACTIVE,
        )
        session = self.client.session
        session["user_id"] = self.admin.id
        session.save()

    def test_import_patch_and_delete_update_stock_delta(self):
        create_response = self.client.post(
            reverse("stock-import-list"),
            {
                "vaccine": self.vaccine.id,
                "quantity": 10,
                "import_date": str(timezone.localdate()),
                "supplier": self.supplier.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 20)

        detail_url = reverse("stock-import-detail", args=[create_response.data["id"]])
        patch_response = self.client.patch(detail_url, {"quantity": 5}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 15)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 10)

    def test_export_patch_and_delete_update_stock_delta(self):
        create_response = self.client.post(
            reverse("stock-export-list"),
            {
                "vaccine": self.vaccine.id,
                "quantity": 5,
                "export_date": str(timezone.localdate()),
                "destination": "Clinic A",
                "export_type": "transfer",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 5)

        detail_url = reverse("stock-export-detail", args=[create_response.data["id"]])
        patch_response = self.client.patch(detail_url, {"quantity": 3}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 7)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 10)

    def test_adjustment_patch_and_delete_update_stock_delta(self):
        create_response = self.client.post(
            reverse("stock-adjustment-list"),
            {
                "vaccine": self.vaccine.id,
                "adjustment_type": "decrease",
                "quantity": 4,
                "reason": "Damaged vials",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 6)

        detail_url = reverse("stock-adjustment-detail", args=[create_response.data["id"]])
        patch_response = self.client.patch(detail_url, {"quantity": 2}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 8)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 10)

    def test_import_patch_rejects_stock_that_would_go_negative(self):
        create_response = self.client.post(
            reverse("stock-import-list"),
            {
                "vaccine": self.vaccine.id,
                "quantity": 10,
                "import_date": str(timezone.localdate()),
                "supplier": self.supplier.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.vaccine.quantity = 4
        self.vaccine.save(update_fields=["quantity"])

        detail_url = reverse("stock-import-detail", args=[create_response.data["id"]])
        patch_response = self.client.patch(detail_url, {"quantity": 5}, format="json")

        self.assertEqual(patch_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.vaccine.refresh_from_db()
        self.assertEqual(self.vaccine.quantity, 4)


class AssetsCsrfTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.supplier = Supplier.objects.create(name="CSRF Supplier")
        self.vaccine = Vaccine.objects.create(
            name="Flu",
            manufacturer="CSRF Pharma",
            batch_number="ASSET-CSRF-001",
            quantity=10,
            minimum_stock=1,
            expiration_date=timezone.localdate() + timedelta(days=30),
            supplier=self.supplier,
        )
        self.admin = AppUser.objects.create(
            full_name="Admin CSRF",
            email="assets-admin-csrf@example.com",
            password_hash="x",
            role=AppUser.ROLE_ADMIN,
            status=AppUser.STATUS_ACTIVE,
        )
        session = self.client.session
        session["user_id"] = self.admin.id
        session.save()

    def _csrf_headers(self):
        token = "c" * 32
        self.client.cookies["csrftoken"] = token
        return {"HTTP_X_CSRFTOKEN": token}

    def test_stock_import_requires_csrf_token(self):
        payload = {
            "vaccine": self.vaccine.id,
            "quantity": 1,
            "import_date": str(timezone.localdate()),
            "supplier": self.supplier.id,
        }
        url = reverse("stock-import-list")

        missing = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)

        ok = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)


class ResetDemoDataVNCommandTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()

    def _login_as_app_user(self, user):
        session = self.client.session
        session["user_id"] = user.id
        session.save()

    def test_command_seeds_expected_demo_records(self):
        call_command("reset_demo_data_vn", skip_backup=True, verbosity=0)

        self.assertEqual(AppUser.objects.count(), 6)
        self.assertEqual(Supplier.objects.count(), 5)
        self.assertEqual(StorageLocation.objects.count(), 4)
        self.assertTrue(StorageLocation.objects.filter(name="Kho lạnh trung tâm 2-8°C").exists())
        self.assertTrue(StorageLocation.objects.filter(name="Kho âm sâu đặc biệt").exists())
        self.assertFalse(StorageLocation.objects.filter(name__icontains="Kho lanh").exists())
        self.assertEqual(Vaccine.objects.count(), 30)
        self.assertEqual(StockImport.objects.count(), 30)
        self.assertEqual(Vaccine.objects.filter(expiration_date__gt=timezone.localdate()).count(), 30)
        self.assertEqual(Vaccine.objects.values("batch_number").distinct().count(), 30)
        self.assertTrue(Vaccine.objects.filter(name="Gardasil 9").exists())
        self.assertTrue(
            get_user_model().objects.filter(username=DJANGO_ADMIN_USERNAME, is_superuser=True).exists()
        )

    def test_command_provides_working_inventory_pages_and_api(self):
        call_command("reset_demo_data_vn", skip_backup=True, verbosity=0)

        admin_user = AppUser.objects.get(email="admin.demo@vaccin.local")
        self._login_as_app_user(admin_user)

        dashboard_response = self.client.get(reverse("inventory-dashboard-page"))
        vaccine_response = self.client.get(reverse("vaccine-list"))
        supplier_response = self.client.get(reverse("supplier-list"))
        location_response = self.client.get(reverse("location-list"))

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(vaccine_response.status_code, status.HTTP_200_OK)
        self.assertEqual(supplier_response.status_code, status.HTTP_200_OK)
        self.assertEqual(location_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(vaccine_response.json()), 30)
        self.assertEqual(len(supplier_response.json()), 5)
        self.assertEqual(len(location_response.json()), 4)

    def test_command_creates_login_credentials_for_admin_flows(self):
        call_command("reset_demo_data_vn", skip_backup=True, verbosity=0)

        app_admin_login = self.client.post(
            reverse("login"),
            {"email": "admin.demo@vaccin.local", "password": APP_DEMO_PASSWORD},
        )

        self.assertEqual(app_admin_login.status_code, 302)
        self.assertEqual(app_admin_login.headers["Location"], "/users/dashboard/")
        self.assertTrue(self.client.login(username=DJANGO_ADMIN_USERNAME, password=DJANGO_ADMIN_PASSWORD))
        self.assertEqual(self.client.get("/admin/").status_code, status.HTTP_200_OK)
