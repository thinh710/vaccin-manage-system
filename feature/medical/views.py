import calendar
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from feature.assets.models import Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.booking.serializers import BookingSerializer
from feature.booking.views import _resolve_vaccine_by_name
from feature.csrf import csrf_protect_session_api

from .models import OnlineEligibilityReview, PostInjectionTracking, PreScreeningDeclaration, ScreeningResult, VaccinationLog
from .serializers import (
    OnlineEligibilityReviewSerializer,
    PostInjectionTrackingSerializer,
    PreScreeningDeclarationSerializer,
    ScreeningResultSerializer,
    VaccinationLogSerializer,
)


def _serialize_declaration(declaration):
    if not declaration:
        return None
    return {
        "id": declaration.id,
        "booking": declaration.booking_id,
        "has_fever": declaration.has_fever,
        "has_allergy_history": declaration.has_allergy_history,
        "has_chronic_condition": declaration.has_chronic_condition,
        "recent_symptoms": declaration.recent_symptoms or "",
        "current_medications": declaration.current_medications or "",
        "has_severe_allergy": declaration.has_severe_allergy,
        "severe_allergy_details": declaration.severe_allergy_details or "",
        "has_current_health_issue": declaration.has_current_health_issue,
        "current_health_issue_details": declaration.current_health_issue_details or "",
        "had_recent_vaccination": declaration.had_recent_vaccination,
        "recent_vaccination_details": declaration.recent_vaccination_details or "",
        "uses_immunosuppressive_medication": declaration.uses_immunosuppressive_medication,
        "immunosuppressive_medication_details": declaration.immunosuppressive_medication_details or "",
        "has_pregnancy_or_breastfeeding_consideration": declaration.has_pregnancy_or_breastfeeding_consideration,
        "pregnancy_or_breastfeeding_details": declaration.pregnancy_or_breastfeeding_details or "",
        "note": declaration.note or "",
        "created_at": declaration.created_at.isoformat(),
        "updated_at": declaration.updated_at.isoformat(),
    }


def _serialize_online_review(online_review):
    if not online_review:
        return None
    return {
        "id": online_review.id,
        "booking": online_review.booking_id,
        "decision": online_review.decision,
        "doctor_note": online_review.doctor_note or "",
        "reviewed_by": online_review.reviewed_by_id,
        "reviewed_by_name": online_review.reviewed_by.full_name if online_review.reviewed_by else "",
        "reviewed_at": online_review.reviewed_at.isoformat(),
    }


def _serialize_screening_result(screening_result):
    if not screening_result:
        return None
    return {
        "id": screening_result.id,
        "booking": screening_result.booking_id,
        "temperature": screening_result.temperature,
        "blood_pressure": screening_result.blood_pressure,
        "decision": screening_result.decision,
        "is_eligible": screening_result.is_eligible,
        "doctor_note": screening_result.doctor_note or "",
        "created_at": screening_result.created_at.isoformat(),
    }


def _get_session_user(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None, redirect("/auth/login-page/")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None, redirect("/auth/login-page/")

    return user, None


def _build_schedule_context(today):
    calendar_builder = calendar.Calendar(firstweekday=0)
    month_weeks = []
    booking_dates = set(
        Booking.objects.filter(vaccine_date__year=today.year, vaccine_date__month=today.month)
        .exclude(status__in=[Booking.STATUS_CANCELLED, Booking.STATUS_INELIGIBLE])
        .values_list("vaccine_date", flat=True)
    )

    for week in calendar_builder.monthdayscalendar(today.year, today.month):
        cells = []
        for day in week:
            cell_date = None
            if day:
                cell_date = today.replace(day=day)
            cells.append(
                {
                    "day": day,
                    "is_today": bool(cell_date and cell_date == today),
                    "has_booking": bool(cell_date and cell_date in booking_dates),
                }
            )
        month_weeks.append(cells)

    vaccination_schedule = list(
        Booking.objects.filter(vaccine_date__gte=today)
        .exclude(status__in=[Booking.STATUS_CANCELLED, Booking.STATUS_INELIGIBLE])
        .order_by("vaccine_date", "id")[:4]
    )
    health_schedule = list(
        Booking.objects.filter(vaccine_date__gte=today)
        .filter(
            status__in=[
                Booking.STATUS_AWAITING_ELIGIBILITY,
                Booking.STATUS_PENDING,
                Booking.STATUS_DEPOSIT_PENDING,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CHECKED_IN,
                Booking.STATUS_DELAYED,
            ]
        )
        .order_by("vaccine_date", "id")[:4]
    )

    return {
        "calendar_month_label": f"ThÃ¡ng {today.month}",
        "calendar_weekdays": ["T2", "T3", "T4", "T5", "T6", "T7", "CN"],
        "calendar_weeks": month_weeks,
        "vaccination_schedule": vaccination_schedule,
        "health_schedule": health_schedule,
    }


@ensure_csrf_cookie
def medical_dashboard(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role == User.ROLE_ADMIN:
        return redirect("/assets/")

    if user.role not in [User.ROLE_STAFF, User.ROLE_DOCTOR]:
        return redirect("/users/dashboard/")

    today = date.today()
    vaccines = list(
        Vaccine.objects.filter(
            quantity__gt=0,
            expiration_date__gte=timezone.localdate(),
        ).order_by("name").values("id", "name", "quantity", "batch_number")
    )
    context = {
        "user": user,
        "today": today,
        "vaccines": vaccines,
    }
    context.update(_build_schedule_context(today))
    return render(request, "medical/medical.html", context)


def _get_api_session_user(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None


def _require_staff_user(request):
    """DÃ¹ng cho bÆ°á»›c check-in, inject, monitor â€” Staff váº­n hÃ nh."""
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Báº¡n chÆ°a Ä‘Äƒng nháº­p."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role != User.ROLE_STAFF:
        return None, Response({"detail": "Chá»©c nÄƒng nÃ y chá»‰ dÃ nh cho nhÃ¢n viÃªn."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _require_medical_read_user(request):
    """DÃ¹ng cho cÃ¡c mÃ n hÃ¬nh/list API mÃ  staff vÃ  doctor cáº§n xem."""
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Báº¡n chÆ°a Ä‘Äƒng nháº­p."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_STAFF, User.ROLE_DOCTOR]:
        return None, Response({"detail": "Báº¡n khÃ´ng cÃ³ quyá»n dÃ¹ng chá»©c nÄƒng y khoa."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _require_doctor_user(request):
    """DÃ¹ng cho bÆ°á»›c khÃ¡m sÃ ng lá»c â€” chá»‰ Doctor."""
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Báº¡n chÆ°a Ä‘Äƒng nháº­p."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role != User.ROLE_DOCTOR:
        return None, Response(
            {"detail": "Chá»‰ bÃ¡c sÄ© má»›i Ä‘Æ°á»£c thá»±c hiá»‡n khÃ¡m sÃ ng lá»c."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return user, None


def _find_active_citizen_by_email(email):
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    return User.objects.filter(
        email__iexact=normalized_email,
        role=User.ROLE_CITIZEN,
        status=User.STATUS_ACTIVE,
    ).first()


def _can_access_booking(user, booking):
    if user.role == User.ROLE_ADMIN:
        return False
    if user.role in [User.ROLE_STAFF, User.ROLE_DOCTOR]:
        return True
    if user.role != User.ROLE_CITIZEN:
        return False
    if booking.user_id and booking.user_id == user.id:
        return True
    return bool(user.email and booking.email and booking.email.lower() == user.email.lower())


@api_view(["GET"])
def today_bookings(request):
    user, error_response = _require_medical_read_user(request)
    if error_response:
        return error_response

    bookings = (
        Booking.objects.exclude(status__in=[Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED])
        .filter(
            Q(vaccine_date__gte=timezone.localdate())
            | Q(
                status__in=[
                    Booking.STATUS_CHECKED_IN,
                    Booking.STATUS_READY_TO_INJECT,
                    Booking.STATUS_IN_OBSERVATION,
                    Booking.STATUS_DELAYED,
                    Booking.STATUS_INELIGIBLE,
                ]
            )
        )
        .select_related("pre_screening", "online_review", "online_review__reviewed_by")
        .order_by("vaccine_date", "id")
    )
    serializer = BookingSerializer(bookings, many=True, context={"session_user": user})
    return Response(serializer.data)


@csrf_protect_session_api
@api_view(["GET", "POST", "PATCH"])
def pre_screening_declaration_detail(request, booking_id):
    user = _get_api_session_user(request)
    if not user:
        return Response({"detail": "Báº¡n chÆ°a Ä‘Äƒng nháº­p."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "KhÃ´ng tÃ¬m tháº¥y booking."}, status=status.HTTP_404_NOT_FOUND)

    if not _can_access_booking(user, booking):
        return Response({"detail": "Báº¡n khÃ´ng cÃ³ quyá»n truy cáº­p booking nÃ y."}, status=status.HTTP_403_FORBIDDEN)

    declaration = PreScreeningDeclaration.objects.filter(booking=booking).first()
    online_review = OnlineEligibilityReview.objects.filter(booking=booking).select_related("reviewed_by").first()

    if request.method == "GET":
        screening_result = ScreeningResult.objects.filter(booking=booking).first()
        return Response(
            {
                "booking": booking.id,
                "declaration": _serialize_declaration(declaration),
                "online_review": _serialize_online_review(online_review),
                "screening_result": _serialize_screening_result(screening_result),
            }
        )

    # POST / PATCH â€” citizen hoáº·c staff Ä‘á»u Ä‘Æ°á»£c (staff Ä‘iá»n há»™ khi walk-in)
    if user.role not in [User.ROLE_CITIZEN, User.ROLE_STAFF]:
        return Response(
            {"detail": "Báº¡n khÃ´ng cÃ³ quyá»n gá»­i khai bÃ¡o sÃ ng lá»c."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if booking.status in [Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED, Booking.STATUS_INELIGIBLE]:
        return Response(
            {"detail": "Booking nÃ y khÃ´ng cÃ²n má»Ÿ Ä‘á»ƒ khai bÃ¡o sÃ ng lá»c."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if declaration:
        serializer = PreScreeningDeclarationSerializer(declaration, data=request.data, partial=True)
    else:
        serializer = PreScreeningDeclarationSerializer(data=request.data)

    if serializer.is_valid():
        saved_declaration = serializer.save(booking=booking)

        if booking.booking_source == Booking.BOOKING_SOURCE_ONLINE and booking.status in [
            Booking.STATUS_DEPOSIT_PENDING,
            Booking.STATUS_CONFIRMED,
            Booking.STATUS_DELAYED,
            Booking.STATUS_INELIGIBLE,
        ]:
            OnlineEligibilityReview.objects.filter(booking=booking).delete()
            booking.clear_eligibility_confirmation()
            booking.clear_deposit_confirmation()
            booking.status = Booking.STATUS_AWAITING_ELIGIBILITY
            booking.save(
                update_fields=[
                    "status",
                    "eligibility_confirmed_at",
                    "eligibility_confirmed_by",
                    "deposit_paid_at",
                    "deposit_paid_by",
                    "deposit_note",
                    "updated_at",
                ]
            )

        return Response(
            PreScreeningDeclarationSerializer(saved_declaration).data,
            status=status.HTTP_200_OK if declaration else status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_protect_session_api
@api_view(["PATCH"])
def check_in_booking(request, booking_id):
    _, error_response = _require_staff_user(request)
    if error_response:
        return error_response

    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Khong tim thay booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status in [Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED]:
        return Response({"detail": "Khong the check-in booking nay."}, status=status.HTTP_400_BAD_REQUEST)

    if booking.status != Booking.STATUS_CONFIRMED:
        return Response(
            {"detail": "Can xac nhan lich truoc khi check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not PreScreeningDeclaration.objects.filter(booking=booking).exists():
        return Response(
            {"detail": "Can hoan tat khai bao y te truoc khi check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking.status = Booking.STATUS_CHECKED_IN
    booking.save(update_fields=["status", "updated_at"])

    return Response({"status": "checked_in", "booking_id": booking.id})


@csrf_protect_session_api
@api_view(["POST"])
def submit_screening_result(request):
    """BÆ°á»›c 4 â€” chá»‰ Doctor thá»±c hiá»‡n khÃ¡m sÃ ng lá»c."""
    _, error_response = _require_doctor_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "KhÃ´ng tÃ¬m tháº¥y booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_CHECKED_IN:
        return Response(
            {"detail": "Chá»‰ Ä‘Æ°á»£c khÃ¡m sÃ ng lá»c khi booking Ä‘Ã£ check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not PreScreeningDeclaration.objects.filter(booking=booking).exists():
        return Response(
            {"detail": "Booking chua co khai bao y te. Can hoan tat khai bao truoc khi bac si sang loc."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    decision = request.data.get("decision")
    if decision not in ("eligible", "delayed", "cancelled"):
        return Response(
            {"detail": "TrÆ°á»ng 'decision' pháº£i lÃ : eligible, delayed, hoáº·c cancelled."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        screening = ScreeningResult.objects.get(booking=booking)
        serializer = ScreeningResultSerializer(screening, data=request.data)
    except ScreeningResult.DoesNotExist:
        serializer = ScreeningResultSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()

        # 3 nhÃ¡nh quyáº¿t Ä‘á»‹nh dá»±a vÃ o field 'decision'
        if decision == "eligible":
            booking.status = Booking.STATUS_READY_TO_INJECT
        elif decision == "delayed":
            booking.status = Booking.STATUS_DELAYED
        elif decision == "cancelled":
            booking.status = Booking.STATUS_INELIGIBLE

        booking.save(update_fields=["status", "updated_at"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_protect_session_api
@api_view(["POST"])
def submit_vaccination_log(request):
    """BÆ°á»›c 5 â€” Staff xÃ¡c nháº­n tiÃªm. Booking pháº£i á»Ÿ ready_to_inject."""
    _, error_response = _require_staff_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "KhÃ´ng tÃ¬m tháº¥y booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_READY_TO_INJECT:
        return Response(
            {"detail": "Booking chÆ°a Ä‘Æ°á»£c bÃ¡c sÄ© chá»‰ Ä‘á»‹nh tiÃªm."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data.copy()
    vaccine_obj = None
    batch_number = (data.get("batch_number") or "").strip()
    today = timezone.localdate()

    if data.get("vaccine"):
        try:
            vaccine_obj = Vaccine.objects.get(pk=data.get("vaccine"))
        except (TypeError, ValueError, Vaccine.DoesNotExist):
            return Response(
                {"detail": "KhÃ´ng tÃ¬m tháº¥y váº¯c xin Ä‘Æ°á»£c chá»n."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vaccine_obj.quantity <= 0 or vaccine_obj.expiration_date < today:
            return Response(
                {"detail": "Váº¯c xin Ä‘Æ°á»£c chá»n Ä‘Ã£ háº¿t hÃ ng hoáº·c háº¿t háº¡n, khÃ´ng thá»ƒ ghi nháº­n tiÃªm."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if batch_number and vaccine_obj.batch_number != batch_number:
            return Response(
                {"detail": "Sá»‘ lÃ´ khÃ´ng khá»›p vá»›i váº¯c xin Ä‘Æ°á»£c chá»n."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking_vaccine_name = (booking.vaccine_name or "").strip().lower()
        selected_vaccine_name = (vaccine_obj.name or "").strip().lower()
        has_matching_batch = bool(batch_number and vaccine_obj.batch_number == batch_number)
        if booking_vaccine_name and selected_vaccine_name != booking_vaccine_name and not has_matching_batch:
            return Response(
                {"detail": "Váº¯c xin Ä‘Æ°á»£c chá»n khÃ´ng khá»›p vá»›i loáº¡i váº¯c xin trong booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not batch_number:
            data["batch_number"] = vaccine_obj.batch_number
    else:
        if batch_number:
            vaccine_obj = (
                Vaccine.objects.filter(
                    batch_number=batch_number,
                    quantity__gt=0,
                    expiration_date__gte=today,
                )
                .order_by("expiration_date", "id")
                .first()
            )
            if not vaccine_obj:
                return Response(
                    {
                        "detail": (
                            "KhÃ´ng tÃ¬m tháº¥y lÃ´ váº¯c xin phÃ¹ há»£p vá»›i sá»‘ lÃ´ Ä‘Ã£ nháº­p, "
                            "hoáº·c lÃ´ nÃ y Ä‘Ã£ háº¿t hÃ ng / háº¿t háº¡n."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if vaccine_obj is None:
            vaccine_obj = (
                Vaccine.objects.filter(
                    name__iexact=booking.vaccine_name,
                    quantity__gt=0,
                    expiration_date__gte=today,
                )
                .order_by("expiration_date", "id")
                .first()
            )

        if not vaccine_obj:
            return Response(
                {
                    "detail": (
                        "KhÃ´ng tÃ¬m tháº¥y váº¯c xin phÃ¹ há»£p trong kho Ä‘á»ƒ xÃ¡c nháº­n tiÃªm. "
                        "HÃ£y kiá»ƒm tra láº¡i sá»‘ lÃ´ hoáº·c tá»“n kho hiá»‡n cÃ³."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data["vaccine"] = vaccine_obj.id
        if not batch_number:
            data["batch_number"] = vaccine_obj.batch_number

    was_existing_log = False
    try:
        vaccination = VaccinationLog.objects.get(booking=booking)
        serializer = VaccinationLogSerializer(vaccination, data=data)
        was_existing_log = True
    except VaccinationLog.DoesNotExist:
        serializer = VaccinationLogSerializer(data=data)

    if serializer.is_valid():
        try:
            with transaction.atomic():
                serializer.save()

                # Trá»« tá»“n kho â€” pháº£i trong cÃ¹ng transaction vá»›i booking status
                vaccine_obj = serializer.instance.vaccine if serializer.instance.vaccine else None
                if vaccine_obj and not was_existing_log:
                    updated = Vaccine.objects.filter(
                        pk=vaccine_obj.pk,
                        quantity__gt=0,
                        expiration_date__gte=today,
                    ).update(quantity=F("quantity") - 1)
                    if updated != 1:
                        raise serializers.ValidationError(
                            {"detail": "Váº¯c xin Ä‘Ã£ háº¿t hÃ ng hoáº·c háº¿t háº¡n, khÃ´ng thá»ƒ ghi nháº­n tiÃªm."}
                        )

                # Chuyá»ƒn sang tráº¡ng thÃ¡i theo dÃµi sau tiÃªm
                booking.status = Booking.STATUS_IN_OBSERVATION
                booking.save(update_fields=["status", "updated_at"])
        except serializers.ValidationError as error:
            return Response(error.detail, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "KhÃ´ng thá»ƒ lÆ°u xÃ¡c nháº­n tiÃªm vÃ¬ dá»¯ liá»‡u há»“ sÆ¡ tiÃªm cÅ© chÆ°a tÆ°Æ¡ng thÃ­ch hoÃ n toÃ n. "
                        "HÃ£y cháº¡y migration má»›i rá»“i thá»­ láº¡i."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK if was_existing_log else status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_protect_session_api
@api_view(["POST"])
def submit_post_injection_tracking(request):
    """BÆ°á»›c 6 â€” Staff ghi nháº­n theo dÃµi sau tiÃªm. Booking pháº£i á»Ÿ in_observation."""
    _, error_response = _require_staff_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        vaccination_log = VaccinationLog.objects.get(booking__id=booking_id)
    except VaccinationLog.DoesNotExist:
        return Response({"detail": "KhÃ´ng tÃ¬m tháº¥y há»“ sÆ¡ tiÃªm cho booking nÃ y."}, status=status.HTTP_404_NOT_FOUND)

    booking = vaccination_log.booking
    if booking.status != Booking.STATUS_IN_OBSERVATION:
        return Response(
            {"detail": "Bá»‡nh nhÃ¢n chÆ°a á»Ÿ tráº¡ng thÃ¡i theo dÃµi sau tiÃªm."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data.copy()
    data["vaccination_log"] = vaccination_log.id

    serializer = PostInjectionTrackingSerializer(data=data)
    if serializer.is_valid():
        serializer.save()

        # HoÃ n táº¥t â€” chuyá»ƒn sang Completed
        booking.status = Booking.STATUS_COMPLETED
        booking.save(update_fields=["status", "updated_at"])

        return Response(
            {**serializer.data, "booking_id": booking.id, "booking_status": booking.status},
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_protect_session_api
@api_view(["POST"])
def walkin_checkin(request):
    """Walk-in: Staff tao booking moi va check-in ngay tai quay."""
    user, err = _require_staff_user(request)
    if err:
        return err

    pre_data = request.data.get("pre_screening")
    if not isinstance(pre_data, dict):
        return Response(
            {"detail": "Walk-in can nhap day du khai bao y te truoc khi check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        booking_data = {
            "full_name": request.data.get("full_name"),
            "phone": request.data.get("phone"),
            "email": request.data.get("email", ""),
            "vaccine_name": request.data.get("vaccine_name", "General Vaccine"),
            "vaccine_date": request.data.get("vaccine_date"),
            "dose_number": request.data.get("dose_number", 1),
            "note": request.data.get("note", ""),
            "status": Booking.STATUS_CHECKED_IN,
        }

        booking_owner = _find_active_citizen_by_email(request.data.get("email"))

        booking_serializer = BookingSerializer(
            data=booking_data,
            context={
                "session_user": user,
                "resolved_vaccine": _resolve_vaccine_by_name(booking_data["vaccine_name"]),
                "recalculate_pricing": True,
                "force_status": Booking.STATUS_CHECKED_IN,
            },
        )
        if not booking_serializer.is_valid():
            return Response(booking_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pre_serializer = PreScreeningDeclarationSerializer(data=pre_data)
        if not pre_serializer.is_valid():
            return Response(pre_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        booking = booking_serializer.save(
            user=booking_owner,
            booking_source=Booking.BOOKING_SOURCE_WALKIN,
        )
        pre_serializer.save(booking=booking)

    return Response(
        BookingSerializer(booking, context={"session_user": user}).data,
        status=status.HTTP_201_CREATED,
    )


@csrf_protect_session_api
@api_view(["POST"])
def reschedule_booking(request, booking_id):
    """Äáº·t láº¡i lá»‹ch cho booking bá»‹ hoÃ£n (Delayed). Staff hoáº·c chÃ­nh citizen Ä‘Ã³."""
    user = _get_api_session_user(request)
    if not user:
        return Response({"detail": "Báº¡n chÆ°a Ä‘Äƒng nháº­p."}, status=status.HTTP_401_UNAUTHORIZED)

    if user.role not in [User.ROLE_CITIZEN, User.ROLE_STAFF]:
        return Response(
            {"detail": "Chá»‰ cÃ´ng dÃ¢n hoáº·c nhÃ¢n viÃªn má»›i Ä‘Æ°á»£c Ä‘áº·t láº¡i lá»‹ch."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        source = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "KhÃ´ng tÃ¬m tháº¥y booking."}, status=status.HTTP_404_NOT_FOUND)

    # Citizen chá»‰ reschedule booking cá»§a mÃ¬nh
    if user.role == User.ROLE_CITIZEN:
        if not _can_access_booking(user, source):
            return Response({"detail": "Báº¡n khÃ´ng cÃ³ quyá»n Ä‘áº·t láº¡i lá»‹ch nÃ y."}, status=status.HTTP_403_FORBIDDEN)

    # Chá»‰ cho phÃ©p reschedule khi Ä‘ang Delayed
    if source.status != Booking.STATUS_DELAYED:
        return Response(
            {"detail": "Chá»‰ cÃ³ thá»ƒ Ä‘áº·t láº¡i lá»‹ch cho cÃ¡c ca bá»‹ hoÃ£n (Delayed)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if source.rescheduled_bookings.exists():
        return Response(
            {"detail": "Booking nÃ y Ä‘Ã£ cÃ³ lá»‹ch thay tháº¿, khÃ´ng thá»ƒ Ä‘áº·t láº¡i thÃªm láº§n ná»¯a."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_date_str = request.data.get("vaccine_date")
    if not new_date_str:
        return Response({"detail": "Vui lÃ²ng cung cáº¥p ngÃ y tiÃªm má»›i."}, status=status.HTTP_400_BAD_REQUEST)

    booking_owner = source.user
    if booking_owner is None and user.role == User.ROLE_CITIZEN and _can_access_booking(user, source):
        booking_owner = user
    if booking_owner is None:
        booking_owner = _find_active_citizen_by_email(source.email)

    validation_user = booking_owner if booking_owner and booking_owner.role == User.ROLE_CITIZEN else user
    payload = {
        "full_name": source.full_name,
        "phone": source.phone,
        "email": source.email,
        "vaccine_name": source.vaccine_name,
        "vaccine_date": new_date_str,
        "dose_number": source.dose_number,
        "note": source.note,
        "status": Booking.STATUS_AWAITING_ELIGIBILITY,
    }

    serializer = BookingSerializer(
        data=payload,
        context={
            "session_user": validation_user,
            "resolved_vaccine": source.vaccine or _resolve_vaccine_by_name(source.vaccine_name),
            "recalculate_pricing": True,
            "force_status": Booking.STATUS_AWAITING_ELIGIBILITY,
        },
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        new_booking = serializer.save(
            user=booking_owner,
            booking_source=source.booking_source,
            rescheduled_from=source,
        )

        # Clone PreScreeningDeclaration náº¿u cÃ³
        old_pre = PreScreeningDeclaration.objects.filter(booking=source).first()
        if old_pre:
            PreScreeningDeclaration.objects.create(
                booking=new_booking,
                has_fever=old_pre.has_fever,
                has_allergy_history=old_pre.has_allergy_history,
                has_chronic_condition=old_pre.has_chronic_condition,
                recent_symptoms=old_pre.recent_symptoms,
                current_medications=old_pre.current_medications,
                has_severe_allergy=old_pre.has_severe_allergy,
                severe_allergy_details=old_pre.severe_allergy_details,
                has_current_health_issue=old_pre.has_current_health_issue,
                current_health_issue_details=old_pre.current_health_issue_details,
                had_recent_vaccination=old_pre.had_recent_vaccination,
                recent_vaccination_details=old_pre.recent_vaccination_details,
                uses_immunosuppressive_medication=old_pre.uses_immunosuppressive_medication,
                immunosuppressive_medication_details=old_pre.immunosuppressive_medication_details,
                has_pregnancy_or_breastfeeding_consideration=old_pre.has_pregnancy_or_breastfeeding_consideration,
                pregnancy_or_breastfeeding_details=old_pre.pregnancy_or_breastfeeding_details,
                note=old_pre.note,
            )

    return Response(
        BookingSerializer(new_booking, context={"session_user": user}).data,
        status=status.HTTP_201_CREATED,
    )


