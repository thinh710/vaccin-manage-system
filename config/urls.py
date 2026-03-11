#file định nghĩa url của project

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/booking/", include("booking.urls")),
    path("api/identity/", include("identity.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/medical/", include("medical.urls")),
]