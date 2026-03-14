from django.urls import path
from .views import booking_list_create, booking_test

urlpatterns = [
    path("test/", booking_test, name="booking-test"),
    path("", booking_list_create, name="booking-list-create"),
]