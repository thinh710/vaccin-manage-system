from django.urls import path

from .views import (
    facebook_login_callback,
    facebook_login_start,
    google_login_callback,
    google_login_start,
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
    path('social/google/start/', google_login_start, name='google-login-start'),
    path('social/google/callback/', google_login_callback, name='google-login-callback'),
    path('social/facebook/start/', facebook_login_start, name='facebook-login-start'),
    path('social/facebook/callback/', facebook_login_callback, name='facebook-login-callback'),
]
