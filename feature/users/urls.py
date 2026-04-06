from django.urls import path
from .views import (
    dashboard,
    profile,
    screening_portal,
    vaccine_packages,
    vaccination_knowledge,
    vaccination_system,
)

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('profile/', profile, name='profile'),
    path('screening/', screening_portal, name='screening-portal'),
    path('packages/', vaccine_packages, name='vaccine-packages'),
    path('system/', vaccination_system, name='vaccination-system'),
    path('knowledge/', vaccination_knowledge, name='vaccination-knowledge'),
]
