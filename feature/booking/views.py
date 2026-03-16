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