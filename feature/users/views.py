from django.db import IntegrityError
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils import timezone

from feature.authentication.models import User


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


def dashboard(request: HttpRequest):
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    if user.role == User.ROLE_ADMIN:
        today = timezone.localdate()
        context = {
            'user': user,
            'today': today,
            'total_bookings': 0,
            'todays_bookings_count': 0,
            'upcoming_bookings_count': 0,
            'pending_count': 0,
            'confirmed_count': 0,
            'cancelled_count': 0,
            'recent_upcoming_bookings': [],
            'inventory_summary': [],
        }
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
        return render(request, 'users/staff_dashboard.html', context)

    if user.role != User.ROLE_CITIZEN:
        return redirect('/auth/login-page/')

    return render(request, 'users/dashboard.html', {'user': user})


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
