from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from feature.assets.models import Vaccine
from feature.authentication.models import User

from .models import Booking
from .serializers import BookingSerializer


def _get_session_user(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None


def _require_session_user(request):
    user = _get_session_user(request)
    if user:
        return user, None
    return None, redirect("/auth/login-page/")


def _scope_bookings_for_user(queryset, user):
    if not user:
        return queryset.none()
    if user.role in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return queryset
    return queryset.filter(Q(user=user) | Q(email__iexact=user.email))


def _build_portal_context(user):
    bookings = _scope_bookings_for_user(Booking.objects.all(), user)
    today = timezone.localdate()
    upcoming_bookings = bookings.filter(vaccine_date__gte=today).exclude(status=Booking.STATUS_CANCELLED)
    status_summary = bookings.values("status").annotate(total=Count("id"))
    status_map = {item["status"]: item["total"] for item in status_summary}

    vaccines = list(
        Vaccine.objects.filter(quantity__gt=0, expiration_date__gte=today)
        .order_by("name")
        .values("id", "name", "quantity", "batch_number", "expiration_date")
    )

    return {
        "user": user,
        "today": today,
        "vaccines": vaccines,
        "vaccine_options": [v["name"] for v in vaccines],
        "booking_stats": {
            "total": bookings.count(),
            "pending": status_map.get(Booking.STATUS_PENDING, 0),
            "confirmed": status_map.get(Booking.STATUS_CONFIRMED, 0),
            "completed": status_map.get(Booking.STATUS_COMPLETED, 0),
            "upcoming": upcoming_bookings.count(),
        },
        "initial_bookings": BookingSerializer(bookings[:12], many=True, context={"session_user": user}).data,
    }


def booking_portal(request):
    user, redirect_response = _require_session_user(request)
    if redirect_response:
        return redirect_response
    return render(request, "booking/portal.html", _build_portal_context(user))


@api_view(["GET", "POST"])
def booking_list_create(request):
    user = _get_session_user(request)
    if not user:
        return Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "GET":
        queryset = _scope_bookings_for_user(Booking.objects.select_related("user").all(), user)
        keyword = request.GET.get("q")
        booking_status = request.GET.get("status")
        vaccine_date = request.GET.get("date")

        if keyword:
            queryset = queryset.filter(
                Q(full_name__icontains=keyword)
                | Q(phone__icontains=keyword)
                | Q(vaccine_name__icontains=keyword)
            )
        if booking_status:
            queryset = queryset.filter(status=booking_status)
        if vaccine_date:
            queryset = queryset.filter(vaccine_date=vaccine_date)

        return Response(BookingSerializer(queryset, many=True, context={"session_user": user}).data)

    payload = request.data.copy()
    if user.role == User.ROLE_CITIZEN:
        payload["full_name"] = payload.get("full_name") or user.full_name
        payload["phone"] = payload.get("phone") or user.phone_number
        payload["email"] = payload.get("email") or user.email
        payload["status"] = Booking.STATUS_PENDING

    serializer = BookingSerializer(data=payload, context={"request": request, "session_user": user})
    if serializer.is_valid():
        booking = serializer.save(user=user)
        return Response(
            BookingSerializer(booking, context={"session_user": user}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
def booking_detail(request, booking_id):
    try:
        booking = Booking.objects.select_related("user").get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Không tìm thấy booking."}, status=status.HTTP_404_NOT_FOUND)

    user = _get_session_user(request)
    if not user:
        return Response({"detail": "Bạn chưa đăng nhập."}, status=status.HTTP_401_UNAUTHORIZED)

    if not _scope_bookings_for_user(Booking.objects.filter(pk=booking_id), user).exists():
        return Response({"detail": "Bạn không có quyền truy cập booking này."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        return Response(BookingSerializer(booking, context={"session_user": user}).data)

    if request.method == "PATCH":
        payload = request.data.copy()
        next_status = payload.get("status")

        if user.role == User.ROLE_CITIZEN:
            allowed_fields = {"vaccine_date", "note", "status", "phone"}
            unexpected_fields = set(payload.keys()) - allowed_fields
            if unexpected_fields:
                return Response(
                    {"detail": "Công dân chỉ được đổi ngày tiêm, số điện thoại, ghi chú hoặc hủy lịch."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if next_status and next_status != Booking.STATUS_CANCELLED:
                return Response(
                    {"detail": "Công dân chỉ có thể hủy lịch của mình."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            medical_only_status_messages = {
                Booking.STATUS_CHECKED_IN: "Check-in phải được thực hiện ở khu y khoa.",
                Booking.STATUS_SCREENED: "Kết quả sàng lọc phải được cập nhật ở khu y khoa.",
                Booking.STATUS_COMPLETED: "Xác nhận đã tiêm phải được cập nhật ở khu y khoa.",
                Booking.STATUS_DELAYED: "Trạng thái tạm hoãn phải đến từ kết quả sàng lọc.",
            }

            if next_status in medical_only_status_messages:
                return Response(
                    {"detail": medical_only_status_messages[next_status]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if next_status == Booking.STATUS_CONFIRMED:
                if user.role != User.ROLE_ADMIN:
                    return Response(
                        {"detail": "Chỉ bác sĩ/quản trị mới được xác nhận lịch tiêm."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if booking.status not in [Booking.STATUS_PENDING, Booking.STATUS_DELAYED]:
                    return Response(
                        {"detail": "Chỉ có thể xác nhận các lịch đang chờ xác nhận hoặc chờ xác nhận lại."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if next_status == Booking.STATUS_PENDING and user.role != User.ROLE_ADMIN:
                return Response(
                    {"detail": "Chỉ bác sĩ/quản trị mới được chuyển lịch về trạng thái chờ xác nhận."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = BookingSerializer(
            booking,
            data=payload,
            partial=True,
            context={"request": request, "session_user": user},
        )
        if serializer.is_valid():
            booking = serializer.save()
            return Response(BookingSerializer(booking, context={"session_user": user}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if user.role not in [User.ROLE_ADMIN, User.ROLE_STAFF]:
        return Response({"detail": "Bạn không có quyền xóa booking."}, status=status.HTTP_403_FORBIDDEN)
    booking.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def booking_test(request):
    return Response({"message": "Booking API is working"})
