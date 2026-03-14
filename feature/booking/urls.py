from django.urls import path
<<<<<<< HEAD
from .views import booking_page, create_booking

urlpatterns = [
    path("", booking_page, name="booking_page"),
    path("create/", create_booking, name="create_booking"),
=======
from .views import booking_list_create, booking_test

urlpatterns = [
    path("test/", booking_test, name="booking-test"),
    path("", booking_list_create, name="booking-list-create"),
>>>>>>> fdbb98c (Add files via upload)
]