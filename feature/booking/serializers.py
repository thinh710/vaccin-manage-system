from django.utils import timezone
from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    can_edit = serializers.SerializerMethodField(read_only=True)
    can_cancel = serializers.SerializerMethodField(read_only=True)
    can_reschedule = serializers.SerializerMethodField(read_only=True)
    can_confirm_eligibility = serializers.SerializerMethodField(read_only=True)
    can_doctor_review_online = serializers.SerializerMethodField(read_only=True)
    can_confirm_deposit = serializers.SerializerMethodField(read_only=True)
    customer_label = serializers.SerializerMethodField(read_only=True)
    pre_screening = serializers.SerializerMethodField(read_only=True)
    online_review = serializers.SerializerMethodField(read_only=True)
    needs_deposit_reminder = serializers.SerializerMethodField(read_only=True)
    deposit_deadline_status = serializers.SerializerMethodField(read_only=True)
    deposit_deadline_message = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'user',
            'vaccine',
            'full_name',
            'phone',
            'email',
            'vaccine_name',
            'vaccine_date',
            'dose_number',
            'total_amount',
            'deposit_amount',
            'deposit_deadline',
            'deposit_paid_at',
            'deposit_note',
            'eligibility_confirmed_at',
            'booking_source',
            'note',
            'status',
            'created_at',
            'updated_at',
            'can_edit',
            'can_cancel',
            'can_reschedule',
            'can_confirm_eligibility',
            'can_doctor_review_online',
            'can_confirm_deposit',
            'customer_label',
            'pre_screening',
            'online_review',
            'needs_deposit_reminder',
            'deposit_deadline_status',
            'deposit_deadline_message',
        ]
        read_only_fields = [
            'user',
            'vaccine',
            'total_amount',
            'deposit_amount',
            'deposit_deadline',
            'deposit_paid_at',
            'deposit_note',
            'eligibility_confirmed_at',
            'booking_source',
            'created_at',
            'updated_at',
            'can_edit',
            'can_cancel',
            'can_reschedule',
            'can_confirm_eligibility',
            'can_doctor_review_online',
            'can_confirm_deposit',
            'customer_label',
            'pre_screening',
            'online_review',
            'needs_deposit_reminder',
            'deposit_deadline_status',
            'deposit_deadline_message',
        ]

    def validate_phone(self, value):
        digits = ''.join(character for character in value if character.isdigit())
        if len(digits) < 9:
            raise serializers.ValidationError('So dien thoai khong hop le.')
        return value.strip()

    def validate_vaccine_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Ten vac xin qua ngan.')
        return value

    def validate_vaccine_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError('Ngay tiem phai tu hom nay tro di.')
        return value

    def validate(self, attrs):
        instance = self.instance
        user = self.context.get('session_user')
        vaccine_date = attrs.get('vaccine_date', getattr(instance, 'vaccine_date', None))
        vaccine_name = attrs.get('vaccine_name', getattr(instance, 'vaccine_name', '')).strip()

        if instance and instance.status in [Booking.STATUS_COMPLETED, Booking.STATUS_CANCELLED]:
            next_status = attrs.get('status')
            if next_status and next_status != instance.status:
                raise serializers.ValidationError('Booking da dong, khong the doi trang thai them nua.')
            editable_fields = set(attrs.keys()) - {'status'}
            if editable_fields:
                raise serializers.ValidationError('Booking da dong, khong the chinh sua thong tin nay.')

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
                raise serializers.ValidationError('Ban da co booking cung vac xin trong ngay nay.')

        return attrs

    def create(self, validated_data):
        booking = Booking(**validated_data)
        self._apply_context_changes(booking)
        booking.save()
        return booking

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._apply_context_changes(instance)
        instance.save()
        return instance

    def _apply_context_changes(self, booking):
        if 'resolved_vaccine' in self.context:
            booking.vaccine = self.context.get('resolved_vaccine')
            if booking.vaccine is not None:
                booking.vaccine_name = booking.vaccine.name

        if self.context.get('reset_eligibility'):
            booking.clear_eligibility_confirmation()
        if self.context.get('reset_deposit'):
            booking.clear_deposit_confirmation()

        if self.context.get('eligibility_confirmed_by') is not None:
            booking.eligibility_confirmed_by = self.context['eligibility_confirmed_by']
            booking.eligibility_confirmed_at = timezone.now()
        if self.context.get('deposit_paid_by') is not None:
            booking.deposit_paid_by = self.context['deposit_paid_by']
            booking.deposit_paid_at = timezone.now()
            if 'deposit_note' in self.context:
                booking.deposit_note = self.context.get('deposit_note') or ''

        if 'force_status' in self.context:
            booking.status = self.context['force_status']

        if self.context.get('recalculate_pricing', True):
            booking.recalculate_financials()

    def _get_days_until_deadline(self, obj):
        if not obj.deposit_deadline:
            return None
        return (obj.deposit_deadline - timezone.localdate()).days

    def _get_deposit_deadline_state(self, obj):
        if obj.booking_source == Booking.BOOKING_SOURCE_WALKIN or not obj.deposit_deadline:
            return 'not_applicable'
        if obj.deposit_paid_at:
            return 'paid'
        if obj.status != Booking.STATUS_DEPOSIT_PENDING:
            return 'not_applicable'

        days_until_deadline = self._get_days_until_deadline(obj)
        if days_until_deadline is None:
            return 'not_applicable'
        if days_until_deadline < 0:
            return 'expired'
        if days_until_deadline <= 1:
            return 'warning'
        if days_until_deadline <= 3:
            return 'upcoming'
        return 'not_applicable'

    def get_can_edit(self, obj):
        return obj.status in [
            Booking.STATUS_AWAITING_ELIGIBILITY,
            Booking.STATUS_PENDING,
            Booking.STATUS_DEPOSIT_PENDING,
            Booking.STATUS_CONFIRMED,
            Booking.STATUS_DELAYED,
            Booking.STATUS_INELIGIBLE,
        ]

    def get_can_cancel(self, obj):
        return obj.status in [
            Booking.STATUS_AWAITING_ELIGIBILITY,
            Booking.STATUS_PENDING,
            Booking.STATUS_DEPOSIT_PENDING,
            Booking.STATUS_CONFIRMED,
            Booking.STATUS_DELAYED,
            Booking.STATUS_INELIGIBLE,
        ]

    def get_can_reschedule(self, obj):
        return obj.status == Booking.STATUS_DELAYED and not obj.rescheduled_bookings.exists()

    def get_can_confirm_eligibility(self, obj):
        return False

    def get_can_doctor_review_online(self, obj):
        user = self.context.get('session_user')
        return bool(
            user
            and user.role == user.ROLE_DOCTOR
            and obj.booking_source == Booking.BOOKING_SOURCE_ONLINE
            and obj.status in [Booking.STATUS_AWAITING_ELIGIBILITY, Booking.STATUS_PENDING]
            and hasattr(obj, 'pre_screening')
        )

    def get_can_confirm_deposit(self, obj):
        user = self.context.get('session_user')
        return bool(
            user
            and user.role == user.ROLE_STAFF
            and obj.booking_source == Booking.BOOKING_SOURCE_ONLINE
            and obj.status == Booking.STATUS_DEPOSIT_PENDING
            and not obj.deposit_paid_at
        )

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
            'has_severe_allergy': declaration.has_severe_allergy,
            'severe_allergy_details': declaration.severe_allergy_details or '',
            'has_current_health_issue': declaration.has_current_health_issue,
            'current_health_issue_details': declaration.current_health_issue_details or '',
            'had_recent_vaccination': declaration.had_recent_vaccination,
            'recent_vaccination_details': declaration.recent_vaccination_details or '',
            'uses_immunosuppressive_medication': declaration.uses_immunosuppressive_medication,
            'immunosuppressive_medication_details': declaration.immunosuppressive_medication_details or '',
            'has_pregnancy_or_breastfeeding_consideration': declaration.has_pregnancy_or_breastfeeding_consideration,
            'pregnancy_or_breastfeeding_details': declaration.pregnancy_or_breastfeeding_details or '',
            'note': declaration.note or '',
            'updated_at': declaration.updated_at.isoformat(),
        }

    def get_online_review(self, obj):
        if not hasattr(obj, 'online_review'):
            return None

        review = obj.online_review
        return {
            'decision': review.decision,
            'doctor_note': review.doctor_note or '',
            'reviewed_by': review.reviewed_by_id,
            'reviewed_by_name': review.reviewed_by.full_name if review.reviewed_by else '',
            'reviewed_at': review.reviewed_at.isoformat(),
        }

    def get_needs_deposit_reminder(self, obj):
        return self._get_deposit_deadline_state(obj) in ['upcoming', 'warning']

    def get_deposit_deadline_status(self, obj):
        return self._get_deposit_deadline_state(obj)

    def get_deposit_deadline_message(self, obj):
        state = self._get_deposit_deadline_state(obj)
        if state == 'not_applicable':
            return ''
        if state == 'paid':
            return 'Da xac nhan dat coc.'
        if state == 'expired':
            return 'Dat coc da qua han, booking se bi huy neu chua duoc xu ly.'

        deadline_text = obj.deposit_deadline.strftime('%d/%m/%Y')
        days_until_deadline = self._get_days_until_deadline(obj)
        if state == 'warning':
            if days_until_deadline == 0:
                return f'Hom nay la han cuoi dat coc ({deadline_text}).'
            return f'Can dat coc truoc {deadline_text}. Booking dang sap het han.'
        return f'Can dat coc truoc {deadline_text}.'
