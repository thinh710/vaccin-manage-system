from django.db import models
from django.utils import timezone

from feature.authentication.models import User


class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Tên nhà cung cấp")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Số điện thoại")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Địa chỉ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_supplier"
        verbose_name = "Nhà cung cấp"
        verbose_name_plural = "Nhà cung cấp"

    def __str__(self):
        return self.name


class StorageLocation(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên vị trí")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mô tả")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_storage_location"
        verbose_name = "Vị trí bảo quản"
        verbose_name_plural = "Vị trí bảo quản"

    def __str__(self):
        return self.name


class Vaccine(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên vắc-xin")
    manufacturer = models.CharField(max_length=100, verbose_name="Nhà sản xuất")
    batch_number = models.CharField(max_length=50, unique=True, verbose_name="Số lô")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng tồn")
    minimum_stock = models.PositiveIntegerField(default=10, verbose_name="Tồn tối thiểu")
    expiration_date = models.DateField(verbose_name="Hạn sử dụng")
    storage_temperature = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Nhiệt độ bảo quản",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccines",
        verbose_name="Nhà cung cấp",
    )
    location = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccines",
        verbose_name="Vị trí bảo quản",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_vaccine"
        verbose_name = "Vắc-xin"
        verbose_name_plural = "Vắc-xin"

    def __str__(self):
        return f"{self.name} - {self.batch_number}"

    @property
    def is_low_stock(self):
        return self.quantity <= self.minimum_stock

    @property
    def is_expired(self):
        return self.expiration_date < timezone.now().date()


class StockImport(models.Model):
    vaccine = models.ForeignKey(
        Vaccine,
        on_delete=models.CASCADE,
        related_name="imports",
        verbose_name="Vắc-xin",
    )
    quantity = models.PositiveIntegerField(verbose_name="Số lượng nhập")
    import_date = models.DateField(verbose_name="Ngày nhập")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imports",
        verbose_name="Nhà cung cấp",
    )
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_imports",
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_stock_import"
        verbose_name = "Phiếu nhập kho"
        verbose_name_plural = "Phiếu nhập kho"

    def __str__(self):
        return f"Nhập {self.vaccine.name} - {self.quantity}"


class StockExport(models.Model):
    EXPORT_TYPE_TRANSFER = 'transfer'
    EXPORT_TYPE_DISPOSAL = 'disposal'
    EXPORT_TYPE_EXPIRED  = 'expired'

    EXPORT_TYPE_CHOICES = [
        (EXPORT_TYPE_TRANSFER, 'Xuất chuyển'),
        (EXPORT_TYPE_DISPOSAL, 'Xuất hủy'),
        (EXPORT_TYPE_EXPIRED,  'Hủy hết hạn'),
    ]

    vaccine = models.ForeignKey(
        Vaccine,
        on_delete=models.CASCADE,
        related_name="exports",
        verbose_name="Vắc-xin",
    )
    quantity = models.PositiveIntegerField(verbose_name="Số lượng xuất")
    export_date = models.DateField(verbose_name="Ngày xuất")
    destination = models.CharField(max_length=150, verbose_name="Nơi nhận")
    export_type = models.CharField(
        max_length=20,
        choices=EXPORT_TYPE_CHOICES,
        default=EXPORT_TYPE_TRANSFER,
        verbose_name="Loại xuất",
    )
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_exports",
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_stock_export"
        verbose_name = "Phiếu xuất kho"
        verbose_name_plural = "Phiếu xuất kho"

    def __str__(self):
        return f"Xuất {self.vaccine.name} - {self.quantity}"


class StockAdjustment(models.Model):
    ADJUSTMENT_TYPE_CHOICES = (
        ("increase", "Tăng"),
        ("decrease", "Giảm"),
    )

    vaccine = models.ForeignKey(
        Vaccine,
        on_delete=models.CASCADE,
        related_name="adjustments",
        verbose_name="Vắc-xin",
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=ADJUSTMENT_TYPE_CHOICES,
        verbose_name="Loại điều chỉnh",
    )
    quantity = models.PositiveIntegerField(verbose_name="Số lượng điều chỉnh")
    reason = models.CharField(max_length=255, verbose_name="Lý do")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assets_stock_adjustment"
        verbose_name = "Phiếu điều chỉnh kho"
        verbose_name_plural = "Phiếu điều chỉnh kho"

    def __str__(self):
        return f"{self.adjustment_type} - {self.vaccine.name} - {self.quantity}"
