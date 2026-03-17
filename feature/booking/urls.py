
from django.urls import path
from .views import booking_page, create_booking

urlpatterns = [
    path("", booking_page, name="booking_page"),
    path("create/", create_booking, name="create_booking"),
from .views import booking_list_create, booking_test

urlpatterns = [
    path("test/", booking_test, name="booking-test"),
    path("", booking_list_create, name="booking-list-create"),
]
from django.urls import path
from .views import booking_detail, booking_list_create, booking_test

urlpatterns = [
    path('test/', booking_test, name='booking-test'),
    path('', booking_list_create, name='booking-list-create'),
    path('<int:booking_id>/', booking_detail, name='booking-detail'),
]