from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Booking
from .serializers import BookingSerializer


@api_view(["GET", "POST"])
def booking_list_create(request):
    if request.method == "GET":
        bookings = Booking.objects.all().order_by("-id")
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    serializer = BookingSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def booking_test(request):
    return Response({"message": "Booking API is working"})