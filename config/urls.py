from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles import views as staticfiles_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import redirect
from django.urls import include, path, re_path


def home(request):
    return redirect('/auth/login-page/')


urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    re_path(r'^static/(?P<path>.*)$', staticfiles_views.serve, {'insecure': True}),
    path('assets/', include('feature.assets.urls')),
    path('auth/', include('feature.authentication.urls')),
    path('booking/', include('feature.booking.urls')),
    path('users/', include('feature.users.urls')),
    path('medical/', include('feature.medical.urls')),
    path('api/medical/', include('feature.medical.urls')),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
