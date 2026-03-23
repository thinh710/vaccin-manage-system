from django.urls import path
from .views import (
    medical_dashboard,
    today_bookings,
    check_in_booking,
    submit_screening_result,
    submit_vaccination_log,
    submit_post_injection_tracking
)

urlpatterns = [
    path('dashboard/', medical_dashboard, name='medical-dashboard-page'),
    path('today/', today_bookings, name='medical-today'),
    path('<int:booking_id>/check-in/', check_in_booking, name='medical-check-in'),
    path('screening/', submit_screening_result, name='medical-screening'),
    path('inject/', submit_vaccination_log, name='medical-inject'),
    path('monitor/', submit_post_injection_tracking, name='medical-monitor'),
]
