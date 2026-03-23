from django.urls import path
from .views import dashboard, profile

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('profile/', profile, name='profile'),
]
