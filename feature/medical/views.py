import calendar
from datetime import date

from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from feature.assets.models import Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.booking.serializers import BookingSerializer

from .models import PostInjectionTracking, PreScreeningDeclaration, ScreeningResult, VaccinationLog
from .serializers import (
    PostInjectionTrackingSerializer,
    PreScreeningDeclarationSerializer,
    ScreeningResultSerializer,
    VaccinationLogSerializer,
)


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
        .exclude(status=Booking.STATUS_CANCELLED)
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
        .exclude(status=Booking.STATUS_CANCELLED)
        .order_by("vaccine_date", "id")[:4]
    )
    health_schedule = list(
        Booking.objects.filter(vaccine_date__gte=today)
        .filter(
            status__in=[
                Booking.STATUS_PENDING,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CHECKED_IN,
                Booking.STATUS_DELAYED,
            ]
        )
        .order_by("vaccine_date", "id")[:4]
    )

    return {
        "calendar_month_label": f"Tháng {today.month}",
        "calendar_weekdays": ["T2", "T3", "T4", "T5", "T6", "T7", "CN"],
        "calendar_weeks": month_weeks,
        "vaccination_schedule": vaccination_schedule,
        "health_schedule": health_schedule,
    }


def medical_dashboard(request):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    today = date.today()
    context = {
        "user": user,
        "today": today,
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


def _require_medical_api_user(request):
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return None, Response({"detail": "Bạn không có quyền dùng chức năng y khoa."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _can_access_booking(user, booking):
    if user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return True
    if booking.user_id and booking.user_id == user.id:
        return True
    return bool(user.email and booking.email and booking.email.lower() == user.email.lower())


@api_view(["GET"])
def today_bookings(request):
    _, error_response = _require_medical_api_user(request)
    if error_response:
        return error_response

    today = timezone.localdate()
    bookings = (
        Booking.objects.filter(vaccine_date=today)
        .exclude(status=Booking.STATUS_CANCELLED)
        .select_related("pre_screening")
        .order_by("vaccine_date", "id")
    )
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(["GET", "POST", "PATCH"])
def pre_screening_declaration_detail(request, booking_id):
    user = _get_api_session_user(request)
    if not user:
        return Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if not _can_access_booking(user, booking):
        return Response({"detail": "Bạn không có quyền truy cập booking này."}, status=status.HTTP_403_FORBIDDEN)

    declaration = PreScreeningDeclaration.objects.filter(booking=booking).first()

    if request.method == "GET":
        if not declaration:
            return Response({"booking": booking.id, "declaration": None})
        return Response(PreScreeningDeclarationSerializer(declaration).data)

    if user.role != User.ROLE_CITIZEN:
        return Response(
            {"detail": "Chỉ công dân mới có thể gửi khai báo sàng lọc."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if booking.status in [Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED]:
        return Response(
            {"detail": "Booking này không còn mở để khai báo sàng lọc."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if declaration:
        serializer = PreScreeningDeclarationSerializer(declaration, data=request.data, partial=True)
    else:
        serializer = PreScreeningDeclarationSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(booking=booking)
        return Response(serializer.data, status=status.HTTP_200_OK if declaration else status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
def check_in_booking(request, booking_id):
    _, error_response = _require_medical_api_user(request)
    if error_response:
        return error_response

    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status in [Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED]:
        return Response({"detail": "Không thể check-in booking này."}, status=status.HTTP_400_BAD_REQUEST)

    if booking.status != Booking.STATUS_CONFIRMED:
        return Response(
            {"detail": "Bác sĩ phải xác nhận lịch trước khi y tá check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking.status = Booking.STATUS_CHECKED_IN
    booking.save(update_fields=["status", "updated_at"])

    return Response({"status": "checked_in", "booking_id": booking.id})


@api_view(["POST"])
def submit_screening_result(request):
    _, error_response = _require_medical_api_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_CHECKED_IN:
        return Response(
            {"detail": "Y tá chỉ được nhập kết quả sau khi booking đã check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        screening = ScreeningResult.objects.get(booking=booking)
        serializer = ScreeningResultSerializer(screening, data=request.data)
    except ScreeningResult.DoesNotExist:
        serializer = ScreeningResultSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()

        is_eligible = serializer.validated_data.get("is_eligible")
        booking.status = Booking.STATUS_SCREENED if is_eligible else Booking.STATUS_DELAYED
        booking.save(update_fields=["status", "updated_at"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def submit_vaccination_log(request):
    _, error_response = _require_medical_api_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_SCREENED:
        return Response(
            {"detail": "Chỉ được xác nhận tiêm khi booking đã hoàn tất sàng lọc."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data.copy()
    vaccine_obj = None
    batch_number = (data.get("batch_number") or "").strip()

    if not data.get("vaccine"):
        if batch_number:
            vaccine_obj = (
                Vaccine.objects.filter(
                    batch_number=batch_number,
                    quantity__gt=0,
                    expiration_date__gte=timezone.localdate(),
                )
                .order_by("expiration_date", "id")
                .first()
            )
            if not vaccine_obj:
                return Response(
                    {
                        "detail": (
                            "Không tìm thấy lô vắc xin phù hợp với số lô đã nhập, "
                            "hoặc lô này đã hết hàng / hết hạn."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if vaccine_obj is None:
            vaccine_obj = (
                Vaccine.objects.filter(
                    name__iexact=booking.vaccine_name,
                    quantity__gt=0,
                    expiration_date__gte=timezone.localdate(),
                )
                .order_by("expiration_date", "id")
                .first()
            )

        if not vaccine_obj:
            return Response(
                {
                    "detail": (
                        "Không tìm thấy vắc xin phù hợp trong kho để xác nhận tiêm. "
                        "Hãy kiểm tra lại số lô hoặc tồn kho hiện có."
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

                vaccine_obj = serializer.instance.vaccine if serializer.instance.vaccine else None
                if vaccine_obj and vaccine_obj.quantity > 0:
                    vaccine_obj.quantity -= 1
                    vaccine_obj.save(update_fields=["quantity"])

                booking.status = Booking.STATUS_COMPLETED
                booking.save(update_fields=["status", "updated_at"])
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "Không thể lưu xác nhận tiêm vì dữ liệu hồ sơ tiêm cũ chưa tương thích hoàn toàn. "
                        "Hãy chạy migration mới rồi thử lại."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK if was_existing_log else status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def submit_post_injection_tracking(request):
    _, error_response = _require_medical_api_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        vaccination_log = VaccinationLog.objects.get(booking__id=booking_id)
    except VaccinationLog.DoesNotExist:
        return Response({"detail": "Không tìm thấy hồ sơ tiêm cho booking này."}, status=status.HTTP_404_NOT_FOUND)

    data = request.data.copy()
    data["vaccination_log"] = vaccination_log.id

    serializer = PostInjectionTrackingSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
