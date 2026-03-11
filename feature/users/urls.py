from django.http import JsonResponse
from django.urls import path


def users_home(request):
    return JsonResponse({
        "module": "users",
        "message": "users module is running"
    })


urlpatterns = [
    path("", users_home),
]