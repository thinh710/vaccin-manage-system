import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.utils import timezone

from feature.assets.models import StockImport, StorageLocation, Supplier, Vaccine
from feature.authentication.models import User as AppUser


DJANGO_ADMIN_USERNAME = "admin"
DJANGO_ADMIN_EMAIL = "admin@vaccin.local"
DJANGO_ADMIN_PASSWORD = "AdminDemo@123"

APP_DEMO_PASSWORD = "Demo@123"
SEED_NOTE_PREFIX = "[VN demo seed]"


@dataclass(frozen=True)
class DemoVaccine:
    name: str
    manufacturer: str
    supplier_name: str
    location_name: str
    storage_temperature: str


SUPPLIER_DATA = [
    {
        "name": "VNVC Central Supply",
        "phone": "02871026595",
        "email": "supply@vnvc.local",
        "address": "Thu Duc, Ho Chi Minh City",
    },
    {
        "name": "GSK Vietnam Distribution",
        "phone": "02871020001",
        "email": "gsk-distribution@vnvc.local",
        "address": "District 1, Ho Chi Minh City",
    },
    {
        "name": "MSD Vietnam Distribution",
        "phone": "02871020002",
        "email": "msd-distribution@vnvc.local",
        "address": "District 3, Ho Chi Minh City",
    },
    {
        "name": "Sanofi Pasteur Vietnam",
        "phone": "02871020003",
        "email": "sanofi-distribution@vnvc.local",
        "address": "District 7, Ho Chi Minh City",
    },
    {
        "name": "Pfizer Vietnam Distribution",
        "phone": "02871020004",
        "email": "pfizer-distribution@vnvc.local",
        "address": "Hai Ba Trung, Hanoi",
    },
]


LOCATION_DATA = [
    {
        "name": "Kho lanh trung tam 2-8C",
        "description": "Kho tong cho vaccine bao quan nhiet do 2-8C.",
    },
    {
        "name": "Kho lanh khu tre em",
        "description": "Khu bao quan vaccine danh cho cac phac do tre em.",
    },
    {
        "name": "Kho lanh khu nguoi lon",
        "description": "Khu bao quan vaccine danh cho thanh thieu nien va nguoi lon.",
    },
    {
        "name": "Kho am sau dac biet",
        "description": "Khu bao quan cac lo vaccine can dieu kien lanh dac biet.",
    },
]


DEMO_VACCINES = [
    DemoVaccine("Infanrix Hexa", "GSK (Belgium)", "GSK Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Hexaxim", "Sanofi (France)", "Sanofi Pasteur Vietnam", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Rotateq", "MSD (USA)", "MSD Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Rotarix", "GSK (Belgium)", "GSK Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Rotavin", "Polyvac (Vietnam)", "VNVC Central Supply", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Synflorix", "GSK (Belgium)", "GSK Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Prevenar 13", "Pfizer (Belgium)", "Pfizer Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Vaxneuvance", "MSD (Ireland)", "MSD Vietnam Distribution", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Prevenar 20", "Pfizer (Belgium)", "Pfizer Vietnam Distribution", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Pneumovax 23", "MSD (USA)", "MSD Vietnam Distribution", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Ivactuber", "IVAC (Vietnam)", "VNVC Central Supply", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Gene Hbvax 1ml", "Vabiotech (Vietnam)", "VNVC Central Supply", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Heberbiovac 1ml", "Heber Biotec (Cuba)", "VNVC Central Supply", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Gene Hbvax 0.5ml", "Vabiotech (Vietnam)", "VNVC Central Supply", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Heberbiovac 0.5ml", "Heber Biotec (Cuba)", "VNVC Central Supply", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Bexsero", "GSK (Italy)", "GSK Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("VA-Mengoc-BC", "Finlay Institute (Cuba)", "VNVC Central Supply", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Nimenrix", "Pfizer (Belgium)", "Pfizer Vietnam Distribution", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("MenQuadfi", "Sanofi (USA)", "Sanofi Pasteur Vietnam", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Menactra", "Sanofi (USA)", "Sanofi Pasteur Vietnam", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("MMR II", "MSD (USA)", "MSD Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Priorix", "GSK (Belgium)", "GSK Vietnam Distribution", "Kho lanh khu tre em", "2-8C"),
    DemoVaccine("Varivax", "MSD (USA)", "MSD Vietnam Distribution", "Kho am sau dac biet", "-15C"),
    DemoVaccine("Varilrix", "GSK (Belgium)", "GSK Vietnam Distribution", "Kho am sau dac biet", "-15C"),
    DemoVaccine("Gardasil 9", "MSD (USA)", "MSD Vietnam Distribution", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Qdenga", "Takeda (Germany)", "VNVC Central Supply", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Imojev", "Sanofi (Thailand)", "Sanofi Pasteur Vietnam", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Verorab", "Sanofi (France)", "Sanofi Pasteur Vietnam", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Adacel", "Sanofi (Canada)", "Sanofi Pasteur Vietnam", "Kho lanh khu nguoi lon", "2-8C"),
    DemoVaccine("Havax", "IVAC (Vietnam)", "VNVC Central Supply", "Kho lanh khu nguoi lon", "2-8C"),
]


class Command(BaseCommand):
    help = "Back up current PostgreSQL data, reset demo data, and seed 30 Vietnam market vaccines."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-backup",
            action="store_true",
            help="Skip pg_dump backup before reset.",
        )
        parser.add_argument(
            "--skip-flush",
            action="store_true",
            help="Skip database flush before seeding. Useful for local tests.",
        )

    def handle(self, *args, **options):
        if not options["skip_backup"]:
            self._backup_database_if_supported()
        else:
            self.stdout.write(self.style.WARNING("Skipping database backup by request."))

        self.stdout.write("Ensuring database schema is up to date...")
        call_command("migrate", interactive=False, verbosity=max(options.get("verbosity", 1) - 1, 0))

        if not options["skip_flush"]:
            self.stdout.write(self.style.WARNING("Flushing all existing data from the current database..."))
            call_command("flush", interactive=False, verbosity=max(options.get("verbosity", 1) - 1, 0))
        else:
            self.stdout.write(self.style.WARNING("Skipping flush; command will upsert demo records."))

        self.stdout.write("Seeding demo users, suppliers, locations, vaccines, and stock imports...")
        with transaction.atomic():
            app_users = self._seed_app_users()
            self._seed_django_admin_user()
            suppliers = self._seed_suppliers()
            locations = self._seed_locations()
            self._seed_vaccines_and_imports(
                admin_user=app_users["admin"],
                suppliers=suppliers,
                locations=locations,
            )

        self._print_credentials()
        self.stdout.write(self.style.SUCCESS("Demo reset complete. The environment now contains 30 seeded vaccines."))

    def _backup_database_if_supported(self):
        database = settings.DATABASES["default"]
        engine = database.get("ENGINE", "")
        if "postgresql" not in engine:
            self.stdout.write("Current database is not PostgreSQL; skipping pg_dump backup.")
            return

        pg_dump_path = shutil.which("pg_dump")
        if not pg_dump_path:
            raise CommandError(
                "pg_dump was not found. Install postgresql-client or rerun with --skip-backup."
            )

        backup_dir = Path(settings.BASE_DIR) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        backup_file = backup_dir / f"pre-reset-demo-{timestamp}.sql"

        command = [
            pg_dump_path,
            "-Fp",
            "-h",
            database.get("HOST") or "localhost",
            "-p",
            str(database.get("PORT") or "5432"),
            "-U",
            database.get("USER") or "postgres",
            "-d",
            database.get("NAME") or "",
            "-f",
            str(backup_file),
        ]

        env = os.environ.copy()
        password = database.get("PASSWORD")
        if password:
            env["PGPASSWORD"] = str(password)

        self.stdout.write(f"Creating PostgreSQL backup at {backup_file} ...")
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise CommandError(
                f"pg_dump failed with exit code {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
            )
        self.stdout.write(self.style.SUCCESS(f"Backup completed: {backup_file}"))

    def _seed_app_users(self):
        demo_users = {
            "admin": {
                "full_name": "Demo Admin",
                "email": "admin.demo@vaccin.local",
                "role": AppUser.ROLE_ADMIN,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000001",
                "gender": "other",
            },
            "staff": {
                "full_name": "Demo Staff",
                "email": "staff.demo@vaccin.local",
                "role": AppUser.ROLE_STAFF,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000002",
                "gender": "female",
            },
            "doctor": {
                "full_name": "Demo Doctor",
                "email": "doctor.demo@vaccin.local",
                "role": AppUser.ROLE_DOCTOR,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000003",
                "gender": "male",
            },
            "citizen": {
                "full_name": "Demo Citizen",
                "email": "citizen.demo@vaccin.local",
                "role": AppUser.ROLE_CITIZEN,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000004",
                "gender": "female",
            },
        }

        created_users = {}
        for key, defaults in demo_users.items():
            user, _ = AppUser.objects.update_or_create(
                email=defaults["email"],
                defaults={
                    **defaults,
                    "auth_provider": AppUser.AUTH_PROVIDER_LOCAL,
                },
            )
            user.set_password(APP_DEMO_PASSWORD)
            user.save(update_fields=["password_hash"])
            created_users[key] = user

        return created_users

    def _seed_django_admin_user(self):
        django_user_model = get_user_model()
        admin_user, _ = django_user_model.objects.get_or_create(
            username=DJANGO_ADMIN_USERNAME,
            defaults={
                "email": DJANGO_ADMIN_EMAIL,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        admin_user.email = DJANGO_ADMIN_EMAIL
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.set_password(DJANGO_ADMIN_PASSWORD)
        admin_user.save()

    def _seed_suppliers(self):
        suppliers = {}
        for item in SUPPLIER_DATA:
            supplier, _ = Supplier.objects.update_or_create(name=item["name"], defaults=item)
            suppliers[supplier.name] = supplier
        return suppliers

    def _seed_locations(self):
        locations = {}
        for item in LOCATION_DATA:
            location, _ = StorageLocation.objects.update_or_create(name=item["name"], defaults=item)
            locations[location.name] = location
        return locations

    def _seed_vaccines_and_imports(self, *, admin_user, suppliers, locations):
        StockImport.objects.filter(note__startswith=SEED_NOTE_PREFIX).delete()

        today = timezone.localdate()
        for index, demo_vaccine in enumerate(DEMO_VACCINES, start=1):
            minimum_stock = 12 + ((index - 1) % 4) * 6
            quantity = 45 + ((index * 17) % 140)
            if index in {5, 18, 27}:
                quantity = max(minimum_stock - 2, 4)

            if index == 1:
                expiration_date = today + timedelta(days=20)
            elif index == 2:
                expiration_date = today + timedelta(days=28)
            elif index == 3:
                expiration_date = today + timedelta(days=45)
            else:
                expiration_date = today + timedelta(days=180 + index * 13)

            vaccine, _ = Vaccine.objects.update_or_create(
                batch_number=f"VN-DEMO-{index:03d}",
                defaults={
                    "name": demo_vaccine.name,
                    "manufacturer": demo_vaccine.manufacturer,
                    "quantity": quantity,
                    "minimum_stock": minimum_stock,
                    "expiration_date": expiration_date,
                    "storage_temperature": demo_vaccine.storage_temperature,
                    "supplier": suppliers[demo_vaccine.supplier_name],
                    "location": locations[demo_vaccine.location_name],
                },
            )

            StockImport.objects.create(
                vaccine=vaccine,
                quantity=quantity,
                import_date=today - timedelta(days=2 + (index % 9)),
                supplier=suppliers[demo_vaccine.supplier_name],
                note=f"{SEED_NOTE_PREFIX} Initial stock for {demo_vaccine.name}",
                created_by=admin_user,
            )

    def _print_credentials(self):
        self.stdout.write("")
        self.stdout.write("Seeded credentials:")
        self.stdout.write(f"  Django admin: {DJANGO_ADMIN_USERNAME} / {DJANGO_ADMIN_PASSWORD}")
        self.stdout.write(f"  App admin: admin.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App staff: staff.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App doctor: doctor.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App citizen: citizen.demo@vaccin.local / {APP_DEMO_PASSWORD}")
