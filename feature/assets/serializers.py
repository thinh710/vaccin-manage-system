from django.utils import timezone
from rest_framework import serializers

from .models import (
    Supplier,
    StorageLocation,
    Vaccine,
    StockImport,
    StockExport,
    StockAdjustment,
)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class StorageLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        fields = "__all__"


class VaccineSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = Vaccine
        fields = "__all__"

    def validate_expiration_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Không thể tạo vắc-xin có hạn sử dụng trong quá khứ.")
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Số lượng tồn không được âm.")
        return value

    def validate_minimum_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Tồn tối thiểu không được âm.")
        return value


class StockImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockImport
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Số lượng nhập phải lớn hơn 0.")
        return value


class StockExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockExport
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate(self, attrs):
        vaccine = attrs["vaccine"]
        quantity = attrs["quantity"]

        if quantity <= 0:
            raise serializers.ValidationError("Số lượng xuất phải lớn hơn 0.")

        if vaccine.quantity < quantity:
            raise serializers.ValidationError("Số lượng xuất lớn hơn số lượng tồn kho.")

        if vaccine.expiration_date < timezone.now().date():
            raise serializers.ValidationError("Không thể xuất vắc-xin đã hết hạn.")

        return attrs


class StockAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAdjustment
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate(self, attrs):
        vaccine = attrs["vaccine"]
        adjustment_type = attrs["adjustment_type"]
        quantity = attrs["quantity"]

        if quantity <= 0:
            raise serializers.ValidationError("Số lượng điều chỉnh phải lớn hơn 0.")

        if adjustment_type == "decrease" and vaccine.quantity < quantity:
            raise serializers.ValidationError("Không thể điều chỉnh giảm lớn hơn số lượng tồn kho.")

        return attrs