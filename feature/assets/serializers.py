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
            raise serializers.ValidationError("Khong the tao vac-xin co han su dung trong qua khu.")
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("So luong ton khong duoc am.")
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Gia vac-xin khong duoc am.")
        return value

    def validate_minimum_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Ton toi thieu khong duoc am.")
        return value


class StockImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockImport
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("So luong nhap phai lon hon 0.")
        return value


class StockExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockExport
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate(self, attrs):
        vaccine = attrs.get("vaccine") or getattr(self.instance, "vaccine", None)
        quantity = attrs.get("quantity") or getattr(self.instance, "quantity", None)

        if quantity <= 0:
            raise serializers.ValidationError("So luong xuat phai lon hon 0.")

        available_quantity = vaccine.quantity
        if self.instance and self.instance.vaccine_id == vaccine.id:
            available_quantity += self.instance.quantity

        if available_quantity < quantity:
            raise serializers.ValidationError("So luong xuat lon hon so luong ton kho.")

        if vaccine.expiration_date < timezone.now().date():
            raise serializers.ValidationError("Khong the xuat vac-xin da het han.")

        return attrs


class StockAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAdjustment
        fields = "__all__"
        read_only_fields = ("created_by",)

    def validate(self, attrs):
        vaccine = attrs.get("vaccine") or getattr(self.instance, "vaccine", None)
        adjustment_type = attrs.get("adjustment_type") or getattr(self.instance, "adjustment_type", None)
        quantity = attrs.get("quantity") or getattr(self.instance, "quantity", None)

        if quantity <= 0:
            raise serializers.ValidationError("So luong dieu chinh phai lon hon 0.")

        available_quantity = vaccine.quantity
        if self.instance and self.instance.vaccine_id == vaccine.id:
            if self.instance.adjustment_type == "decrease":
                available_quantity += self.instance.quantity
            elif self.instance.adjustment_type == "increase":
                available_quantity -= self.instance.quantity

        if adjustment_type == "decrease" and available_quantity < quantity:
            raise serializers.ValidationError("Khong the dieu chinh giam lon hon so luong ton kho.")

        return attrs
