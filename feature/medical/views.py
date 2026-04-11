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


def _flatten_serializer_errors(serializer):
    return " ".join(str(message) for messages in serializer.errors.values() for message in messages)


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
        "note": declaration.note or "",
        "created_at": declaration.created_at.isoformat(),
        "updated_at": declaration.updated_at.isoformat(),
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
    page_error = ""
    page_success = ""

    if request.method == "POST":
        action = request.POST.get("action")
        booking_id = request.POST.get("booking_id")

        if action == "confirm_booking" and user.role in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_DOCTOR]:
            booking = Booking.objects.filter(pk=booking_id).first()
            if booking and booking.status in [Booking.STATUS_PENDING, Booking.STATUS_DELAYED]:
                booking.status = Booking.STATUS_CONFIRMED
                booking.save(update_fields=["status", "updated_at"])
                page_success = "Đã xác nhận lịch hẹn."
            else:
                page_error = "Không thể xác nhận booking này."

        elif action == "check_in" and user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
            booking = Booking.objects.filter(pk=booking_id).first()
            if booking and booking.status == Booking.STATUS_CONFIRMED:
                booking.status = Booking.STATUS_CHECKED_IN
                booking.save(update_fields=["status", "updated_at"])
                page_success = "Đã check-in bệnh nhân."
            else:
                page_error = "Không thể check-in booking này."

        elif action == "save_prescreen" and user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
            booking = Booking.objects.filter(pk=booking_id).first()
            if booking:
                declaration = PreScreeningDeclaration.objects.filter(booking=booking).first()
                payload = {
                    "has_fever": bool(request.POST.get("has_fever")),
                    "has_allergy_history": bool(request.POST.get("has_allergy_history")),
                    "has_chronic_condition": bool(request.POST.get("has_chronic_condition")),
                    "recent_symptoms": request.POST.get("recent_symptoms", "").strip(),
                    "current_medications": request.POST.get("current_medications", "").strip(),
                    "note": request.POST.get("note", "").strip(),
                }
                serializer = (
                    PreScreeningDeclarationSerializer(declaration, data=payload, partial=True)
                    if declaration
                    else PreScreeningDeclarationSerializer(data=payload)
                )
                if serializer.is_valid():
                    serializer.save(booking=booking)
                    page_success = "Đã lưu khai báo y tế bổ sung."
                else:
                    page_error = _flatten_serializer_errors(serializer) or "Không thể lưu khai báo y tế."
            else:
                page_error = "Không tìm thấy booking."

        elif action == "screening" and user.role in [User.ROLE_ADMIN, User.ROLE_DOCTOR]:
            booking = Booking.objects.filter(pk=booking_id).first()
            if booking and booking.status == Booking.STATUS_CHECKED_IN:
                payload = {
                    "booking": booking.id,
                    "temperature": request.POST.get("temperature"),
                    "blood_pressure": request.POST.get("blood_pressure"),
                    "decision": request.POST.get("decision"),
                    "doctor_note": request.POST.get("doctor_note", "").strip(),
                }
                existing = ScreeningResult.objects.filter(booking=booking).first()
                serializer = (
                    ScreeningResultSerializer(existing, data=payload)
                    if existing
                    else ScreeningResultSerializer(data=payload)
                )
                if serializer.is_valid():
                    serializer.save()
                    if payload["decision"] == "eligible":
                        booking.status = Booking.STATUS_READY_TO_INJECT
                    elif payload["decision"] == "delayed":
                        booking.status = Booking.STATUS_DELAYED
                    else:
                        booking.status = Booking.STATUS_CANCELLED
                    booking.save(update_fields=["status", "updated_at"])
                    page_success = "Đã lưu kết quả sàng lọc."
                else:
                    page_error = _flatten_serializer_errors(serializer) or "Không thể lưu kết quả sàng lọc."
            else:
                page_error = "Booking chưa ở trạng thái có thể sàng lọc."

        elif action == "inject" and user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
            booking = Booking.objects.filter(pk=booking_id).first()
            if booking and booking.status == Booking.STATUS_READY_TO_INJECT:
                payload = {
                    "booking": booking.id,
                    "batch_number": request.POST.get("batch_number", "").strip(),
                    "injected_by": request.POST.get("injected_by", "").strip(),
                    "dose_number": request.POST.get("dose_number"),
                }
                serializer = VaccinationLogSerializer(data=payload)
                if serializer.is_valid():
                    try:
                        with transaction.atomic():
                            serializer.save()
                            vaccine_obj = serializer.instance.vaccine
                            if vaccine_obj and vaccine_obj.quantity > 0:
                                vaccine_obj.quantity -= 1
                                vaccine_obj.save(update_fields=["quantity"])
                            booking.status = Booking.STATUS_IN_OBSERVATION
                            booking.save(update_fields=["status", "updated_at"])
                        page_success = "Đã lưu thông tin tiêm."
                    except IntegrityError:
                        page_error = "Không thể lưu hồ sơ tiêm."
                else:
                    page_error = _flatten_serializer_errors(serializer) or "Không thể lưu hồ sơ tiêm."
            else:
                page_error = "Booking chưa sẵn sàng để tiêm."

        elif action == "monitor" and user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
            booking = Booking.objects.filter(pk=booking_id).first()
            vaccination_log = VaccinationLog.objects.filter(booking=booking).first() if booking else None
            if booking and vaccination_log and booking.status == Booking.STATUS_IN_OBSERVATION:
                payload = {
                    "vaccination_log": vaccination_log.id,
                    "reaction_status": request.POST.get("reaction_status"),
                    "notes": request.POST.get("notes", "").strip(),
                }
                serializer = PostInjectionTrackingSerializer(data=payload)
                if serializer.is_valid():
                    serializer.save()
                    booking.status = Booking.STATUS_COMPLETED
                    booking.save(update_fields=["status", "updated_at"])
                    page_success = "Đã hoàn tất theo dõi sau tiêm."
                else:
                    page_error = _flatten_serializer_errors(serializer) or "Không thể lưu theo dõi."
            else:
                page_error = "Booking chưa ở giai đoạn theo dõi sau tiêm."

        elif action == "walkin" and user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
            booking_payload = {
                "full_name": request.POST.get("full_name"),
                "phone": request.POST.get("phone"),
                "email": request.POST.get("email"),
                "vaccine_name": request.POST.get("vaccine_name"),
                "vaccine_date": request.POST.get("vaccine_date"),
                "dose_number": request.POST.get("dose_number"),
                "status": Booking.STATUS_CHECKED_IN,
            }
            booking_serializer = BookingSerializer(data=booking_payload, context={"session_user": user})
            pre_payload = {
                "has_fever": bool(request.POST.get("walkin_has_fever")),
                "has_allergy_history": bool(request.POST.get("walkin_has_allergy_history")),
                "has_chronic_condition": bool(request.POST.get("walkin_has_chronic_condition")),
                "recent_symptoms": request.POST.get("walkin_recent_symptoms", "").strip(),
                "current_medications": request.POST.get("walkin_current_medications", "").strip(),
                "note": request.POST.get("walkin_note", "").strip(),
            }
            pre_serializer = PreScreeningDeclarationSerializer(data=pre_payload)
            if booking_serializer.is_valid() and pre_serializer.is_valid():
                with transaction.atomic():
                    booking = booking_serializer.save(
                        user=_find_active_citizen_by_email(request.POST.get("email")),
                        booking_source=Booking.BOOKING_SOURCE_WALKIN,
                    )
                    pre_serializer.save(booking=booking)
                page_success = "Đã tiếp nhận khách vãng lai."
            elif not booking_serializer.is_valid():
                page_error = _flatten_serializer_errors(booking_serializer) or "Không thể tạo walk-in."
            else:
                page_error = _flatten_serializer_errors(pre_serializer) or "Không thể lưu khai báo walk-in."

    vaccines = list(
        Vaccine.objects.filter(
            quantity__gt=0,
            expiration_date__gte=timezone.localdate(),
        ).order_by("name").values("id", "name", "quantity", "batch_number")
    )
    today_bookings_list = (
        Booking.objects.filter(vaccine_date=today)
        .exclude(status=Booking.STATUS_CANCELLED)
        .select_related("pre_screening", "screening_result", "vaccination_log")
        .order_by("id")
    )

    context = {
        "user": user,
        "today": today,
        "vaccines": vaccines,
        "page_error": page_error,
        "page_success": page_success,
        "today_bookings_list": today_bookings_list,
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
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return None, Response({"detail": "Chức năng này chỉ dành cho nhân viên."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _require_medical_read_user(request):
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_DOCTOR]:
        return None, Response({"detail": "Bạn không có quyền dùng chức năng y khoa."}, status=status.HTTP_403_FORBIDDEN)
    return user, None


def _require_doctor_user(request):
    user = _get_api_session_user(request)
    if not user:
        return None, Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role not in [User.ROLE_ADMIN, User.ROLE_DOCTOR]:
        return None, Response({"detail": "Chỉ bác sĩ mới được thực hiện khám sàng lọc."}, status=status.HTTP_403_FORBIDDEN)
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
        screening_result = ScreeningResult.objects.filter(booking=booking).first()
        return Response(
            {
                "booking": booking.id,
                "declaration": _serialize_declaration(declaration),
                "screening_result": _serialize_screening_result(screening_result),
            }
        )

    if user.role not in [User.ROLE_CITIZEN, User.ROLE_STAFF, User.ROLE_ADMIN]:
        return Response({"detail": "Bạn không có quyền gửi khai báo sàng lọc."}, status=status.HTTP_403_FORBIDDEN)

    if booking.status in [Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED]:
        return Response({"detail": "Booking này không còn mở để khai báo sàng lọc."}, status=status.HTTP_400_BAD_REQUEST)

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
        return Response({"detail": "Cần xác nhận lịch trước khi check-in."}, status=status.HTTP_400_BAD_REQUEST)

    booking.status = Booking.STATUS_CHECKED_IN
    booking.save(update_fields=["status", "updated_at"])

    has_declaration = PreScreeningDeclaration.objects.filter(booking=booking).exists()
    return Response(
        {
            "status": "checked_in",
            "booking_id": booking.id,
            "has_pre_screening": has_declaration,
            "warning": None if has_declaration else "Chưa có khai báo y tế. Y tá cần điền hộ.",
        }
    )


@api_view(["POST"])
def submit_screening_result(request):
    _, error_response = _require_doctor_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_CHECKED_IN:
        return Response({"detail": "Chỉ được khám sàng lọc khi booking đã check-in."}, status=status.HTTP_400_BAD_REQUEST)

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
    _, error_response = _require_staff_user(request)
    if error_response:
        return error_response

    booking_id = request.data.get("booking")
    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_READY_TO_INJECT:
        return Response({"detail": "Booking chưa được bác sĩ chỉ định tiêm."}, status=status.HTTP_400_BAD_REQUEST)

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
                    {"detail": "Không tìm thấy lô vắc xin phù hợp với số lô đã nhập, hoặc lô này đã hết hàng / hết hạn."},
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
                {"detail": "Không tìm thấy vắc xin phù hợp trong kho để xác nhận tiêm. Hãy kiểm tra lại số lô hoặc tồn kho hiện có."},
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

                booking.status = Booking.STATUS_IN_OBSERVATION
                booking.save(update_fields=["status", "updated_at"])
        except IntegrityError:
            return Response(
                {"detail": "Không thể lưu xác nhận tiêm vì dữ liệu hồ sơ tiêm cũ chưa tương thích hoàn toàn. Hãy chạy migration mới rồi thử lại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(serializer.data, status=status.HTTP_200_OK if was_existing_log else status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def submit_post_injection_tracking(request):
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
        return Response({"detail": "Bệnh nhân chưa ở trạng thái theo dõi sau tiêm."}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data.copy()
    data["vaccination_log"] = vaccination_log.id

    serializer = PostInjectionTrackingSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        booking.status = Booking.STATUS_COMPLETED
        booking.save(update_fields=["status", "updated_at"])

        return Response(
            {**serializer.data, "booking_id": booking.id, "booking_status": booking.status},
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def walkin_checkin(request):
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
        booking_serializer = BookingSerializer(data=booking_data, context={"session_user": user})
        if not booking_serializer.is_valid():
            return Response(booking_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        booking = booking_serializer.save(user=booking_owner, booking_source=Booking.BOOKING_SOURCE_WALKIN)

        pre_data = request.data.get("pre_screening")
        if pre_data:
            pre_serializer = PreScreeningDeclarationSerializer(data=pre_data)
            if not pre_serializer.is_valid():
                return Response(pre_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            pre_serializer.save(booking=booking)

    return Response(BookingSerializer(booking, context={"session_user": user}).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def reschedule_booking(request, booking_id):
    user = _get_api_session_user(request)
    if not user:
        return Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        source = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    if user.role == User.ROLE_CITIZEN and not _can_access_booking(user, source):
        return Response({"detail": "Bạn không có quyền đặt lại lịch này."}, status=status.HTTP_403_FORBIDDEN)

    if source.status != Booking.STATUS_DELAYED:
        return Response({"detail": "Chỉ có thể đặt lại lịch cho các ca bị hoãn (Delayed)."}, status=status.HTTP_400_BAD_REQUEST)

    if source.rescheduled_bookings.exists():
        return Response({"detail": "Booking này đã có lịch thay thế, không thể đặt lại thêm lần nữa."}, status=status.HTTP_400_BAD_REQUEST)

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

    return Response(BookingSerializer(new_booking, context={"session_user": user}).data, status=status.HTTP_201_CREATED)
