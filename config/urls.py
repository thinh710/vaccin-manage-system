from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def home(request):
    return redirect('/auth/login-page/')


urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('assets/', include('feature.assets.urls')),
    path('auth/', include('feature.authentication.urls')),
    path('booking/', include('feature.booking.urls')),
    path('users/', include('feature.users.urls')),
    path('medical/', include('feature.medical.urls')),
]
