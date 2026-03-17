from django.http import JsonResponse
from django.urls import path


def auth_home(request):
    return JsonResponse({'module': 'authentication', 'message': 'authentication module is running'})


urlpatterns = [path('', auth_home)]
