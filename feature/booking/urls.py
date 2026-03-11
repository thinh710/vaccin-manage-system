from django.http import JsonResponse
from django.urls import path


def booking_home(request):
    user_id = request.GET.get("user_id")

    return JsonResponse({
        "module": "booking",
        "message": "booking module is running",
        "user_id": user_id,
    })


urlpatterns = [
    path("", booking_home),
]