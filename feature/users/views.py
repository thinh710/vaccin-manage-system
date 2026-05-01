import calendar
from pathlib import Path

from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from feature.assets.models import Vaccine
from feature.authentication.models import User
from feature.booking.models import Booking
from feature.booking.serializers import BookingSerializer
from feature.medical.models import OnlineEligibilityReview, PreScreeningDeclaration, ScreeningResult


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
        "calendar_month_label": f"ThÃ¡ng {today.month}",
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
            "eyebrow": "GÃ³i váº¯c xin",
            "title": "Chá»n gÃ³i váº¯c xin phÃ¹ há»£p cho tá»«ng giai Ä‘oáº¡n",
            "description": (
                "Tá»•ng há»£p cÃ¡c gÃ³i tiÃªm phá»• biáº¿n Ä‘á»ƒ ngÆ°á»i dÃ¹ng tham kháº£o nhanh trÆ°á»›c khi Ä‘áº·t lá»‹ch. "
                "Trang nÃ y giÃºp cÃ´ng dÃ¢n xem nhanh nhÃ³m váº¯c xin, Ä‘á»‘i tÆ°á»£ng phÃ¹ há»£p vÃ  hÆ°á»›ng Ä‘áº·t háº¹n tiáº¿p theo."
            ),
            "primary_action_label": "Äáº·t lá»‹ch ngay",
            "primary_action_href": "/booking/portal/",
            "secondary_action_label": "Xem lá»‹ch háº¹n",
            "secondary_action_href": "/booking/portal/",
            "highlights": [
                {
                    "title": "GÃ³i tráº» em",
                    "body": "Táº­p trung cÃ¡c mÅ©i cÆ¡ báº£n, nháº¯c láº¡i vÃ  theo dÃµi cÃ¡c má»‘c tiÃªm quan trá»ng cho bÃ©.",
                },
                {
                    "title": "GÃ³i thanh niÃªn",
                    "body": "PhÃ¹ há»£p vá»›i HPV, viÃªm gan, cÃºm mÃ¹a vÃ  cÃ¡c mÅ©i cáº§n nháº¯c láº¡i theo Ä‘á»™ tuá»•i.",
                },
                {
                    "title": "GÃ³i gia Ä‘Ã¬nh",
                    "body": "Tá»•ng há»£p nhu cáº§u tiÃªm cho nhiá»u thÃ nh viÃªn Ä‘á»ƒ Ä‘áº·t lá»‹ch nhanh hÆ¡n trÃªn cÃ¹ng má»™t há»‡ thá»‘ng.",
                },
            ],
        },
        "system": {
            "eyebrow": "Há»‡ thá»‘ng tiÃªm chá»§ng",
            "title": "Theo dÃµi toÃ n bá»™ luá»“ng tiÃªm chá»§ng trÃªn há»‡ thá»‘ng",
            "description": (
                "Trang tá»•ng quan giÃºp ngÆ°á»i dÃ¹ng hiá»ƒu quy trÃ¬nh tá»« booking, check-in, sÃ ng lá»c, "
                "tiÃªm vÃ  theo dÃµi sau tiÃªm. ÄÃ¢y lÃ  Ä‘iá»ƒm vÃ o Ä‘á»ƒ cÃ´ng dÃ¢n náº¯m rÃµ cÃ¡c bÆ°á»›c cáº§n cÃ³ khi Ä‘i tiÃªm."
            ),
            "primary_action_label": "Má»Ÿ cá»•ng Ä‘áº·t lá»‹ch",
            "primary_action_href": "/booking/portal/",
            "secondary_action_label": "Cáº­p nháº­t há»“ sÆ¡",
            "secondary_action_href": "/users/profile/",
            "highlights": [
                {
                    "title": "BÆ°á»›c 1: Äáº·t lá»‹ch",
                    "body": "NgÆ°á»i dÃ¹ng táº¡o booking, chá»n váº¯c xin vÃ  ngÃ y tiÃªm trong portal.",
                },
                {
                    "title": "BÆ°á»›c 2: SÃ ng lá»c",
                    "body": "NhÃ¢n viÃªn y táº¿ tiáº¿p nháº­n, Ä‘Ã¡nh giÃ¡ sá»©c khá»e vÃ  cáº­p nháº­t tráº¡ng thÃ¡i.",
                },
                {
                    "title": "BÆ°á»›c 3: Theo dÃµi",
                    "body": "Sau khi tiÃªm, há»‡ thá»‘ng tiáº¿p tá»¥c lÆ°u káº¿t quáº£ vÃ  há»— trá»£ tra cá»©u lá»‹ch sá»­.",
                },
            ],
        },
        "knowledge": {
            "eyebrow": "Kiáº¿n thá»©c tiÃªm chá»§ng",
            "title": "Kiáº¿n thá»©c cÆ¡ báº£n Ä‘á»ƒ Ä‘i tiÃªm an tÃ¢m hÆ¡n",
            "description": (
                "Tá»•ng há»£p nhá»¯ng lÆ°u Ã½ trÆ°á»›c tiÃªm, sau tiÃªm vÃ  cÃ¡c nguyÃªn táº¯c theo dÃµi sá»©c khá»e. "
                "Trang nÃ y Ä‘Ã³ng vai trÃ² nhÆ° má»™t knowledge hub cÆ¡ báº£n Ä‘á»ƒ hoÃ n chá»‰nh Ä‘iá»u hÆ°á»›ng trong dashboard."
            ),
            "primary_action_label": "Äáº·t lá»‹ch tÆ° váº¥n",
            "primary_action_href": "/booking/portal/",
            "secondary_action_label": "Vá» dashboard",
            "secondary_action_href": "/users/dashboard/",
            "highlights": [
                {
                    "title": "TrÆ°á»›c khi tiÃªm",
                    "body": "Ngá»§, Äƒn uá»‘ng Ä‘áº§y Ä‘á»§, mang theo thÃ´ng tin y táº¿ vÃ  khai bÃ¡o tiá»n sá»­ dá»‹ á»©ng náº¿u cÃ³.",
                },
                {
                    "title": "Sau khi tiÃªm",
                    "body": "Theo dÃµi pháº£n á»©ng táº¡i chá»— vÃ  toÃ n thÃ¢n, liÃªn há»‡ cÆ¡ sá»Ÿ y táº¿ náº¿u cÃ³ dáº¥u hiá»‡u báº¥t thÆ°á»ng.",
                },
                {
                    "title": "Nhá»› lá»‹ch nháº¯c láº¡i",
                    "body": "Theo dÃµi booking vÃ  má»‘c tiÃªm nháº¯c láº¡i Ä‘á»ƒ Ä‘áº£m báº£o hiá»‡u quáº£ báº£o vá»‡.",
                },
            ],
        },
    }

    context = pages[page_key].copy()
    context["user"] = user
    context["page_key"] = page_key
    return context


def _booking_status_labels():
    return {
        Booking.STATUS_AWAITING_ELIGIBILITY: "Cho bac si duyet online",
        Booking.STATUS_PENDING: "Cho xac nhan",
        Booking.STATUS_DEPOSIT_PENDING: "Cho dat coc",
        Booking.STATUS_CONFIRMED: "Da xac nhan",
        Booking.STATUS_INELIGIBLE: "Khong du dieu kien tiem",
        Booking.STATUS_CHECKED_IN: "Da check-in",
        Booking.STATUS_READY_TO_INJECT: "Cho tiem",
        Booking.STATUS_IN_OBSERVATION: "Dang theo doi",
        Booking.STATUS_COMPLETED: "Da hoan thanh",
        Booking.STATUS_DELAYED: "Tam hoan",
        Booking.STATUS_CANCELLED: "Da huy",
    }


def _screening_can_declare(booking):
    return booking.status not in [
        Booking.STATUS_CANCELLED,
        Booking.STATUS_COMPLETED,
        Booking.STATUS_CHECKED_IN,
        Booking.STATUS_READY_TO_INJECT,
        Booking.STATUS_IN_OBSERVATION,
    ]


def _serialize_citizen_declaration(declaration):
    if not declaration:
        return None
    return {
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
        "updated_at": declaration.updated_at.isoformat(),
    }


def _serialize_citizen_online_review(review):
    if not review:
        return None
    return {
        "decision": review.decision,
        "doctor_note": review.doctor_note or "",
        "reviewed_at": review.reviewed_at.isoformat(),
        "reviewed_by_name": review.reviewed_by.full_name if review.reviewed_by else "",
    }


def _serialize_citizen_screening_result(screening_result):
    if not screening_result:
        return None
    return {
        "temperature": screening_result.temperature,
        "blood_pressure": screening_result.blood_pressure,
        "is_eligible": screening_result.is_eligible,
        "decision": screening_result.decision,
        "doctor_note": screening_result.doctor_note or "",
        "created_at": screening_result.created_at.isoformat(),
    }

def _build_screening_bookings_data(user):
    bookings = list(
        Booking.objects.filter(Q(user=user) | Q(email__iexact=user.email))
        .order_by("vaccine_date", "-id")
    )
    booking_ids = [booking.id for booking in bookings]
    declarations = {
        item.booking_id: item
        for item in PreScreeningDeclaration.objects.filter(booking_id__in=booking_ids)
    }
    online_reviews = {
        item.booking_id: item
        for item in OnlineEligibilityReview.objects.select_related("reviewed_by").filter(booking_id__in=booking_ids)
    }
    screening_results = {
        item.booking_id: item
        for item in ScreeningResult.objects.filter(booking_id__in=booking_ids)
    }
    status_labels = _booking_status_labels()

    screening_bookings = []
    for booking in bookings:
        screening_bookings.append(
            {
                "id": booking.id,
                "vaccine_name": booking.vaccine_name,
                "vaccine_date": booking.vaccine_date.isoformat(),
                "dose_number": booking.dose_number,
                "status": booking.status,
                "status_label": status_labels.get(booking.status, booking.status),
                "can_declare": _screening_can_declare(booking),
                "declaration": _serialize_citizen_declaration(declarations.get(booking.id)),
                "online_review": _serialize_citizen_online_review(online_reviews.get(booking.id)),
                "screening_result": _serialize_citizen_screening_result(screening_results.get(booking.id)),
            }
        )

    return screening_bookings


def _dashboard_action(label, href):
    tab_by_href = {
        "/booking/portal/": "appointments",
        "/users/dashboard/": "vaccines",
    }
    return {
        "label": label,
        "href": href,
        "tab": tab_by_href.get(href, ""),
    }


def _build_dashboard_info_pages(_user):
    return [
        {
            "key": "packages",
            "eyebrow": "GÃ³i váº¯c xin",
            "title": "Chá»n gÃ³i váº¯c xin phÃ¹ há»£p cho tá»«ng giai Ä‘oáº¡n",
            "description": (
                "Tá»•ng há»£p cÃ¡c gÃ³i tiÃªm phá»• biáº¿n Ä‘á»ƒ tham kháº£o nhanh trÆ°á»›c khi Ä‘áº·t lá»‹ch. "
                "Báº¡n cÃ³ thá»ƒ xem nhÃ³m váº¯c xin, Ä‘á»‘i tÆ°á»£ng phÃ¹ há»£p vÃ  chuyá»ƒn tháº³ng sang lá»‹ch háº¹n."
            ),
            "highlights": [
                {
                    "title": "GÃ³i tráº» em",
                    "body": "Táº­p trung cÃ¡c mÅ©i cÆ¡ báº£n, mÅ©i nháº¯c láº¡i vÃ  cÃ¡c má»‘c tiÃªm quan trá»ng cho bÃ©.",
                },
                {
                    "title": "GÃ³i thanh niÃªn",
                    "body": "PhÃ¹ há»£p vá»›i HPV, viÃªm gan, cÃºm mÃ¹a vÃ  cÃ¡c mÅ©i cáº§n nháº¯c láº¡i theo Ä‘á»™ tuá»•i.",
                },
                {
                    "title": "GÃ³i gia Ä‘Ã¬nh",
                    "body": "Tá»•ng há»£p nhu cáº§u tiÃªm cho nhiá»u thÃ nh viÃªn Ä‘á»ƒ Ä‘áº·t lá»‹ch nhanh hÆ¡n trÃªn cÃ¹ng má»™t há»‡ thá»‘ng.",
                },
            ],
            "details": [
                {
                    "title": "CÃ¡c gÃ³i phá»• biáº¿n",
                    "items": [
                        "GÃ³i tráº» sÆ¡ sinh vÃ  tráº» nhá»: 5 trong 1, 6 trong 1, pháº¿ cáº§u, rota, cÃºm mÃ¹a vÃ  cÃ¡c mÅ©i nháº¯c theo tuá»•i.",
                        "GÃ³i há»c Ä‘Æ°á»ng: sá»Ÿi - quai bá»‹ - rubella, thá»§y Ä‘áº­u, viÃªm nÃ£o Nháº­t Báº£n, cÃºm mÃ¹a vÃ  nÃ£o mÃ´ cáº§u.",
                        "GÃ³i thanh thiáº¿u niÃªn: HPV, viÃªm gan B, uá»‘n vÃ¡n, cÃºm mÃ¹a vÃ  cÃ¡c mÅ©i cáº§n nháº¯c trÆ°á»›c khi Ä‘i há»c xa.",
                        "GÃ³i ngÆ°á»i lá»›n vÃ  ngÆ°á»i cao tuá»•i: cÃºm mÃ¹a, pháº¿ cáº§u, zona, viÃªm gan vÃ  cÃ¡c mÅ©i theo bá»‡nh ná»n.",
                    ],
                },
                {
                    "title": "CÃ¡ch chá»n gÃ³i phÃ¹ há»£p",
                    "items": [
                        "Dá»±a trÃªn Ä‘á»™ tuá»•i, lá»‹ch sá»­ tiÃªm trÆ°á»›c Ä‘Ã³, bá»‡nh ná»n vÃ  nguy cÆ¡ phÆ¡i nhiá»…m.",
                        "Æ¯u tiÃªn cÃ¡c mÅ©i cÃ²n thiáº¿u hoáº·c sáº¯p Ä‘áº¿n háº¡n nháº¯c láº¡i.",
                        "Khai bÃ¡o thÃ´ng tin sá»©c khá»e trÆ°á»›c tiÃªm Ä‘á»ƒ nhÃ¢n viÃªn y táº¿ tÆ° váº¥n chÃ­nh xÃ¡c hÆ¡n.",
                    ],
                },
                {
                    "title": "LÆ°u Ã½ khi Ä‘áº·t gÃ³i",
                    "items": [
                        "Má»—i ngÆ°á»i nÃªn cÃ³ lá»‹ch háº¹n riÃªng Ä‘á»ƒ há»‡ thá»‘ng theo dÃµi Ä‘Ãºng mÅ©i tiÃªm.",
                        "Náº¿u chÆ°a cháº¯c Ä‘Ã£ tá»«ng tiÃªm mÅ©i nÃ o, hÃ£y ghi chÃº trong lá»‹ch háº¹n Ä‘á»ƒ Ä‘Æ°á»£c kiá»ƒm tra.",
                        "Má»™t sá»‘ váº¯c xin cáº§n nhiá»u mÅ©i, nÃªn Ä‘áº·t lá»‹ch nháº¯c Ä‘á»ƒ khÃ´ng bá» lá»¡ thá»i Ä‘iá»ƒm báº£o vá»‡ tá»‘t nháº¥t.",
                    ],
                },
            ],
            "actions": [
                _dashboard_action("Äáº·t lá»‹ch ngay", "/booking/portal/"),
                _dashboard_action("Xem lá»‹ch háº¹n", "/booking/portal/"),
            ],
        },
        {
            "key": "system",
            "eyebrow": "Há»‡ thá»‘ng tiÃªm chá»§ng",
            "title": "Theo dÃµi toÃ n bá»™ luá»“ng tiÃªm chá»§ng trÃªn há»‡ thá»‘ng",
            "description": (
                "Náº¯m rÃµ quy trÃ¬nh tá»« Ä‘áº·t lá»‹ch, check-in, sÃ ng lá»c, tiÃªm vÃ  theo dÃµi sau tiÃªm. "
                "Má»—i bÆ°á»›c Ä‘á»u Ä‘Æ°á»£c cáº­p nháº­t Ä‘á»ƒ báº¡n chá»§ Ä‘á»™ng chuáº©n bá»‹."
            ),
            "highlights": [
                {
                    "title": "BÆ°á»›c 1: Äáº·t lá»‹ch",
                    "body": "Táº¡o lá»‹ch háº¹n, chá»n váº¯c xin vÃ  ngÃ y tiÃªm ngay trong dashboard.",
                },
                {
                    "title": "BÆ°á»›c 2: SÃ ng lá»c",
                    "body": "Khai bÃ¡o trÆ°á»›c tiÃªm Ä‘á»ƒ nhÃ¢n viÃªn y táº¿ tiáº¿p nháº­n vÃ  Ä‘Ã¡nh giÃ¡ sá»©c khá»e nhanh hÆ¡n.",
                },
                {
                    "title": "BÆ°á»›c 3: Theo dÃµi",
                    "body": "Sau khi tiÃªm, há»‡ thá»‘ng lÆ°u tráº¡ng thÃ¡i vÃ  há»— trá»£ tra cá»©u lá»‹ch sá»­ tiÃªm chá»§ng.",
                },
            ],
            "details": [
                {
                    "title": "Quy trÃ¬nh táº¡i há»‡ thá»‘ng",
                    "items": [
                        "Äáº·t lá»‹ch: chá»n váº¯c xin, ngÃ y tiÃªm, sá»‘ Ä‘iá»‡n thoáº¡i vÃ  ghi chÃº y táº¿ cáº§n lÆ°u Ã½.",
                        "XÃ¡c nháº­n: nhÃ¢n viÃªn hoáº·c bÃ¡c sÄ© kiá»ƒm tra lá»‹ch háº¹n vÃ  xÃ¡c nháº­n thá»i gian tiÃªm.",
                        "Check-in: khi Ä‘áº¿n cÆ¡ sá»Ÿ, lá»‹ch háº¹n Ä‘Æ°á»£c chuyá»ƒn sang tráº¡ng thÃ¡i Ä‘Ã£ tiáº¿p nháº­n.",
                        "SÃ ng lá»c: nhÃ¢n viÃªn y táº¿/bÃ¡c sÄ© Ä‘Ã¡nh giÃ¡ Ä‘iá»u kiá»‡n tiÃªm trÆ°á»›c khi chá»‰ Ä‘á»‹nh.",
                        "TiÃªm vÃ  theo dÃµi: sau tiÃªm, há»‡ thá»‘ng lÆ°u tráº¡ng thÃ¡i theo dÃµi vÃ  hoÃ n thÃ nh.",
                    ],
                },
                {
                    "title": "Ã nghÄ©a tráº¡ng thÃ¡i lá»‹ch háº¹n",
                    "items": [
                        "Chá» xÃ¡c nháº­n: lá»‹ch má»›i Ä‘Æ°á»£c táº¡o vÃ  Ä‘ang chá» nhÃ¢n viÃªn kiá»ƒm tra.",
                        "ÄÃ£ xÃ¡c nháº­n: lá»‹ch Ä‘Ã£ Ä‘Æ°á»£c duyá»‡t, báº¡n nÃªn Ä‘áº¿n Ä‘Ãºng ngÃ y Ä‘Ã£ chá»n.",
                        "ÄÃ£ check-in: báº¡n Ä‘Ã£ Ä‘Æ°á»£c tiáº¿p nháº­n táº¡i Ä‘iá»ƒm tiÃªm.",
                        "Chá» tiÃªm hoáº·c Ä‘ang theo dÃµi: lá»‹ch Ä‘ang trong giai Ä‘oáº¡n y táº¿ xá»­ lÃ½.",
                        "Táº¡m hoÃ£n: cáº§n Ä‘áº·t láº¡i lá»‹ch theo ngÃ y phÃ¹ há»£p hÆ¡n.",
                    ],
                },
                {
                    "title": "Báº¡n nÃªn chuáº©n bá»‹",
                    "items": [
                        "Cáº­p nháº­t há»“ sÆ¡ cÃ¡ nhÃ¢n, sá»‘ Ä‘iá»‡n thoáº¡i vÃ  thÃ´ng tin sá»©c khá»e trÆ°á»›c khi Ä‘áº¿n tiÃªm.",
                        "HoÃ n thÃ nh khai bÃ¡o sÃ ng lá»c trong dashboard Ä‘á»ƒ giáº£m thá»i gian chá».",
                        "Mang theo giáº¥y tá» cáº§n thiáº¿t vÃ  lá»‹ch sá»­ tiÃªm náº¿u cÃ³.",
                    ],
                },
            ],
            "actions": [
                _dashboard_action("Má»Ÿ lá»‹ch háº¹n", "/booking/portal/"),
                _dashboard_action("Cáº­p nháº­t há»“ sÆ¡", "/users/profile/"),
            ],
        },
        {
            "key": "knowledge",
            "eyebrow": "Kiáº¿n thá»©c tiÃªm chá»§ng",
            "title": "Kiáº¿n thá»©c cÆ¡ báº£n Ä‘á»ƒ Ä‘i tiÃªm an tÃ¢m hÆ¡n",
            "description": (
                "Nhá»¯ng lÆ°u Ã½ trÆ°á»›c tiÃªm, sau tiÃªm vÃ  nguyÃªn táº¯c theo dÃµi sá»©c khá»e giÃºp báº¡n chuáº©n bá»‹ tá»‘t hÆ¡n "
                "cho tá»«ng buá»•i tiÃªm."
            ),
            "highlights": [
                {
                    "title": "TrÆ°á»›c khi tiÃªm",
                    "body": "Ngá»§, Äƒn uá»‘ng Ä‘áº§y Ä‘á»§, mang theo thÃ´ng tin y táº¿ vÃ  khai bÃ¡o tiá»n sá»­ dá»‹ á»©ng náº¿u cÃ³.",
                },
                {
                    "title": "Sau khi tiÃªm",
                    "body": "Theo dÃµi pháº£n á»©ng táº¡i chá»— vÃ  toÃ n thÃ¢n, liÃªn há»‡ cÆ¡ sá»Ÿ y táº¿ khi cÃ³ dáº¥u hiá»‡u báº¥t thÆ°á»ng.",
                },
                {
                    "title": "Nhá»› lá»‹ch nháº¯c láº¡i",
                    "body": "Theo dÃµi lá»‹ch háº¹n vÃ  cÃ¡c má»‘c nháº¯c láº¡i Ä‘á»ƒ duy trÃ¬ hiá»‡u quáº£ báº£o vá»‡.",
                },
            ],
            "details": [
                {
                    "title": "TrÆ°á»›c khi tiÃªm",
                    "items": [
                        "Ä‚n uá»‘ng bÃ¬nh thÆ°á»ng, ngá»§ Ä‘á»§ vÃ  trÃ¡nh Ä‘á»ƒ cÆ¡ thá»ƒ quÃ¡ má»‡t trÆ°á»›c buá»•i tiÃªm.",
                        "ThÃ´ng bÃ¡o tiá»n sá»­ dá»‹ á»©ng, bá»‡nh ná»n, thuá»‘c Ä‘ang dÃ¹ng hoáº·c pháº£n á»©ng sau tiÃªm trÆ°á»›c Ä‘Ã¢y.",
                        "Náº¿u Ä‘ang sá»‘t, nhiá»…m trÃ¹ng cáº¥p hoáº·c cÃ³ triá»‡u chá»©ng báº¥t thÆ°á»ng, hÃ£y khai bÃ¡o rÃµ trong pháº§n sÃ ng lá»c.",
                    ],
                },
                {
                    "title": "Sau khi tiÃªm",
                    "items": [
                        "á»ž láº¡i theo dÃµi theo hÆ°á»›ng dáº«n cá»§a cÆ¡ sá»Ÿ tiÃªm chá»§ng.",
                        "Má»™t sá»‘ pháº£n á»©ng nháº¹ nhÆ° Ä‘au táº¡i chá»— tiÃªm, sá»‘t nháº¹, má»‡t má»i cÃ³ thá»ƒ xáº£y ra.",
                        "Uá»‘ng Ä‘á»§ nÆ°á»›c, nghá»‰ ngÆ¡i vÃ  theo dÃµi pháº£n á»©ng trong 24-48 giá» Ä‘áº§u.",
                    ],
                },
                {
                    "title": "Khi nÃ o cáº§n liÃªn há»‡ y táº¿",
                    "items": [
                        "Sá»‘t cao kÃ©o dÃ i, khÃ³ thá»Ÿ, ná»•i má» Ä‘ay lan rá»™ng, tÃ­m tÃ¡i hoáº·c lÆ¡ mÆ¡.",
                        "Äau, sÆ°ng, Ä‘á» táº¡i chá»— tiÃªm tÄƒng nhanh hoáº·c cÃ³ dáº¥u hiá»‡u nhiá»…m trÃ¹ng.",
                        "Báº¥t ká»³ triá»‡u chá»©ng nÃ o khiáº¿n báº¡n lo láº¯ng sau tiÃªm.",
                    ],
                },
            ],
            "actions": [
                _dashboard_action("Äáº·t lá»‹ch tÆ° váº¥n", "/booking/portal/"),
                _dashboard_action("Vá» váº¯c xin phÃ²ng bá»‡nh", "/users/dashboard/"),
            ],
        },
    ]


def _build_citizen_dashboard_context(user, request):
    today = timezone.localdate()
    bookings = Booking.objects.filter(Q(user=user) | Q(email__iexact=user.email))
    upcoming_bookings = bookings.filter(vaccine_date__gte=today).exclude(status=Booking.STATUS_CANCELLED)
    status_summary = bookings.values("status").annotate(total=Count("id"))
    status_map = {item["status"]: item["total"] for item in status_summary}
    vaccines = list(
        Vaccine.objects.filter(quantity__gt=0, expiration_date__gte=today)
        .order_by("name")
        .values("id", "name", "quantity", "batch_number", "expiration_date")
    )
    hero_images = _get_dashboard_hero_images()
    screening_bookings = _build_screening_bookings_data(user)
    dashboard_info_pages = _build_dashboard_info_pages(user)

    return {
        "user": user,
        "today": today,
        "dashboard_hero_images": hero_images,
        "dashboard_vaccines": vaccines,
        "dashboard_vaccine_options": [vaccine["name"] for vaccine in vaccines],
        "dashboard_booking_stats": {
            "total": bookings.count(),
            "pending": status_map.get(Booking.STATUS_PENDING, 0),
            "confirmed": status_map.get(Booking.STATUS_CONFIRMED, 0),
            "completed": status_map.get(Booking.STATUS_COMPLETED, 0),
            "upcoming": upcoming_bookings.count(),
        },
        "dashboard_initial_bookings": BookingSerializer(
            bookings.order_by("-id")[:12],
            many=True,
            context={"session_user": user},
        ).data,
        "dashboard_screening_bookings": screening_bookings,
        "dashboard_screening_count": len(screening_bookings),
        "dashboard_declarable_screening_count": sum(1 for item in screening_bookings if item["can_declare"]),
        "dashboard_info_pages": dashboard_info_pages,
        "dashboard_static_pages": dashboard_info_pages,
        "dashboard_config": {
            "userRole": user.role,
            "today": today.isoformat(),
            "userFullName": user.full_name or "",
            "userEmail": user.email or "",
            "userPhone": user.phone_number or "",
            "heroImages": hero_images,
            "selectedTab": request.GET.get("tab", ""),
            "selectedScreeningBookingId": request.GET.get("booking", ""),
        },
    }


@ensure_csrf_cookie
def dashboard(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role == User.ROLE_ADMIN:
        return redirect("/assets/")

    if user.role == User.ROLE_STAFF:
        return redirect("/medical/dashboard/")

    if user.role == User.ROLE_DOCTOR:
        return redirect("/medical/dashboard/")

    if user.role != User.ROLE_CITIZEN:
        return redirect("/auth/login-page/")

    return render(request, "users/dashboard.html", _build_citizen_dashboard_context(user, request))


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
                    "phone": user.phone_number or "ChÆ°a cáº­p nháº­t",
                    "gender": user.gender or "ThÃªm thÃ´ng tin",
                    "date_of_birth": user.date_of_birth,
                    "blood_group": user.blood_group or "UNKNOWN",
                    "allergies": user.allergies or "ChÆ°a cáº­p nháº­t",
                    "medical_history": user.medical_history or "ChÆ°a cáº­p nháº­t",
                    "error_message": "Email Ä‘Ã£ tá»“n táº¡i. Vui lÃ²ng chá»n email khÃ¡c.",
                    "success_message": "",
                    "blood_group_choices": User.BLOOD_GROUP_CHOICES,
                },
            )
        return redirect("/users/profile/?updated=1")

    context = {
        "user": user,
        "phone": user.phone_number or "ChÆ°a cáº­p nháº­t",
        "gender": user.gender or "ThÃªm thÃ´ng tin",
        "date_of_birth": user.date_of_birth,
        "blood_group": user.blood_group or "UNKNOWN",
        "allergies": user.allergies or "ChÆ°a cáº­p nháº­t",
        "medical_history": user.medical_history or "ChÆ°a cáº­p nháº­t",
        "error_message": "",
        "success_message": "Cáº­p nháº­t há»“ sÆ¡ thÃ nh cÃ´ng." if request.GET.get("updated") == "1" else "",
        "blood_group_choices": User.BLOOD_GROUP_CHOICES,
    }
    return render(request, "users/profile.html", context)


def screening_portal(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role != User.ROLE_CITIZEN:
        return redirect("/users/dashboard/")

    selected_booking_id = request.GET.get("booking", "")
    destination = "/users/dashboard/?tab=screening"
    if selected_booking_id:
        destination = f"{destination}&booking={selected_booking_id}"
    return redirect(destination)

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

