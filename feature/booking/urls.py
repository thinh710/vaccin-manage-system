from django.urls import path

from .views import (
    booking_detail,
    booking_list_create,
    booking_portal,
    booking_test,
    confirm_booking_deposit,
    confirm_booking_eligibility,
)

urlpatterns = [
    path('portal/', booking_portal, name='booking-portal'),
    path('test/', booking_test, name='booking-test'),
    path('', booking_list_create, name='booking-list-create'),
    path('<int:booking_id>/', booking_detail, name='booking-detail'),
    path('<int:booking_id>/doctor-review/', confirm_booking_eligibility, name='booking-doctor-review'),
    path('<int:booking_id>/eligibility/', confirm_booking_eligibility, name='booking-confirm-eligibility'),
    path('<int:booking_id>/deposit/', confirm_booking_deposit, name='booking-confirm-deposit'),
]
