from django.urls import path
from .views import booking_detail, booking_list_create, booking_portal, booking_test

urlpatterns = [
    path('portal/', booking_portal, name='booking-portal'),
    path('test/', booking_test, name='booking-test'),
    path('', booking_list_create, name='booking-list-create'),
    path('<int:booking_id>/', booking_detail, name='booking-detail'),
]
