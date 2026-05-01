import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone

from feature.assets.models import StockImport, StorageLocation, Supplier, Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.medical.models import PreScreeningDeclaration


SEED_NOTE_PREFIX = "[WEEK demo seed]"
VACCINE_NOTE_PREFIX = "[WEEK vaccine seed]"
PATIENT_PASSWORD = "123"
WEEK_LOCATION_NAME = "Kho demo lịch hẹn 2-8°C"
WEEK_FROZEN_LOCATION_NAME = "Kho demo đông sâu"
LEGACY_WEEK_LOCATION_NAME_MAP = {
    "Kho demo lich hen 2-8C": WEEK_LOCATION_NAME,
    "Kho demo dong sau": WEEK_FROZEN_LOCATION_NAME,
}


VACCINE_DATA = [
    ("Vaxigrip Tetra", "Sanofi Pasteur", "2-8C"),
    ("Gardasil 9", "MSD", "2-8C"),
    ("Prevenar 13", "Pfizer", "2-8C"),
    ("Prevenar 20", "Pfizer", "2-8C"),
    ("Infanrix Hexa", "GSK", "2-8C"),
    ("Hexaxim", "Sanofi Pasteur", "2-8C"),
    ("Rotateq", "MSD", "2-8C"),
    ("Rotarix", "GSK", "2-8C"),
    ("Synflorix", "GSK", "2-8C"),
    ("MMR II", "MSD", "2-8C"),
    ("Priorix", "GSK", "2-8C"),
    ("Varivax", "MSD", "-15C"),
    ("Varilrix", "GSK", "-15C"),
    ("Verorab", "Sanofi Pasteur", "2-8C"),
    ("Abhayrab", "Human Biologicals Institute", "2-8C"),
    ("Qdenga", "Takeda", "2-8C"),
    ("Imojev", "Sanofi Pasteur", "2-8C"),
    ("Menactra", "Sanofi Pasteur", "2-8C"),
    ("Nimenrix", "Pfizer", "2-8C"),
    ("Bexsero", "GSK", "2-8C"),
    ("Adacel", "Sanofi Pasteur", "2-8C"),
    ("Havax", "IVAC", "2-8C"),
    ("Engerix-B", "GSK", "2-8C"),
    ("Pneumovax 23", "MSD", "2-8C"),
    ("Shingrix", "GSK", "2-8C"),
]


PATIENT_NAMES = [
    "Nguyen Tran Quan",
    "Tran Thi Minh Anh",
    "Le Hoang Nam",
    "Pham Gia Han",
    "Hoang Minh Khang",
    "Vo Thanh Truc",
    "Dang Quoc Bao",
    "Bui Ngoc Linh",
    "Do Anh Thu",
    "Ngo Tuan Kiet",
    "Huynh Bao Ngoc",
    "Phan Duc Huy",
    "Truong My Duyen",
    "Ly Nhat Minh",
    "Mai Phuong Thao",
    "Nguyen Khanh Vy",
    "Tran Duc Anh",
    "Le Bao Tram",
    "Pham Nhat Huy",
    "Hoang Tuong Vy",
    "Vo Minh Quan",
    "Dang Ha Anh",
    "Bui Gia Bao",
    "Do Nhu Quynh",
    "Ngo Thanh Phong",
    "Huynh Mai Chi",
    "Phan Anh Khoa",
    "Truong Bao Chau",
    "Ly Minh Tri",
    "Mai Ngoc Anh",
    "Nguyen Hoai Nam",
    "Tran Lan Chi",
    "Le Tien Dat",
    "Pham Minh Chau",
    "Hoang Anh Tu",
    "Vo Thao Nhi",
    "Dang Minh Duc",
    "Bui Ha My",
    "Do Quang Huy",
    "Ngo Phuong Linh",
    "Huynh Gia Huy",
    "Phan Minh Ngoc",
    "Truong Anh Minh",
    "Ly Bao Han",
    "Mai Thanh Dat",
    "Nguyen Thien An",
    "Tran Bao Nhi",
    "Le Gia Phuc",
    "Pham Ngoc Diep",
    "Hoang Khanh Linh",
    "Vo Duy Khang",
    "Dang Hoang Yen",
    "Bui Minh Nhat",
    "Do Thuy Duong",
    "Ngo Anh Quan",
    "Huynh Bao Anh",
    "Phan Quoc Huy",
    "Truong Minh Thu",
    "Ly Gia Minh",
    "Mai Anh Dao",
    "Nguyen Huu Phuoc",
    "Tran Ngoc Mai",
    "Le Minh Tam",
    "Pham Bao Vy",
    "Hoang Quoc Viet",
    "Vo Khanh An",
    "Dang Ngoc Han",
    "Bui Duy Anh",
    "Do Minh Khue",
    "Ngo Bao Long",
]


class Command(BaseCommand):
    help = "Seed vaccine stock and patient bookings for today through the next week."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Number of future days after today.")
        parser.add_argument("--today-count", type=int, default=15, help="Target active bookings for today.")
        parser.add_argument("--min-daily", type=int, default=5, help="Minimum target bookings for each future day.")
        parser.add_argument("--max-daily", type=int, default=10, help="Maximum target bookings for each future day.")
        parser.add_argument("--seed", type=int, default=20260421, help="Random seed for repeatable demo data.")

    def handle(self, *args, **options):
        if options["min_daily"] > options["max_daily"]:
            raise ValueError("--min-daily must be less than or equal to --max-daily.")

        rng = random.Random(options["seed"])
        today = timezone.localdate()
        end_date = today + timedelta(days=options["days"])
        patient_password_hash = make_password(PATIENT_PASSWORD)

        with transaction.atomic():
            vaccines = self._seed_vaccines(today)
            deleted_bookings, _ = Booking.objects.filter(
                note__startswith=SEED_NOTE_PREFIX,
                vaccine_date__gte=today,
                vaccine_date__lte=end_date,
            ).delete()

            summaries = []
            global_index = 0
            for offset in range(options["days"] + 1):
                booking_date = today + timedelta(days=offset)
                target_count = (
                    options["today_count"]
                    if offset == 0
                    else rng.randint(options["min_daily"], options["max_daily"])
                )
                existing_count = (
                    Booking.objects.filter(vaccine_date=booking_date)
                    .exclude(status=Booking.STATUS_CANCELLED)
                    .exclude(note__startswith=SEED_NOTE_PREFIX)
                    .count()
                )
                create_count = max(target_count - existing_count, 0)

                for day_index in range(create_count):
                    vaccine = vaccines[(global_index + day_index) % len(vaccines)]
                    self._create_patient_booking(
                        booking_date=booking_date,
                        day_index=day_index,
                        global_index=global_index + day_index,
                        offset=offset,
                        vaccine_name=vaccine.name,
                        patient_password_hash=patient_password_hash,
                        rng=rng,
                    )

                global_index += create_count
                final_count = Booking.objects.filter(vaccine_date=booking_date).exclude(
                    status=Booking.STATUS_CANCELLED
                ).count()
                summaries.append((booking_date, target_count, existing_count, create_count, final_count))

        self.stdout.write(self.style.SUCCESS(f"Seeded/updated {len(vaccines)} vaccine batches."))
        self.stdout.write(self.style.WARNING(f"Replaced {deleted_bookings} old generated booking records."))
        for booking_date, target_count, existing_count, create_count, final_count in summaries:
            self.stdout.write(
                f"{booking_date}: target {target_count}, existing {existing_count}, "
                f"created {create_count}, active total {final_count}"
            )
        self.stdout.write(self.style.SUCCESS("Weekly demo data is ready. Patient password: 123"))

    def _seed_vaccines(self, today):
        supplier, _ = Supplier.objects.update_or_create(
            name="VNVC Weekly Demo Supply",
            defaults={
                "phone": "02871029999",
                "email": "weekly-supply@vaccin.local",
                "address": "Ho Chi Minh City",
            },
        )
        for old_name, new_name in LEGACY_WEEK_LOCATION_NAME_MAP.items():
            StorageLocation.objects.filter(name=old_name).update(name=new_name)

        location, _ = StorageLocation.objects.update_or_create(
            name=WEEK_LOCATION_NAME,
            defaults={
                "description": (
                    "Kho demo cho dữ liệu lịch hẹn trong tuần, dùng với các lô vắc xin bảo quản 2-8°C."
                )
            },
        )
        frozen_location, _ = StorageLocation.objects.update_or_create(
            name=WEEK_FROZEN_LOCATION_NAME,
            defaults={"description": "Kho demo cho các lô vắc xin cần bảo quản đông hoặc âm sâu."},
        )

        StockImport.objects.filter(note__startswith=VACCINE_NOTE_PREFIX).delete()
        vaccines = []
        for index, (name, manufacturer, temperature) in enumerate(VACCINE_DATA, start=1):
            quantity = 80 + ((index * 11) % 90)
            expiration_date = today + timedelta(days=210 + index * 9)
            vaccine, _ = Vaccine.objects.update_or_create(
                batch_number=f"WEEK-DEMO-{index:03d}",
                defaults={
                    "name": name,
                    "manufacturer": manufacturer,
                    "quantity": quantity,
                    "minimum_stock": 10,
                    "expiration_date": expiration_date,
                    "storage_temperature": temperature,
                    "supplier": supplier,
                    "location": frozen_location if temperature.startswith("-") else location,
                },
            )
            StockImport.objects.create(
                vaccine=vaccine,
                quantity=quantity,
                import_date=today,
                supplier=supplier,
                note=f"{VACCINE_NOTE_PREFIX} {name}",
                created_by=User.objects.filter(role=User.ROLE_ADMIN, status=User.STATUS_ACTIVE).first(),
            )
            vaccines.append(vaccine)

        return vaccines

    def _create_patient_booking(
        self,
        *,
        booking_date,
        day_index,
        global_index,
        offset,
        vaccine_name,
        patient_password_hash,
        rng,
    ):
        email = f"week.patient.{booking_date:%Y%m%d}.{day_index + 1:02d}@vaccin.local"
        phone = f"09{offset + 1:02d}{day_index + 1:06d}"
        full_name = PATIENT_NAMES[global_index % len(PATIENT_NAMES)]
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "phone_number": phone,
                "gender": "female" if global_index % 2 else "male",
                "date_of_birth": booking_date.replace(year=booking_date.year - rng.randint(8, 55)),
                "blood_group": rng.choice(["A+", "B+", "O+", "AB+", "UNKNOWN"]),
                "allergies": "" if global_index % 5 else "Di ung hai san nhe",
                "medical_history": "" if global_index % 4 else "Tien su viem mui di ung",
                "password_hash": patient_password_hash,
                "auth_provider": User.AUTH_PROVIDER_LOCAL,
                "role": User.ROLE_CITIZEN,
                "status": User.STATUS_ACTIVE,
            },
        )

        status_value = self._status_for_booking(offset, day_index, rng)
        booking = Booking.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            email=email,
            vaccine_name=vaccine_name,
            vaccine_date=booking_date,
            dose_number=1 + ((global_index + offset) % 3),
            note=f"{SEED_NOTE_PREFIX} lich demo ngay {booking_date:%Y-%m-%d}",
            status=status_value,
            booking_source=Booking.BOOKING_SOURCE_ONLINE if day_index % 3 else Booking.BOOKING_SOURCE_WALKIN,
        )

        if status_value in {Booking.STATUS_CONFIRMED, Booking.STATUS_CHECKED_IN} and day_index % 2 == 0:
            PreScreeningDeclaration.objects.create(
                booking=booking,
                has_fever=False,
                has_allergy_history=(global_index % 7 == 0),
                has_chronic_condition=(global_index % 9 == 0),
                recent_symptoms="" if global_index % 6 else "Ho nhe, khong sot",
                current_medications="" if global_index % 8 else "Vitamin C",
                note="Khai bao demo truoc tiem",
            )

    def _status_for_booking(self, offset, day_index, rng):
        if offset == 0:
            pattern = [
                Booking.STATUS_PENDING,
                Booking.STATUS_PENDING,
                Booking.STATUS_PENDING,
                Booking.STATUS_PENDING,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CHECKED_IN,
                Booking.STATUS_CHECKED_IN,
                Booking.STATUS_CHECKED_IN,
            ]
            return pattern[day_index % len(pattern)]

        return rng.choice([Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED, Booking.STATUS_CONFIRMED])
