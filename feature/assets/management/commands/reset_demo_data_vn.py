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
from feature.booking.models import Booking
from feature.medical.models import (
    PostInjectionTracking,
    PreScreeningDeclaration,
    ScreeningResult,
    VaccinationLog,
)


DJANGO_ADMIN_USERNAME = "admin"
DJANGO_ADMIN_EMAIL = "admin@vaccin.local"
DJANGO_ADMIN_PASSWORD = "AdminDemo@123"

APP_DEMO_PASSWORD = "Demo@123"
SEED_NOTE_PREFIX = "[VN demo seed]"
BOOKING_NOTE_PREFIX = "[VN demo booking]"


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
            seeded_vaccines = self._seed_vaccines_and_imports(
                admin_user=app_users["admin"],
                suppliers=suppliers,
                locations=locations,
            )
            self._seed_demo_bookings(app_users=app_users, vaccines=seeded_vaccines)

        self._print_credentials()
        self.stdout.write(
            self.style.SUCCESS(
                "Demo reset complete. The environment now contains seeded users, vaccines, bookings, and medical flows."
            )
        )

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
                "full_name": "Quản trị viên Demo",
                "email": "admin.demo@vaccin.local",
                "role": AppUser.ROLE_ADMIN,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000001",
                "gender": "other",
            },
            "staff": {
                "full_name": "Y tá Demo",
                "email": "staff.demo@vaccin.local",
                "role": AppUser.ROLE_STAFF,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000002",
                "gender": "female",
            },
            "doctor": {
                "full_name": "Bác sĩ Demo",
                "email": "doctor.demo@vaccin.local",
                "role": AppUser.ROLE_DOCTOR,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000003",
                "gender": "male",
            },
            "citizen": {
                "full_name": "Công dân Demo",
                "email": "citizen.demo@vaccin.local",
                "role": AppUser.ROLE_CITIZEN,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000004",
                "gender": "female",
            },
            "citizen_two": {
                "full_name": "Nguyễn Minh Anh",
                "email": "citizen2.demo@vaccin.local",
                "role": AppUser.ROLE_CITIZEN,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000005",
                "gender": "male",
            },
            "citizen_three": {
                "full_name": "Trần Bảo Ngọc",
                "email": "citizen3.demo@vaccin.local",
                "role": AppUser.ROLE_CITIZEN,
                "status": AppUser.STATUS_ACTIVE,
                "phone_number": "0901000006",
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
        seeded_vaccines = []
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

            seeded_vaccines.append(vaccine)

        return seeded_vaccines

    def _seed_demo_bookings(self, *, app_users, vaccines):
        Booking.objects.filter(note__startswith=BOOKING_NOTE_PREFIX).delete()

        vaccine_map = {item.name: item for item in vaccines}
        today = timezone.localdate()
        scenarios = [
            {
                "full_name": app_users["citizen"].full_name,
                "phone": app_users["citizen"].phone_number,
                "email": app_users["citizen"].email,
                "user": app_users["citizen"],
                "vaccine_name": "Gardasil 9",
                "vaccine_date": today + timedelta(days=2),
                "dose_number": 1,
                "status": Booking.STATUS_PENDING,
                "booking_source": Booking.BOOKING_SOURCE_ONLINE,
                "note": f"{BOOKING_NOTE_PREFIX} Chờ xác nhận mũi HPV",
            },
            {
                "full_name": app_users["citizen_two"].full_name,
                "phone": app_users["citizen_two"].phone_number,
                "email": app_users["citizen_two"].email,
                "user": app_users["citizen_two"],
                "vaccine_name": "Qdenga",
                "vaccine_date": today,
                "dose_number": 1,
                "status": Booking.STATUS_CONFIRMED,
                "booking_source": Booking.BOOKING_SOURCE_ONLINE,
                "note": f"{BOOKING_NOTE_PREFIX} Đã xác nhận chờ tiếp nhận",
            },
            {
                "full_name": app_users["citizen_three"].full_name,
                "phone": app_users["citizen_three"].phone_number,
                "email": app_users["citizen_three"].email,
                "user": app_users["citizen_three"],
                "vaccine_name": "Prevenar 13",
                "vaccine_date": today,
                "dose_number": 2,
                "status": Booking.STATUS_CHECKED_IN,
                "booking_source": Booking.BOOKING_SOURCE_ONLINE,
                "note": f"{BOOKING_NOTE_PREFIX} Đã tiếp nhận chờ sàng lọc",
                "declaration": {
                    "has_fever": False,
                    "has_allergy_history": True,
                    "has_chronic_condition": False,
                    "recent_symptoms": "Viêm mũi nhẹ tuần trước",
                    "current_medications": "Vitamin C",
                    "note": "Đã nghỉ khỏe 3 ngày trước buổi tiêm",
                },
            },
            {
                "full_name": app_users["citizen"].full_name,
                "phone": app_users["citizen"].phone_number,
                "email": app_users["citizen"].email,
                "user": app_users["citizen"],
                "vaccine_name": "Menactra",
                "vaccine_date": today,
                "dose_number": 1,
                "status": Booking.STATUS_READY_TO_INJECT,
                "booking_source": Booking.BOOKING_SOURCE_ONLINE,
                "note": f"{BOOKING_NOTE_PREFIX} Đủ điều kiện chờ tiêm",
                "declaration": {
                    "has_fever": False,
                    "has_allergy_history": False,
                    "has_chronic_condition": False,
                    "recent_symptoms": "",
                    "current_medications": "",
                    "note": "Khách khai báo ổn định",
                },
                "screening": {
                    "temperature": 36.6,
                    "blood_pressure": "118/76",
                    "decision": ScreeningResult.DECISION_ELIGIBLE,
                    "doctor_note": "Đủ điều kiện tiêm trong ngày",
                },
            },
            {
                "full_name": app_users["citizen_two"].full_name,
                "phone": app_users["citizen_two"].phone_number,
                "email": app_users["citizen_two"].email,
                "user": app_users["citizen_two"],
                "vaccine_name": "Hexaxim",
                "vaccine_date": today,
                "dose_number": 3,
                "status": Booking.STATUS_IN_OBSERVATION,
                "booking_source": Booking.BOOKING_SOURCE_WALKIN,
                "note": f"{BOOKING_NOTE_PREFIX} Đã tiêm đang theo dõi",
                "declaration": {
                    "has_fever": False,
                    "has_allergy_history": False,
                    "has_chronic_condition": False,
                    "recent_symptoms": "",
                    "current_medications": "",
                    "note": "Tiếp nhận tại quầy",
                },
                "screening": {
                    "temperature": 36.7,
                    "blood_pressure": "120/80",
                    "decision": ScreeningResult.DECISION_ELIGIBLE,
                    "doctor_note": "Sức khỏe ổn định",
                },
                "vaccination": {
                    "batch_number": "VN-DEMO-002",
                    "injected_by": app_users["staff"].full_name,
                },
            },
            {
                "full_name": app_users["citizen_three"].full_name,
                "phone": app_users["citizen_three"].phone_number,
                "email": app_users["citizen_three"].email,
                "user": app_users["citizen_three"],
                "vaccine_name": "Verorab",
                "vaccine_date": today - timedelta(days=1),
                "dose_number": 4,
                "status": Booking.STATUS_COMPLETED,
                "booking_source": Booking.BOOKING_SOURCE_ONLINE,
                "note": f"{BOOKING_NOTE_PREFIX} Đã hoàn thành đủ quy trình",
                "declaration": {
                    "has_fever": False,
                    "has_allergy_history": False,
                    "has_chronic_condition": True,
                    "recent_symptoms": "",
                    "current_medications": "Thuốc dạ dày",
                    "note": "Theo dõi kỹ sau tiêm",
                },
                "screening": {
                    "temperature": 36.5,
                    "blood_pressure": "122/78",
                    "decision": ScreeningResult.DECISION_ELIGIBLE,
                    "doctor_note": "Tiêm được, theo dõi 30 phút",
                },
                "vaccination": {
                    "batch_number": "VN-DEMO-028",
                    "injected_by": app_users["staff"].full_name,
                },
                "tracking": {
                    "reaction_status": PostInjectionTracking.REACTION_NORMAL,
                    "notes": "Không ghi nhận phản ứng bất thường",
                },
            },
            {
                "full_name": "Lê Gia Hân",
                "phone": "0901999001",
                "email": "walkin1.demo@vaccin.local",
                "user": None,
                "vaccine_name": "Bexsero",
                "vaccine_date": today + timedelta(days=1),
                "dose_number": 1,
                "status": Booking.STATUS_DELAYED,
                "booking_source": Booking.BOOKING_SOURCE_WALKIN,
                "note": f"{BOOKING_NOTE_PREFIX} Tạm hoãn do đang sốt",
                "declaration": {
                    "has_fever": True,
                    "has_allergy_history": False,
                    "has_chronic_condition": False,
                    "recent_symptoms": "Sốt 38 độ tối qua",
                    "current_medications": "Paracetamol",
                    "note": "Hẹn kiểm tra lại sau 3 ngày",
                },
                "screening": {
                    "temperature": 38.0,
                    "blood_pressure": "115/75",
                    "decision": ScreeningResult.DECISION_DELAYED,
                    "doctor_note": "Tạm hoãn do sốt",
                },
            },
            {
                "full_name": "Phạm Quốc Đạt",
                "phone": "0901999002",
                "email": "walkin2.demo@vaccin.local",
                "user": None,
                "vaccine_name": "Imojev",
                "vaccine_date": today + timedelta(days=4),
                "dose_number": 1,
                "status": Booking.STATUS_CANCELLED,
                "booking_source": Booking.BOOKING_SOURCE_WALKIN,
                "note": f"{BOOKING_NOTE_PREFIX} Hủy do chống chỉ định",
                "declaration": {
                    "has_fever": False,
                    "has_allergy_history": True,
                    "has_chronic_condition": True,
                    "recent_symptoms": "",
                    "current_medications": "Thuốc tim mạch",
                    "note": "Tiền sử phản ứng nặng sau tiêm",
                },
                "screening": {
                    "temperature": 36.8,
                    "blood_pressure": "140/90",
                    "decision": ScreeningResult.DECISION_CANCELLED,
                    "doctor_note": "Chống chỉ định tiêm tại thời điểm hiện tại",
                },
            },
            {
                "full_name": "Đỗ Hải Yến",
                "phone": "0901999003",
                "email": "walkin3.demo@vaccin.local",
                "user": None,
                "vaccine_name": "Priorix",
                "vaccine_date": today + timedelta(days=7),
                "dose_number": 1,
                "status": Booking.STATUS_PENDING,
                "booking_source": Booking.BOOKING_SOURCE_WALKIN,
                "note": f"{BOOKING_NOTE_PREFIX} Khách mới tạo tại quầy",
            },
            {
                "full_name": "Nguyễn Tấn Phát",
                "phone": "0901999004",
                "email": "walkin4.demo@vaccin.local",
                "user": None,
                "vaccine_name": "Adacel",
                "vaccine_date": today + timedelta(days=10),
                "dose_number": 2,
                "status": Booking.STATUS_CONFIRMED,
                "booking_source": Booking.BOOKING_SOURCE_ONLINE,
                "note": f"{BOOKING_NOTE_PREFIX} Đã xác nhận cho mũi nhắc",
            },
        ]

        for scenario in scenarios:
            booking = Booking.objects.create(
                user=scenario["user"],
                full_name=scenario["full_name"],
                phone=scenario["phone"],
                email=scenario["email"],
                vaccine_name=scenario["vaccine_name"],
                vaccine_date=scenario["vaccine_date"],
                dose_number=scenario["dose_number"],
                status=scenario["status"],
                booking_source=scenario["booking_source"],
                note=scenario["note"],
            )

            declaration_data = scenario.get("declaration")
            if declaration_data:
                PreScreeningDeclaration.objects.create(booking=booking, **declaration_data)

            screening_data = scenario.get("screening")
            if screening_data:
                ScreeningResult.objects.create(booking=booking, **screening_data)

            vaccination_data = scenario.get("vaccination")
            if vaccination_data:
                vaccine = vaccine_map.get(scenario["vaccine_name"])
                VaccinationLog.objects.create(
                    booking=booking,
                    vaccine=vaccine,
                    dose_number=scenario["dose_number"],
                    **vaccination_data,
                )

            tracking_data = scenario.get("tracking")
            if tracking_data:
                vaccination_log = booking.vaccination_log
                PostInjectionTracking.objects.create(vaccination_log=vaccination_log, **tracking_data)

    def _print_credentials(self):
        self.stdout.write("")
        self.stdout.write("Seeded credentials:")
        self.stdout.write(f"  Django admin: {DJANGO_ADMIN_USERNAME} / {DJANGO_ADMIN_PASSWORD}")
        self.stdout.write(f"  App admin: admin.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App staff: staff.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App doctor: doctor.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App citizen: citizen.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App citizen 2: citizen2.demo@vaccin.local / {APP_DEMO_PASSWORD}")
        self.stdout.write(f"  App citizen 3: citizen3.demo@vaccin.local / {APP_DEMO_PASSWORD}")
