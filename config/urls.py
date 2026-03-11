from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home(request):
    return JsonResponse({
        "message": "vaccin-manage-system backend is running"
    })


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),

    path("assets/", include("feature.assets.urls")),
    path("auth/", include("feature.authentication.urls")),
    path("booking/", include("feature.booking.urls")),
    path("users/", include("feature.users.urls")),
]