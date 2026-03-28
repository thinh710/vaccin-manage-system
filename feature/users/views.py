import calendar
import json
from pathlib import Path
from django.db import IntegrityError
from django.db.models import Count, Q
from django.templatetags.static import static
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils import timezone

from feature.authentication.models import User
from feature.booking.models import Booking


def _build_schedule_context(today):
    calendar_builder = calendar.Calendar(firstweekday=0)
    month_weeks = []
    booking_dates = set(
        Booking.objects.filter(vaccine_date__year=today.year, vaccine_date__month=today.month)
        .values_list('vaccine_date', flat=True)
    )

    for week in calendar_builder.monthdayscalendar(today.year, today.month):
        cells = []
        for day in week:
            cell_date = None
            if day:
                cell_date = today.replace(day=day)
            cells.append(
                {
                    'day': day,
                    'is_today': bool(cell_date and cell_date == today),
                    'has_booking': bool(cell_date and cell_date in booking_dates),
                }
            )
        month_weeks.append(cells)

    vaccination_schedule = list(
        Booking.objects.filter(vaccine_date__gte=today)
        .order_by('vaccine_date', 'id')[:4]
    )
    health_schedule = list(
        Booking.objects.filter(vaccine_date__gte=today)
        .exclude(status=Booking.STATUS_COMPLETED)
        .order_by('vaccine_date', 'id')[:4]
    )

    return {
        'calendar_month_label': f'Thang {today.month}',
        'calendar_weekdays': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
        'calendar_weeks': month_weeks,
        'vaccination_schedule': vaccination_schedule,
        'health_schedule': health_schedule,
    }


def _get_session_user(request: HttpRequest):
    user_id = request.session.get('user_id')
    if not user_id:
        return None, redirect('/auth/login-page/')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None, redirect('/auth/login-page/')

    return user, None


def _get_dashboard_hero_images():
    image_dir = Path(__file__).resolve().parent / 'static' / 'users' / 'img' / 'dashboard-hero'
    supported_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    images = []

    if image_dir.exists():
        for image_path in sorted(image_dir.iterdir()):
            if image_path.is_file() and image_path.suffix.lower() in supported_extensions:
                images.append(static(f'users/img/dashboard-hero/{image_path.name}'))

    if not images:
        images.append(static('authentication/img/vaccine-db.jpg'))

    return images


def dashboard(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role == User.ROLE_ADMIN:
        today = timezone.localdate()
        bookings = Booking.objects.all()
        upcoming_bookings = bookings.filter(vaccine_date__gte=today).order_by('vaccine_date', 'id')
        inventory_summary = []
        inventory_rows = (
            bookings.values('vaccine_name')
            .annotate(
                total_bookings=Count('id'),
                upcoming_doses=Count('id', filter=Q(vaccine_date__gte=today)),
            )
            .order_by('-upcoming_doses', 'vaccine_name')[:5]
        )
        for row in inventory_rows:
            estimated_stock = max(120 - row['upcoming_doses'] * 6, 0)
            inventory_summary.append(
                {
                    'vaccine_name': row['vaccine_name'],
                    'estimated_stock': estimated_stock,
                    'total_bookings': row['total_bookings'],
                    'upcoming_doses': row['upcoming_doses'],
                    'is_low_stock': estimated_stock < 40,
                }
            )

        context = {
            'user': user,
            'today': today,
            'total_bookings': bookings.count(),
            'todays_bookings_count': bookings.filter(vaccine_date=today).count(),
            'upcoming_bookings_count': upcoming_bookings.count(),
            'pending_count': bookings.filter(status=Booking.STATUS_PENDING).count(),
            'confirmed_count': bookings.filter(status=Booking.STATUS_CONFIRMED).count(),
            'cancelled_count': bookings.filter(status=Booking.STATUS_CANCELLED).count(),
            'recent_upcoming_bookings': list(upcoming_bookings[:5]),
            'inventory_summary': inventory_summary,
        }
        context.update(_build_schedule_context(today))
        return render(request, 'users/admin_dashboard.html', context)

    if user.role == User.ROLE_STAFF:
        today = timezone.localdate()
        context = {
            'user': user,
            'today': today,
            'todays_bookings_count': 0,
            'screened_count': 0,
            'fit_count': 0,
            'not_fit_count': 0,
            'waiting_screening_count': 0,
            'prioritized_screenings': [],
            'recent_medical_reviews': [],
        }
        context.update(_build_schedule_context(today))
        return render(request, 'users/staff_dashboard.html', context)

    if user.role != User.ROLE_CITIZEN:
        return redirect('/auth/login-page/')

    return render(
        request,
        'users/dashboard.html',
        {
            'user': user,
            'dashboard_hero_images': _get_dashboard_hero_images(),
            'dashboard_hero_images_json': json.dumps(_get_dashboard_hero_images()),
        },
    )


def profile(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role != User.ROLE_CITIZEN:
        return redirect('/users/dashboard/')

    if request.method == 'POST':
        user.full_name = request.POST.get('full_name', '').strip() or user.full_name
        new_email = request.POST.get('email', '').strip().lower()
        user.phone_number = request.POST.get('phone_number', '').strip()
        user.gender = request.POST.get('gender', '').strip()
        user.date_of_birth = request.POST.get('date_of_birth') or None
        user.blood_group = request.POST.get('blood_group', 'UNKNOWN').strip() or 'UNKNOWN'
        user.allergies = request.POST.get('allergies', '').strip()
        user.medical_history = request.POST.get('medical_history', '').strip()
        avatar_data = request.POST.get('avatar_data', '').strip()
        if avatar_data:
            user.avatar_data = avatar_data
        if request.POST.get('remove_avatar') == '1':
            user.avatar_data = ''

        if new_email and new_email != user.email:
            user.email = new_email

        try:
            user.save()
        except IntegrityError:
            return render(
                request,
                'users/profile.html',
                {
                    'user': user,
                    'phone': user.phone_number or 'Chua cap nhat',
                    'gender': user.gender or 'Them thong tin',
                    'date_of_birth': user.date_of_birth,
                    'blood_group': user.blood_group or 'UNKNOWN',
                    'allergies': user.allergies or 'Chua cap nhat',
                    'medical_history': user.medical_history or 'Chua cap nhat',
                    'error_message': 'Email da ton tai. Vui long chon email khac.',
                    'success_message': '',
                    'blood_group_choices': User.BLOOD_GROUP_CHOICES,
                },
            )
        return redirect('/users/profile/?updated=1')

    context = {
        'user': user,
        'phone': user.phone_number or 'Chua cap nhat',
        'gender': user.gender or 'Them thong tin',
        'date_of_birth': user.date_of_birth,
        'blood_group': user.blood_group or 'UNKNOWN',
        'allergies': user.allergies or 'Chua cap nhat',
        'medical_history': user.medical_history or 'Chua cap nhat',
        'error_message': '',
        'success_message': 'Cap nhat ho so thanh cong.' if request.GET.get('updated') == '1' else '',
        'blood_group_choices': User.BLOOD_GROUP_CHOICES,
    }
    return render(request, 'users/profile.html', context)
