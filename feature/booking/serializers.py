from django.utils import timezone
from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    can_edit = serializers.SerializerMethodField(read_only=True)
    can_cancel = serializers.SerializerMethodField(read_only=True)
    can_reschedule = serializers.SerializerMethodField(read_only=True)
    customer_label = serializers.SerializerMethodField(read_only=True)
    pre_screening = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'user',
            'full_name',
            'phone',
            'email',
            'vaccine_name',
            'vaccine_date',
            'dose_number',
            'note',
            'status',
            'created_at',
            'updated_at',
            'can_edit',
            'can_cancel',
            'can_reschedule',
            'customer_label',
            'pre_screening',
        ]
        read_only_fields = ['user', 'created_at', 'updated_at', 'can_edit', 'can_cancel', 'can_reschedule', 'customer_label', 'pre_screening']

    def validate_phone(self, value):
        digits = ''.join(character for character in value if character.isdigit())
        if len(digits) < 9:
            raise serializers.ValidationError('Số điện thoại không hợp lệ.')
        return value.strip()

    def validate_vaccine_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Tên vắc xin quá ngắn.')
        return value

    def validate_vaccine_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError('Ngày tiêm phải từ hôm nay trở đi.')
        return value

    def validate(self, attrs):
        instance = self.instance
        user = self.context.get('session_user')
        vaccine_date = attrs.get('vaccine_date', getattr(instance, 'vaccine_date', None))
        vaccine_name = attrs.get('vaccine_name', getattr(instance, 'vaccine_name', '')).strip()

        if instance and instance.status in [Booking.STATUS_COMPLETED, Booking.STATUS_CANCELLED]:
            next_status = attrs.get('status')
            if next_status and next_status != instance.status:
                raise serializers.ValidationError('Booking đã đóng, không thể đổi trạng thái thêm nữa.')
            editable_fields = set(attrs.keys()) - {'status'}
            if editable_fields:
                raise serializers.ValidationError('Booking đã đóng, không thể chỉnh sửa thông tin này.')

        if user and user.role == user.ROLE_CITIZEN and vaccine_date:
            duplicated_booking = Booking.objects.filter(
                user=user,
                vaccine_name__iexact=vaccine_name,
                vaccine_date=vaccine_date,
                status__in=Booking.ACTIVE_STATUSES,
            )
            if instance:
                duplicated_booking = duplicated_booking.exclude(pk=instance.pk)
            if duplicated_booking.exists():
                raise serializers.ValidationError('Bạn đã có booking cùng vắc xin trong ngày này.')

        return attrs

    def get_can_edit(self, obj):
        return obj.status in [Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED, Booking.STATUS_DELAYED]

    def get_can_cancel(self, obj):
        return obj.status in [Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED, Booking.STATUS_DELAYED]

    def get_can_reschedule(self, obj):
        return obj.status == Booking.STATUS_DELAYED and not obj.rescheduled_bookings.exists()

    def get_customer_label(self, obj):
        return f'{obj.full_name} - {obj.phone}'

    def get_pre_screening(self, obj):
        if not hasattr(obj, 'pre_screening'):
            return None

        declaration = obj.pre_screening
        return {
            'has_fever': declaration.has_fever,
            'has_allergy_history': declaration.has_allergy_history,
            'has_chronic_condition': declaration.has_chronic_condition,
            'recent_symptoms': declaration.recent_symptoms or '',
            'current_medications': declaration.current_medications or '',
            'note': declaration.note or '',
            'updated_at': declaration.updated_at.isoformat(),
        }
