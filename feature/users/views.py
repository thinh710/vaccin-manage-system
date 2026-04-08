import calendar
import json
from pathlib import Path

from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone

from feature.assets.models import Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.medical.models import PreScreeningDeclaration, ScreeningResult


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


def _get_session_user(request: HttpRequest):
    user_id = request.session.get("user_id")
    if not user_id:
        return None, redirect("/auth/login-page/")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None, redirect("/auth/login-page/")

    return user, None


def _get_dashboard_hero_images():
    image_dir = Path(__file__).resolve().parent / "static" / "users" / "img" / "dashboard-hero"
    supported_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = []

    if image_dir.exists():
        for image_path in sorted(image_dir.iterdir()):
            if image_path.is_file() and image_path.suffix.lower() in supported_extensions:
                images.append(static(f"users/img/dashboard-hero/{image_path.name}"))

    if not images:
        images.append(static("authentication/img/vaccine-db.jpg"))

    return images


def _build_citizen_page_context(user, page_key):
    pages = {
        "packages": {
            "eyebrow": "Gói vắc xin",
            "title": "Chọn gói vắc xin phù hợp cho từng giai đoạn",
            "description": (
                "Tổng hợp các gói tiêm phổ biến để người dùng tham khảo nhanh trước khi đặt lịch. "
                "Trang này giúp công dân xem nhanh nhóm vắc xin, đối tượng phù hợp và hướng đặt hẹn tiếp theo."
            ),
            "primary_action_label": "Đặt lịch ngay",
            "primary_action_href": "/booking/portal/",
            "secondary_action_label": "Xem lịch hẹn",
            "secondary_action_href": "/booking/portal/",
            "highlights": [
                {
                    "title": "Gói trẻ em",
                    "body": "Tập trung các mũi cơ bản, nhắc lại và theo dõi các mốc tiêm quan trọng cho bé.",
                },
                {
                    "title": "Gói thanh niên",
                    "body": "Phù hợp với HPV, viêm gan, cúm mùa và các mũi cần nhắc lại theo độ tuổi.",
                },
                {
                    "title": "Gói gia đình",
                    "body": "Tổng hợp nhu cầu tiêm cho nhiều thành viên để đặt lịch nhanh hơn trên cùng một hệ thống.",
                },
            ],
        },
        "system": {
            "eyebrow": "Hệ thống tiêm chủng",
            "title": "Theo dõi toàn bộ luồng tiêm chủng trên hệ thống",
            "description": (
                "Trang tổng quan giúp người dùng hiểu quy trình từ booking, check-in, sàng lọc, "
                "tiêm và theo dõi sau tiêm. Đây là điểm vào để công dân nắm rõ các bước cần có khi đi tiêm."
            ),
            "primary_action_label": "Mở cổng đặt lịch",
            "primary_action_href": "/booking/portal/",
            "secondary_action_label": "Cập nhật hồ sơ",
            "secondary_action_href": "/users/profile/",
            "highlights": [
                {
                    "title": "Bước 1: Đặt lịch",
                    "body": "Người dùng tạo booking, chọn vắc xin và ngày tiêm trong portal.",
                },
                {
                    "title": "Bước 2: Sàng lọc",
                    "body": "Nhân viên y tế tiếp nhận, đánh giá sức khỏe và cập nhật trạng thái.",
                },
                {
                    "title": "Bước 3: Theo dõi",
                    "body": "Sau khi tiêm, hệ thống tiếp tục lưu kết quả và hỗ trợ tra cứu lịch sử.",
                },
            ],
        },
        "knowledge": {
            "eyebrow": "Kiến thức tiêm chủng",
            "title": "Kiến thức cơ bản để đi tiêm an tâm hơn",
            "description": (
                "Tổng hợp những lưu ý trước tiêm, sau tiêm và các nguyên tắc theo dõi sức khỏe. "
                "Trang này đóng vai trò như một knowledge hub cơ bản để hoàn chỉnh điều hướng trong dashboard."
            ),
            "primary_action_label": "Đặt lịch tư vấn",
            "primary_action_href": "/booking/portal/",
            "secondary_action_label": "Về dashboard",
            "secondary_action_href": "/users/dashboard/",
            "highlights": [
                {
                    "title": "Trước khi tiêm",
                    "body": "Ngủ, ăn uống đầy đủ, mang theo thông tin y tế và khai báo tiền sử dị ứng nếu có.",
                },
                {
                    "title": "Sau khi tiêm",
                    "body": "Theo dõi phản ứng tại chỗ và toàn thân, liên hệ cơ sở y tế nếu có dấu hiệu bất thường.",
                },
                {
                    "title": "Nhớ lịch nhắc lại",
                    "body": "Theo dõi booking và mốc tiêm nhắc lại để đảm bảo hiệu quả bảo vệ.",
                },
            ],
        },
    }

    context = pages[page_key].copy()
    context["user"] = user
    context["page_key"] = page_key
    return context


def dashboard(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role == User.ROLE_ADMIN:
        today = timezone.localdate()
        bookings = Booking.objects.all()
        upcoming_bookings = (
            bookings.filter(vaccine_date__gte=today)
            .exclude(status=Booking.STATUS_CANCELLED)
            .order_by("vaccine_date", "id")
        )

        inventory_summary = []
        vaccine_stock_map = {v.name.lower(): v for v in Vaccine.objects.all()}
        inventory_rows = (
            bookings.values("vaccine_name")
            .annotate(
                total_bookings=Count("id"),
                upcoming_doses=Count("id", filter=Q(vaccine_date__gte=today)),
            )
            .order_by("-upcoming_doses", "vaccine_name")[:5]
        )

        for row in inventory_rows:
            vaccine_name = row["vaccine_name"]
            vaccine_obj = vaccine_stock_map.get(vaccine_name.lower())

            if vaccine_obj:
                real_stock = vaccine_obj.quantity
                is_low = real_stock <= vaccine_obj.minimum_stock
            else:
                real_stock = max(120 - row["upcoming_doses"] * 6, 0)
                is_low = real_stock < 40

            inventory_summary.append(
                {
                    "vaccine_name": vaccine_name,
                    "estimated_stock": real_stock,
                    "total_bookings": row["total_bookings"],
                    "upcoming_doses": row["upcoming_doses"],
                    "is_low_stock": is_low,
                }
            )

        context = {
            "user": user,
            "today": today,
            "total_bookings": bookings.count(),
            "todays_bookings_count": bookings.filter(vaccine_date=today)
            .exclude(status=Booking.STATUS_CANCELLED)
            .count(),
            "upcoming_bookings_count": upcoming_bookings.count(),
            "pending_count": bookings.filter(status=Booking.STATUS_PENDING).count(),
            "confirmed_count": bookings.filter(status=Booking.STATUS_CONFIRMED).count(),
            "cancelled_count": bookings.filter(status=Booking.STATUS_CANCELLED).count(),
            "recent_upcoming_bookings": list(upcoming_bookings[:5]),
            "inventory_summary": inventory_summary,
        }
        context.update(_build_schedule_context(today))
        return render(request, "users/admin_dashboard.html", context)

    if user.role == User.ROLE_STAFF:
        today = timezone.localdate()
        todays_bookings = list(
            Booking.objects.filter(vaccine_date=today)
            .exclude(status=Booking.STATUS_CANCELLED)
            .select_related("user")
            .order_by("vaccine_date", "id")
        )
        todays_booking_ids = [booking.id for booking in todays_bookings]
        screening_results = list(
            ScreeningResult.objects.select_related("booking")
            .filter(booking_id__in=todays_booking_ids)
            .order_by("-created_at")
        )
        screening_by_booking_id = {result.booking_id: result for result in screening_results}
        declarations_by_booking_id = {
            declaration.booking_id: declaration
            for declaration in PreScreeningDeclaration.objects.filter(booking_id__in=todays_booking_ids)
        }

        prioritized_screenings = []
        for booking in todays_bookings:
            if booking.status not in [
                Booking.STATUS_PENDING,
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_CHECKED_IN,
                Booking.STATUS_DELAYED,
            ]:
                continue

            screening_record = screening_by_booking_id.get(booking.id)
            if booking.status == Booking.STATUS_PENDING:
                action = "confirm"
                action_label = "Chờ bác sĩ xác nhận"
                status_label = "Chờ bác sĩ xác nhận lịch"
            elif booking.status == Booking.STATUS_CONFIRMED:
                action = "check_in"
                action_label = "Check-in"
                status_label = "Đã được bác sĩ xác nhận"
            elif booking.status == Booking.STATUS_CHECKED_IN:
                action = "waiting_doctor"
                action_label = "Nhập kết quả sàng lọc"
                status_label = "Cần sàng lọc"
            else:
                action = "waiting_reconfirm"
                action_label = "Chờ bác sĩ xác nhận lại"
                status_label = "Chờ bác sĩ xác nhận lại"

            prioritized_screenings.append(
                {
                    "booking": booking,
                    "record": screening_record,
                    "declaration": declarations_by_booking_id.get(booking.id),
                    "needs_screening": booking.status == Booking.STATUS_CHECKED_IN,
                    "fit_status": screening_record.is_eligible if screening_record else None,
                    "action": action,
                    "action_label": action_label,
                    "status_label": status_label,
                }
            )

        context = {
            "user": user,
            "today": today,
            "todays_bookings_count": len(todays_bookings),
            "screened_count": len(screening_results),
            "fit_count": sum(1 for result in screening_results if result.is_eligible),
            "not_fit_count": sum(1 for result in screening_results if not result.is_eligible),
            "waiting_screening_count": sum(
                1
                for booking in todays_bookings
                if booking.status in [Booking.STATUS_CONFIRMED, Booking.STATUS_CHECKED_IN]
            ),
            "ready_to_inject_count": Booking.objects.filter(
                vaccine_date=today,
                status=Booking.STATUS_READY_TO_INJECT,
            ).count(),
            "in_observation_count": Booking.objects.filter(
                vaccine_date=today,
                status=Booking.STATUS_IN_OBSERVATION,
            ).count(),
            "prioritized_screenings": prioritized_screenings[:6],
            "recent_medical_reviews": screening_results[:5],
        }
        context.update(_build_schedule_context(today))
        return render(request, "users/staff_dashboard.html", context)

    if user.role == User.ROLE_DOCTOR:
        return redirect("/medical/dashboard/")

    if user.role != User.ROLE_CITIZEN:
        return redirect("/auth/login-page/")

    hero_images = _get_dashboard_hero_images()
    return render(
        request,
        "users/dashboard.html",
        {
            "user": user,
            "dashboard_hero_images": hero_images,
            "dashboard_hero_images_json": json.dumps(hero_images),
        },
    )


def profile(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role != User.ROLE_CITIZEN:
        return redirect("/users/dashboard/")

    if request.method == "POST":
        user.full_name = request.POST.get("full_name", "").strip() or user.full_name
        new_email = request.POST.get("email", "").strip().lower()
        user.phone_number = request.POST.get("phone_number", "").strip()
        user.gender = request.POST.get("gender", "").strip()
        user.date_of_birth = request.POST.get("date_of_birth") or None
        user.blood_group = request.POST.get("blood_group", "UNKNOWN").strip() or "UNKNOWN"
        user.allergies = request.POST.get("allergies", "").strip()
        user.medical_history = request.POST.get("medical_history", "").strip()
        avatar_data = request.POST.get("avatar_data", "").strip()
        if avatar_data:
            user.avatar_data = avatar_data
        if request.POST.get("remove_avatar") == "1":
            user.avatar_data = ""

        if new_email and new_email != user.email:
            user.email = new_email

        try:
            user.save()
        except IntegrityError:
            return render(
                request,
                "users/profile.html",
                {
                    "user": user,
                    "phone": user.phone_number or "Chưa cập nhật",
                    "gender": user.gender or "Thêm thông tin",
                    "date_of_birth": user.date_of_birth,
                    "blood_group": user.blood_group or "UNKNOWN",
                    "allergies": user.allergies or "Chưa cập nhật",
                    "medical_history": user.medical_history or "Chưa cập nhật",
                    "error_message": "Email đã tồn tại. Vui lòng chọn email khác.",
                    "success_message": "",
                    "blood_group_choices": User.BLOOD_GROUP_CHOICES,
                },
            )
        return redirect("/users/profile/?updated=1")

    context = {
        "user": user,
        "phone": user.phone_number or "Chưa cập nhật",
        "gender": user.gender or "Thêm thông tin",
        "date_of_birth": user.date_of_birth,
        "blood_group": user.blood_group or "UNKNOWN",
        "allergies": user.allergies or "Chưa cập nhật",
        "medical_history": user.medical_history or "Chưa cập nhật",
        "error_message": "",
        "success_message": "Cập nhật hồ sơ thành công." if request.GET.get("updated") == "1" else "",
        "blood_group_choices": User.BLOOD_GROUP_CHOICES,
    }
    return render(request, "users/profile.html", context)


def screening_portal(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role != User.ROLE_CITIZEN:
        return redirect("/users/dashboard/")

    bookings = list(
        Booking.objects.filter(Q(user=user) | Q(email__iexact=user.email))
        .order_by("vaccine_date", "-id")
    )
    booking_ids = [booking.id for booking in bookings]
    declarations = {
        item.booking_id: item
        for item in PreScreeningDeclaration.objects.filter(booking_id__in=booking_ids)
    }
    screening_results = {
        item.booking_id: item
        for item in ScreeningResult.objects.filter(booking_id__in=booking_ids)
    }
    status_labels = {
        Booking.STATUS_PENDING: "Chờ xác nhận",
        Booking.STATUS_CONFIRMED: "Đã xác nhận",
        Booking.STATUS_CHECKED_IN: "Đã check-in",
        Booking.STATUS_READY_TO_INJECT: "Chờ tiêm",
        Booking.STATUS_IN_OBSERVATION: "Đang theo dõi",
        Booking.STATUS_COMPLETED: "Đã hoàn thành",
        Booking.STATUS_DELAYED: "Tạm hoãn",
        Booking.STATUS_CANCELLED: "Đã hủy",
    }

    screening_bookings = []
    for booking in bookings:
        declaration = declarations.get(booking.id)
        screening_result = screening_results.get(booking.id)
        screening_bookings.append(
            {
                "id": booking.id,
                "vaccine_name": booking.vaccine_name,
                "vaccine_date": booking.vaccine_date.isoformat(),
                "dose_number": booking.dose_number,
                "status": booking.status,
                "status_label": status_labels.get(booking.status, booking.status),
                "can_declare": booking.status
                not in [Booking.STATUS_CANCELLED, Booking.STATUS_COMPLETED, Booking.STATUS_READY_TO_INJECT],
                "declaration": (
                    {
                        "has_fever": declaration.has_fever,
                        "has_allergy_history": declaration.has_allergy_history,
                        "has_chronic_condition": declaration.has_chronic_condition,
                        "recent_symptoms": declaration.recent_symptoms or "",
                        "current_medications": declaration.current_medications or "",
                        "note": declaration.note or "",
                        "updated_at": declaration.updated_at.isoformat(),
                    }
                    if declaration
                    else None
                ),
                "screening_result": (
                    {
                        "temperature": screening_result.temperature,
                        "blood_pressure": screening_result.blood_pressure,
                        "is_eligible": screening_result.is_eligible,
                        "decision": screening_result.decision,
                        "doctor_note": screening_result.doctor_note or "",
                        "created_at": screening_result.created_at.isoformat(),
                    }
                    if screening_result
                    else None
                ),
            }
        )

    declarable_screening_count = sum(1 for item in screening_bookings if item["can_declare"])

    return render(
        request,
        "users/screening.html",
        {
            "user": user,
            "screening_bookings_count": len(screening_bookings),
            "declarable_screening_count": declarable_screening_count,
            "screening_bookings_data": screening_bookings,
            "selected_booking_id": request.GET.get("booking", ""),
        },
    )


def vaccine_packages(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    return render(request, "users/citizen_info.html", _build_citizen_page_context(user, "packages"))


def vaccination_system(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    return render(request, "users/citizen_info.html", _build_citizen_page_context(user, "system"))


def vaccination_knowledge(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    return render(request, "users/citizen_info.html", _build_citizen_page_context(user, "knowledge"))
