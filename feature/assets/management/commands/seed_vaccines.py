from django.core.management.base import BaseCommand
from feature.assets.models import Vaccine  # Đảm bảo import đúng model của bạn
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Tự động sinh 50 loại vắc xin vào database để test'

    def handle(self, *args, **kwargs):
        self.stdout.write("Đang dọn dẹp kho vắc xin cũ (nếu có)...")
        Vaccine.objects.all().delete() # Xóa data cũ để tránh lỗi trùng lặp tên

        vaccine_list = []
        manufacturers = ['Pfizer', 'Moderna', 'AstraZeneca', 'Sanofi', 'GSK', 'VNVC']

        self.stdout.write("Đang tiến hành tạo dữ liệu...")
        
        # Vòng lặp tạo 50 loại vắc xin
        for i in range(1, 51):
            name = f"Vaccine Test Mẫu số {i}"
            manufacturer = random.choice(manufacturers)
            quantity = random.randint(50, 500)
            
            vaccine = Vaccine(
                name=name,
                manufacturer=manufacturer,
                batch_number=f"LOT-{random.randint(1000, 9999)}-{i}",
                quantity=quantity,
                expiration_date=timezone.now().date() + timezone.timedelta(days=random.randint(365, 730)),
                storage_temperature="2-8°C"
            )
            vaccine_list.append(vaccine)

        # Đẩy toàn bộ list vào database trong 1 lần duy nhất
        Vaccine.objects.bulk_create(vaccine_list)

        self.stdout.write(self.style.SUCCESS('✅ Thành công! Đã tự động thêm 50 loại vắc xin vào kho.'))