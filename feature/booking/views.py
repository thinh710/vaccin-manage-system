from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from feature.assets.models import Vaccine
from feature.authentication.models import User
from feature.csrf import csrf_protect_session_api

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


def _find_active_citizen_by_email(email):
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    return User.objects.filter(
        email__iexact=normalized_email,
        role=User.ROLE_CITIZEN,
        status=User.STATUS_ACTIVE,
    ).first()


def _resolve_booking_owner(payload, acting_user):
    if acting_user.role == User.ROLE_CITIZEN:
        return acting_user, None

    requested_user_id = payload.get("user")
    if requested_user_id not in (None, ""):
        try:
            owner = User.objects.get(
                id=requested_user_id,
                role=User.ROLE_CITIZEN,
                status=User.STATUS_ACTIVE,
            )
        except (TypeError, ValueError, User.DoesNotExist):
            return None, Response(
                {"detail": "Chi duoc gan booking cho cong dan dang hoat dong."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return owner, None

    return _find_active_citizen_by_email(payload.get("email")), None


def _scope_bookings_for_user(queryset, user):
    if not user:
        return queryset.none()
    if user.role in [User.ROLE_STAFF, User.ROLE_DOCTOR]:
        return queryset
    if user.role == User.ROLE_ADMIN:
        return queryset.none()
    return queryset.filter(Q(user=user) | Q(email__iexact=user.email))


def _resolve_vaccine_by_name(vaccine_name):
    normalized_name = (vaccine_name or "").strip()
    if not normalized_name:
        return None

    today = timezone.localdate()
    queryset = Vaccine.objects.filter(name__iexact=normalized_name).order_by("expiration_date", "id")
    preferred = queryset.filter(quantity__gt=0, expiration_date__gte=today).first()
    return preferred or queryset.first()


def _resolve_vaccine_from_payload(payload, required=False):
    vaccine_name = payload.get("vaccine_name")
    vaccine = _resolve_vaccine_by_name(vaccine_name)
    if vaccine is None and required and vaccine_name:
        return None, Response(
            {"detail": "Khong tim thay vac xin duoc chon trong kho."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return vaccine, None


def _has_material_booking_change(booking, payload):
    if "vaccine_name" in payload:
        next_vaccine = str(payload.get("vaccine_name") or "").strip().lower()
        if next_vaccine and next_vaccine != (booking.vaccine_name or "").strip().lower():
            return True

    if "vaccine_date" in payload:
        next_date = str(payload.get("vaccine_date") or "")
        if next_date and next_date != booking.vaccine_date.isoformat():
            return True

    if "dose_number" in payload:
        try:
            next_dose = int(payload.get("dose_number"))
        except (TypeError, ValueError):
            return False
        if next_dose != booking.dose_number:
            return True

    return False


def _booking_queryset_for_api():
    return Booking.objects.select_related(
        "user",
        "vaccine",
        "pre_screening",
        "online_review",
        "online_review__reviewed_by",
    )


def _reset_online_review(booking):
    if hasattr(booking, "online_review"):
        booking.online_review.delete()


def _build_portal_context(user):
    bookings = _scope_bookings_for_user(_booking_queryset_for_api(), user)
    today = timezone.localdate()
    upcoming_bookings = bookings.filter(vaccine_date__gte=today).exclude(status=Booking.STATUS_CANCELLED)
    status_summary = bookings.values("status").annotate(total=Count("id"))
    status_map = {item["status"]: item["total"] for item in status_summary}

    vaccines = list(
        Vaccine.objects.filter(quantity__gt=0, expiration_date__gte=today)
        .order_by("name")
        .values("id", "name", "price", "quantity", "batch_number", "expiration_date")
    )

    return {
        "user": user,
        "today": today,
        "vaccines": vaccines,
        "vaccine_options": [v["name"] for v in vaccines],
        "booking_stats": {
            "total": bookings.count(),
            "awaiting_eligibility": status_map.get(Booking.STATUS_AWAITING_ELIGIBILITY, 0)
            + status_map.get(Booking.STATUS_PENDING, 0),
            "deposit_pending": status_map.get(Booking.STATUS_DEPOSIT_PENDING, 0),
            "confirmed": status_map.get(Booking.STATUS_CONFIRMED, 0),
            "completed": status_map.get(Booking.STATUS_COMPLETED, 0),
            "upcoming": upcoming_bookings.count(),
        },
        "initial_bookings": BookingSerializer(bookings[:12], many=True, context={"session_user": user}).data,
    }


@ensure_csrf_cookie
def booking_portal(request):
    user, redirect_response = _require_session_user(request)
    if redirect_response:
        return redirect_response
    if user.role == User.ROLE_ADMIN:
        return redirect("/assets/")
    return render(request, "booking/portal.html", _build_portal_context(user))


@csrf_protect_session_api
@api_view(["GET", "POST"])
def booking_list_create(request):
    user = _get_session_user(request)
    if not user:
        return Response({"detail": "Ban chua dang nhap."}, status=status.HTTP_401_UNAUTHORIZED)

    if user.role == User.ROLE_ADMIN:
        return Response(
            {"detail": "Tai khoan admin chi dung de quan ly kho."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        queryset = _scope_bookings_for_user(_booking_queryset_for_api(), user)
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
        payload["status"] = Booking.STATUS_AWAITING_ELIGIBILITY
    else:
        payload["status"] = Booking.STATUS_AWAITING_ELIGIBILITY

    booking_owner, error_response = _resolve_booking_owner(payload, user)
    if error_response:
        return error_response

    resolved_vaccine, error_response = _resolve_vaccine_from_payload(payload, required=True)
    if error_response:
        return error_response

    serializer = BookingSerializer(
        data=payload,
        context={
            "request": request,
            "session_user": user,
            "resolved_vaccine": resolved_vaccine,
            "recalculate_pricing": True,
            "force_status": payload["status"],
        },
    )
    if serializer.is_valid():
        booking = serializer.save(user=booking_owner)
        return Response(
            BookingSerializer(booking, context={"session_user": user}).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_protect_session_api
@api_view(["GET", "PATCH", "DELETE"])
def booking_detail(request, booking_id):
    try:
        booking = _booking_queryset_for_api().get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Khong tim thay booking."}, status=status.HTTP_404_NOT_FOUND)

    user = _get_session_user(request)
    if not user:
        return Response({"detail": "Ban chua dang nhap."}, status=status.HTTP_401_UNAUTHORIZED)

    if not _scope_bookings_for_user(Booking.objects.filter(pk=booking_id), user).exists():
        return Response({"detail": "Ban khong co quyen truy cap booking nay."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        return Response(BookingSerializer(booking, context={"session_user": user}).data)

    if request.method == "PATCH":
        if user.role not in [User.ROLE_CITIZEN, User.ROLE_STAFF]:
            return Response({"detail": "Ban khong co quyen cap nhat booking nay."}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data.copy()
        next_status = payload.get("status")
        serializer_context = {"request": request, "session_user": user, "recalculate_pricing": False}

        if user.role == User.ROLE_CITIZEN:
            allowed_fields = {"vaccine_name", "vaccine_date", "dose_number", "note", "status", "phone"}
            unexpected_fields = set(payload.keys()) - allowed_fields
            if unexpected_fields:
                return Response(
                    {"detail": "Cong dan chi duoc doi vac xin, mui tiem, ngay tiem, so dien thoai, ghi chu hoac huy lich."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if next_status and next_status != Booking.STATUS_CANCELLED:
                return Response(
                    {"detail": "Cong dan chi co the huy lich cua minh."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            medical_only_status_messages = {
                Booking.STATUS_CHECKED_IN: "Check-in phai duoc thuc hien o khu y khoa.",
                Booking.STATUS_READY_TO_INJECT: "Ket qua sang loc phai duoc cap nhat o khu y khoa.",
                Booking.STATUS_IN_OBSERVATION: "Trang thai theo doi sau tiem phai den tu khu y khoa.",
                Booking.STATUS_COMPLETED: "Xac nhan da tiem phai duoc cap nhat o khu y khoa.",
                Booking.STATUS_DELAYED: "Trang thai tam hoan phai den tu ket qua sang loc.",
                Booking.STATUS_INELIGIBLE: "Trang thai khong du dieu kien phai den tu duyet online cua bac si.",
                Booking.STATUS_CONFIRMED: "Hay dung thao tac xac nhan dat coc de chuyen booking sang confirmed.",
                Booking.STATUS_DEPOSIT_PENDING: "Hay dung thao tac xac nhan du dieu kien de chuyen booking sang cho dat coc.",
                Booking.STATUS_AWAITING_ELIGIBILITY: "Khong duoc chuyen lai trang thai cho duyet bang thao tac thu cong.",
                Booking.STATUS_PENDING: "Khong duoc chuyen lai trang thai legacy bang thao tac thu cong.",
            }
            if next_status in medical_only_status_messages:
                return Response(
                    {"detail": medical_only_status_messages[next_status]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        material_change = _has_material_booking_change(booking, payload)
        if material_change:
            if "vaccine_name" in payload:
                resolved_vaccine, error_response = _resolve_vaccine_from_payload(payload, required=True)
                if error_response:
                    return error_response
            else:
                resolved_vaccine = booking.vaccine or _resolve_vaccine_by_name(booking.vaccine_name)
            serializer_context["resolved_vaccine"] = resolved_vaccine
            serializer_context["recalculate_pricing"] = True

            if booking.booking_source == Booking.BOOKING_SOURCE_ONLINE and booking.status in [
                Booking.STATUS_DEPOSIT_PENDING,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_DELAYED,
                Booking.STATUS_INELIGIBLE,
            ]:
                serializer_context["force_status"] = Booking.STATUS_AWAITING_ELIGIBILITY
                serializer_context["reset_eligibility"] = True
                serializer_context["reset_deposit"] = True

        serializer = BookingSerializer(
            booking,
            data=payload,
            partial=True,
            context=serializer_context,
        )
        if serializer.is_valid():
            booking = serializer.save()
            if material_change and booking.booking_source == Booking.BOOKING_SOURCE_ONLINE:
                _reset_online_review(booking)
            return Response(BookingSerializer(booking, context={"session_user": user}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if user.role != User.ROLE_STAFF:
        return Response({"detail": "Ban khong co quyen xoa booking."}, status=status.HTTP_403_FORBIDDEN)
    booking.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@csrf_protect_session_api
@api_view(["PATCH"])
def confirm_booking_eligibility(request, booking_id):
    user = _get_session_user(request)
    if not user:
        return Response({"detail": "Ban chua dang nhap."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role != User.ROLE_DOCTOR:
        return Response({"detail": "Chi bac si moi duoc duyet online."}, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = _booking_queryset_for_api().get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Khong tim thay booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.booking_source != Booking.BOOKING_SOURCE_ONLINE:
        return Response({"detail": "Walk-in khong can buoc duyet online."}, status=status.HTTP_400_BAD_REQUEST)
    if booking.status not in [Booking.STATUS_AWAITING_ELIGIBILITY, Booking.STATUS_PENDING]:
        return Response({"detail": "Booking nay khong o trang thai cho duyet dieu kien."}, status=status.HTTP_400_BAD_REQUEST)
    if not hasattr(booking, "pre_screening"):
        return Response({"detail": "Can co khai bao truoc tiem truoc khi xac nhan du dieu kien."}, status=status.HTTP_400_BAD_REQUEST)

    decision = request.data.get("decision")
    if decision not in ["eligible", "delayed", "ineligible"]:
        return Response(
            {"detail": "Truong 'decision' phai la: eligible, delayed, hoac ineligible."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    force_status = {
        "eligible": Booking.STATUS_DEPOSIT_PENDING,
        "delayed": Booking.STATUS_DELAYED,
        "ineligible": Booking.STATUS_INELIGIBLE,
    }[decision]

    serializer = BookingSerializer(
        booking,
        data={},
        partial=True,
        context={
            "session_user": user,
            "force_status": force_status,
            "eligibility_confirmed_by": user if decision == "eligible" else None,
            "reset_eligibility": decision != "eligible",
            "reset_deposit": True,
            "recalculate_pricing": True,
        },
    )
    serializer.is_valid(raise_exception=True)
    booking = serializer.save()
    from feature.medical.models import OnlineEligibilityReview

    OnlineEligibilityReview.objects.update_or_create(
        booking=booking,
        defaults={
            "decision": decision,
            "doctor_note": request.data.get("doctor_note", ""),
            "reviewed_by": user,
        },
    )
    return Response(BookingSerializer(booking, context={"session_user": user}).data)


@csrf_protect_session_api
@api_view(["PATCH"])
def confirm_booking_deposit(request, booking_id):
    user = _get_session_user(request)
    if not user:
        return Response({"detail": "Ban chua dang nhap."}, status=status.HTTP_401_UNAUTHORIZED)
    if user.role != User.ROLE_STAFF:
        return Response({"detail": "Chi nhan vien moi duoc xac nhan dat coc."}, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = _booking_queryset_for_api().get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({"detail": "Khong tim thay booking."}, status=status.HTTP_404_NOT_FOUND)

    if booking.booking_source != Booking.BOOKING_SOURCE_ONLINE:
        return Response({"detail": "Walk-in khong su dung thao tac dat coc."}, status=status.HTTP_400_BAD_REQUEST)
    if booking.status != Booking.STATUS_DEPOSIT_PENDING:
        return Response({"detail": "Booking nay khong o trang thai cho dat coc."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = BookingSerializer(
        booking,
        data={},
        partial=True,
        context={
            "session_user": user,
            "force_status": Booking.STATUS_CONFIRMED,
            "deposit_paid_by": user,
            "deposit_note": request.data.get("deposit_note", ""),
            "recalculate_pricing": False,
        },
    )
    serializer.is_valid(raise_exception=True)
    booking = serializer.save()
    return Response(BookingSerializer(booking, context={"session_user": user}).data)


@api_view(["GET"])
def booking_test(request):
    return Response({"message": "Booking API is working"})
