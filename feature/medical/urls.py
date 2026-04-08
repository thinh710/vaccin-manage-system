from django.urls import path
from .views import (
    medical_dashboard,
    today_bookings,
    pre_screening_declaration_detail,
    check_in_booking,
    submit_screening_result,
    submit_vaccination_log,
    submit_post_injection_tracking,
    walkin_checkin,
    reschedule_booking,
)

urlpatterns = [
    path('dashboard/', medical_dashboard, name='medical-dashboard-page'),
    path('today/', today_bookings, name='medical-today'),
    path('pre-screening/<int:booking_id>/', pre_screening_declaration_detail, name='medical-pre-screening'),
    # Alias: Staff điền bổ sung tờ khai cho ca thiếu sau check-in
    path('<int:booking_id>/pre-screening/add/', pre_screening_declaration_detail, name='medical-pre-screening-add'),
    path('<int:booking_id>/check-in/', check_in_booking, name='medical-check-in'),
    path('screening/', submit_screening_result, name='medical-screening'),
    path('inject/', submit_vaccination_log, name='medical-inject'),
    path('monitor/', submit_post_injection_tracking, name='medical-monitor'),
    path('walkin/', walkin_checkin, name='medical-walkin'),
    path('<int:booking_id>/reschedule/', reschedule_booking, name='medical-reschedule'),
]
