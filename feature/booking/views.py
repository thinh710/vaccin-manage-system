
from django.shortcuts import render, redirect
from .models import Booking


def booking_page(request):
    bookings = Booking.objects.all().order_by("-created_at")
    pending_count = Booking.objects.filter(status="pending").count()
    confirmed_count = Booking.objects.filter(status="confirmed").count()

    return render(request, "booking.html", {
        "bookings": bookings,
        "pending_count": pending_count,
        "confirmed_count": confirmed_count,
    })


def create_booking(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        vaccine_date = request.POST.get("vaccine_date", "").strip()
        note = request.POST.get("note", "").strip()
        status = request.POST.get("status", "pending").strip()

        if not full_name or not phone or not vaccine_date:
            bookings = Booking.objects.all().order_by("-created_at")
            pending_count = Booking.objects.filter(status="pending").count()
            confirmed_count = Booking.objects.filter(status="confirmed").count()

            return render(request, "booking.html", {
                "bookings": bookings,
                "pending_count": pending_count,
                "confirmed_count": confirmed_count,
                "error": "Vui lòng nhập đầy đủ họ tên, số điện thoại và ngày tiêm."
            })

        Booking.objects.create(
            full_name=full_name,
            phone=phone,
            vaccine_date=vaccine_date,
            note=note,
            status=status,
        )

        return redirect("booking_page")

    return redirect("booking_page")
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
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingSerializer


@api_view(['GET', 'POST'])
def booking_list_create(request):
    if request.method == 'GET':
        queryset = Booking.objects.all()
        keyword = request.GET.get('q')
        booking_status = request.GET.get('status')

        if keyword:
            queryset = queryset.filter(full_name__icontains=keyword)
        if booking_status:
            queryset = queryset.filter(status=booking_status)

        return Response(BookingSerializer(queryset, many=True).data)

    serializer = BookingSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
def booking_detail(request, booking_id):
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(BookingSerializer(booking).data)

    if request.method == 'PATCH':
        serializer = BookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    booking.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def booking_test(request):
    return Response({'message': 'Booking API is working'})