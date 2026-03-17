from django.http import HttpRequest
from django.shortcuts import redirect, render

from feature.authentication.models import User


def dashboard(request: HttpRequest):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('/auth/login-page/')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return redirect('/auth/login-page/')

    if user.role != User.ROLE_CITIZEN:
        return redirect('/auth/login-page/')

    return render(request, 'users/dashboard.html', {'user': user})
