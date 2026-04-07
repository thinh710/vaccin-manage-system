import calendar
from datetime import date

from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework import serializers, status
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

    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_DOCTOR]:
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
    """Dùng cho bước check-in, inject, monitor — Staff/Admin vận hành."""
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return None, Response({"detail": "Chức năng này chỉ dành cho nhân viên."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _require_medical_read_user(request):
    """Dùng cho các màn hình/list API mà staff, doctor, admin đều cần xem."""
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_DOCTOR]:
        return None, Response({"detail": "Bạn không có quyền dùng chức năng y khoa."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _require_doctor_user(request):
    """Dùng cho bước khám sàng lọc — chỉ Doctor/Admin."""
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_DOCTOR]:
        return None, Response(
            {"detail": "Chỉ bác sĩ mới được thực hiện khám sàng lọc."},
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
    if user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return True
    if booking.user_id and booking.user_id == user.id:
        return True
    return bool(user.email and booking.email and booking.email.lower() == user.email.lower())


@api_view(["GET"])
def today_bookings(request):
    _, error_response = _require_medical_read_user(request)
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

    # POST / PATCH — citizen hoặc staff đều được (staff điền hộ khi walk-in)
    if user.role not in [User.ROLE_CITIZEN, User.ROLE_STAFF, User.ROLE_ADMIN]:
        return Response(
            {"detail": "Bạn không có quyền gửi khai báo sàng lọc."},
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
    _, error_response = _require_staff_user(request)
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
            {"detail": "Cần xác nhận lịch trước khi check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking.status = Booking.STATUS_CHECKED_IN
    booking.save(update_fields=["status", "updated_at"])

    has_declaration = PreScreeningDeclaration.objects.filter(booking=booking).exists()
    return Response({
        "status": "checked_in",
        "booking_id": booking.id,
        "has_pre_screening": has_declaration,
        "warning": None if has_declaration else "Chưa có khai báo y tế. Y tá cần điền hộ.",
    })


@api_view(["POST"])
def submit_screening_result(request):
    """Bước 4 — chỉ Doctor/Admin thực hiện khám sàng lọc."""
    _, error_response = _require_doctor_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_CHECKED_IN:
        return Response(
            {"detail": "Chỉ được khám sàng lọc khi booking đã check-in."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not PreScreeningDeclaration.objects.filter(booking=booking).exists():
        return Response(
            {"detail": "Booking chua co khai bao y te. Y ta can dien bo sung ngay sau check-in truoc khi bac si sang loc."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    decision = request.data.get("decision")
    if decision not in ("eligible", "delayed", "cancelled"):
        return Response(
            {"detail": "Trường 'decision' phải là: eligible, delayed, hoặc cancelled."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        screening = ScreeningResult.objects.get(booking=booking)
        serializer = ScreeningResultSerializer(screening, data=request.data)
    except ScreeningResult.DoesNotExist:
        serializer = ScreeningResultSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()

        # 3 nhánh quyết định dựa vào field 'decision'
        if decision == "eligible":
            booking.status = Booking.STATUS_READY_TO_INJECT
        elif decision == "delayed":
            booking.status = Booking.STATUS_DELAYED
        elif decision == "cancelled":
            booking.status = Booking.STATUS_CANCELLED

        booking.save(update_fields=["status", "updated_at"])

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def submit_vaccination_log(request):
    """Bước 5 — Staff/Admin xác nhận tiêm. Booking phải ở ready_to_inject."""
    _, error_response = _require_staff_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_READY_TO_INJECT:
        return Response(
            {"detail": "Booking chưa được bác sĩ chỉ định tiêm."},
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

                # Trừ tồn kho — phải trong cùng transaction với booking status
                vaccine_obj = serializer.instance.vaccine if serializer.instance.vaccine else None
                if vaccine_obj and vaccine_obj.quantity > 0:
                    vaccine_obj.quantity -= 1
                    vaccine_obj.save(update_fields=["quantity"])

                # Chuyển sang trạng thái theo dõi sau tiêm
                booking.status = Booking.STATUS_IN_OBSERVATION
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
    """Bước 6 — Staff/Admin ghi nhận theo dõi sau tiêm. Booking phải ở in_observation."""
    _, error_response = _require_staff_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        vaccination_log = VaccinationLog.objects.get(booking__id=booking_id)
    except VaccinationLog.DoesNotExist:
        return Response({"detail": "Không tìm thấy hồ sơ tiêm cho booking này."}, status=status.HTTP_404_NOT_FOUND)

    booking = vaccination_log.booking
    if booking.status != Booking.STATUS_IN_OBSERVATION:
        return Response(
            {"detail": "Bệnh nhân chưa ở trạng thái theo dõi sau tiêm."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data.copy()
    data["vaccination_log"] = vaccination_log.id

    serializer = PostInjectionTrackingSerializer(data=data)
    if serializer.is_valid():
        serializer.save()

        # Hoàn tất — chuyển sang Completed
        booking.status = Booking.STATUS_COMPLETED
        booking.save(update_fields=["status", "updated_at"])

        return Response(
            {**serializer.data, "booking_id": booking.id, "booking_status": booking.status},
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def walkin_checkin(request):
    """Walk-in: Staff tạo booking mới và check-in ngay tại quầy."""
    user, err = _require_staff_user(request)
    if err:
        return err

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
            context={"session_user": user},
        )
        if not booking_serializer.is_valid():
            return Response(booking_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        booking = booking_serializer.save(
            user=booking_owner,
            booking_source=Booking.BOOKING_SOURCE_WALKIN,
        )

        # Tạo PreScreeningDeclaration nếu có
        pre_data = request.data.get("pre_screening")
        if pre_data:
            pre_serializer = PreScreeningDeclarationSerializer(data=pre_data)
            if not pre_serializer.is_valid():
                return Response(pre_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            pre_serializer.save(booking=booking)

    return Response(
        BookingSerializer(booking, context={"session_user": user}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def reschedule_booking(request, booking_id):
    """Đặt lại lịch cho booking bị hoãn (Delayed). Staff hoặc chính citizen đó."""
    user = _get_api_session_user(request)
    if not user:
        return Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        source = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    # Citizen chỉ reschedule booking của mình
    if user.role == User.ROLE_CITIZEN:
        if not _can_access_booking(user, source):
            return Response({"detail": "Bạn không có quyền đặt lại lịch này."}, status=status.HTTP_403_FORBIDDEN)

    # Chỉ cho phép reschedule khi đang Delayed
    if source.status != Booking.STATUS_DELAYED:
        return Response(
            {"detail": "Chỉ có thể đặt lại lịch cho các ca bị hoãn (Delayed)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_date_str = request.data.get("vaccine_date")
    if not new_date_str:
        return Response({"detail": "Vui lòng cung cấp ngày tiêm mới."}, status=status.HTTP_400_BAD_REQUEST)

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
        "status": Booking.STATUS_PENDING,
    }

    serializer = BookingSerializer(data=payload, context={"session_user": validation_user})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        new_booking = serializer.save(
            user=booking_owner,
            booking_source=source.booking_source,
            rescheduled_from=source,
        )

        # Clone PreScreeningDeclaration nếu có
        old_pre = PreScreeningDeclaration.objects.filter(booking=source).first()
        if old_pre:
            PreScreeningDeclaration.objects.create(
                booking=new_booking,
                has_fever=old_pre.has_fever,
                has_allergy_history=old_pre.has_allergy_history,
                has_chronic_condition=old_pre.has_chronic_condition,
                recent_symptoms=old_pre.recent_symptoms,
                current_medications=old_pre.current_medications,
                note=old_pre.note,
            )

    return Response(
        BookingSerializer(new_booking, context={"session_user": user}).data,
        status=status.HTTP_201_CREATED,
    )
