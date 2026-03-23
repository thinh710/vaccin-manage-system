from django.urls import path

from .views import (
    login_page,
    login_view,
    logout_view,
    me_view,
    register_page,
    register_view,
)

urlpatterns = [
    path('login-page/', login_page, name='login-page'),
    path('register-page/', register_page, name='register-page'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('me/', me_view, name='me'),
]
