import calendar
from datetime import date
from django.shortcuts import redirect, render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from feature.authentication.models import User
from feature.booking.models import Booking
from feature.booking.serializers import BookingSerializer

from .models import ScreeningResult, VaccinationLog, PostInjectionTracking
from .serializers import (
    ScreeningResultSerializer,
    VaccinationLogSerializer,
    PostInjectionTrackingSerializer
)


def _get_session_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None, redirect('/auth/login-page/')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return None, redirect('/auth/login-page/')

    return user, None


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

def medical_dashboard(request):
    """Render the Medical frontend HTML page."""
    user, redirect_response = _get_session_user(request)
    if redirect_response:
        return redirect_response

    today = date.today()
    context = {
        'user': user,
        'today': today,
    }
    context.update(_build_schedule_context(today))
    return render(request, 'medical/medical.html', context)


@api_view(['GET'])
def today_bookings(request):
    """Return a list of bookings where vaccine_date is today."""
    today = date.today()
    bookings = Booking.objects.filter(vaccine_date=today)
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
def check_in_booking(request, booking_id):
    """Change the Booking status to 'checked_in'."""
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

    booking.status = Booking.STATUS_CHECKED_IN
    booking.save()
    
    return Response({'status': 'checked_in', 'booking_id': booking.id})


@api_view(['POST'])
def submit_screening_result(request):
    """
    Create ScreeningResult. 
    If is_eligible is True, update Booking status to 'screened'. 
    If False, update to 'delayed'.
    """
    booking_id = request.data.get('booking')
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Get existing or create new
    try:
        screening = ScreeningResult.objects.get(booking=booking)
        serializer = ScreeningResultSerializer(screening, data=request.data)
    except ScreeningResult.DoesNotExist:
        serializer = ScreeningResultSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        
        is_eligible = serializer.validated_data.get('is_eligible')
        if is_eligible:
            booking.status = Booking.STATUS_SCREENED
        else:
            booking.status = Booking.STATUS_DELAYED
        booking.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def submit_vaccination_log(request):
    """
    Create VaccinationLog. 
    Update the Booking status to 'completed'.
    Includes a comment for triggering the inventory module.
    """
    booking_id = request.data.get('booking')
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Get existing or create new
    try:
        vaccination = VaccinationLog.objects.get(booking=booking)
        serializer = VaccinationLogSerializer(vaccination, data=request.data)
    except VaccinationLog.DoesNotExist:
        serializer = VaccinationLogSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        
        booking.status = Booking.STATUS_COMPLETED
        booking.save()
        
        # TODO: Trigger Inventory module to deduct 1 vaccine dose here
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def submit_post_injection_tracking(request):
    """Create PostInjectionTracking from booking ID."""
    booking_id = request.data.get('booking')
    try:
        vaccination_log = VaccinationLog.objects.get(booking__id=booking_id)
    except VaccinationLog.DoesNotExist:
        return Response({'detail': 'Vaccination Log not found for this booking.'}, status=status.HTTP_404_NOT_FOUND)

    # Prepare data for serializer
    data = request.data.copy()
    data['vaccination_log'] = vaccination_log.id

    serializer = PostInjectionTrackingSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
