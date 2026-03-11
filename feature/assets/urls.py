from django.http import JsonResponse
from django.urls import path


def assets_home(request):
    return JsonResponse({
        "module": "assets",
        "message": "assets module is running"
    })


urlpatterns = [
    path("", assets_home),
]