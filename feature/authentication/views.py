import json
import os
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
FACEBOOK_AUTH_URL = 'https://www.facebook.com/v19.0/dialog/oauth'
FACEBOOK_TOKEN_URL = 'https://graph.facebook.com/v19.0/oauth/access_token'
FACEBOOK_USERINFO_URL = 'https://graph.facebook.com/me'


def _build_login_page_redirect(message: str):
    query = urlencode({'social_error': message})
    return redirect(f"{reverse('login-page')}?{query}")


def _build_redirect_uri(request: HttpRequest, env_name: str, route_name: str) -> str:
    configured_uri = os.getenv(env_name, '').strip()
    if configured_uri:
        return configured_uri
    return request.build_absolute_uri(reverse(route_name))


def _oauth_json_request(url: str, method: str = 'GET', data: dict | None = None, headers: dict | None = None):
    request_headers = {'Accept': 'application/json'}
    if headers:
        request_headers.update(headers)

    payload = None
    if data is not None:
        payload = urlencode(data).encode('utf-8')
        request_headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')

    request_object = Request(url, data=payload, headers=request_headers, method=method)
    with urlopen(request_object, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def _fetch_json_or_raise(url: str, method: str = 'GET', data: dict | None = None, headers: dict | None = None):
    try:
        return _oauth_json_request(url, method=method, data=data, headers=headers)
    except HTTPError as error:
        error_body = error.read().decode('utf-8', errors='ignore')
        raise ValueError(error_body or 'OAuth provider rejected the request.') from error
    except URLError as error:
        raise ValueError(str(error.reason) or 'OAuth provider is unreachable.') from error


def _start_social_flow(
    request: HttpRequest,
    provider: str,
    client_id_env: str,
    redirect_uri_env: str,
    route_name: str,
):
    client_id = os.getenv(client_id_env, '').strip()
    if not client_id:
        return _build_login_page_redirect(
            f'Ban can cau hinh {client_id_env} trong file .env truoc khi dang nhap bang {provider}.'
        )

    state = secrets.token_urlsafe(24)
    request.session[f'oauth_state_{provider}'] = state
    redirect_uri = _build_redirect_uri(request, redirect_uri_env, route_name)

    if provider == User.AUTH_PROVIDER_GOOGLE:
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'online',
            'prompt': 'select_account',
        }
        return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(params)}')

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'email,public_profile',
        'state': state,
    }
    return redirect(f'{FACEBOOK_AUTH_URL}?{urlencode(params)}')


def _get_or_create_social_user(
    *,
    email: str,
    full_name: str,
    provider: str,
    provider_user_id: str,
    avatar_url: str = '',
):
    normalized_email = email.strip().lower()
    user = User.objects.filter(email=normalized_email).first()

    if user and user.role != User.ROLE_CITIZEN:
        raise ValueError('Tai khoan nay dang thuoc nhom admin/staff va khong duoc dang nhap qua mang xa hoi.')

    if user:
        if user.status != User.STATUS_ACTIVE:
            raise ValueError('Tai khoan nay chua san sang de dang nhap.')
        if not user.full_name and full_name:
            user.full_name = full_name
        if avatar_url and not user.avatar_data:
            user.avatar_data = avatar_url
        user.auth_provider = provider
        user.provider_user_id = provider_user_id
        user.role = User.ROLE_CITIZEN
        user.save(update_fields=['full_name', 'avatar_data', 'auth_provider', 'provider_user_id', 'role', 'updated_at'])
        return user

    return User.objects.create(
        full_name=full_name or normalized_email.split('@')[0],
        email=normalized_email,
        password_hash=make_password(secrets.token_urlsafe(32)),
        avatar_data=avatar_url,
        auth_provider=provider,
        provider_user_id=provider_user_id,
        role=User.ROLE_CITIZEN,
        status=User.STATUS_ACTIVE,
    )


def _complete_social_login(
    request: HttpRequest,
    *,
    provider: str,
    provider_user_id: str,
    email: str,
    full_name: str,
    avatar_url: str = '',
):
    if not email:
        raise ValueError('Tai khoan mang xa hoi nay chua tra ve email, khong the tao user.')

    user = _get_or_create_social_user(
        email=email,
        full_name=full_name,
        provider=provider,
        provider_user_id=provider_user_id,
        avatar_url=avatar_url,
    )
    request.session['user_id'] = user.id
    return redirect('/users/dashboard/')


@api_view(['GET'])
def login_page(request: HttpRequest):
    return render(request, 'authentication/login.html')


@api_view(['GET'])
def register_page(request: HttpRequest):
    return render(request, 'authentication/register.html')


@api_view(['POST'])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    full_name = serializer.validated_data['full_name']
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    role = serializer.validated_data.get('role', User.ROLE_CITIZEN)

    if User.objects.filter(email=email).exists():
        return Response({'email': ['Email da ton tai.']}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create(
        full_name=full_name,
        email=email,
        password_hash=make_password(password),
        role=role,
        status=User.STATUS_ACTIVE,
        auth_provider=User.AUTH_PROVIDER_LOCAL,
    )
    request.session['user_id'] = user.id

    return Response(
        {
            'message': 'Dang ky thanh cong.',
            'user': UserSerializer(user).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data['email']
    password = serializer.validated_data['password']

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'detail': 'Email hoac mat khau khong dung.'}, status=status.HTTP_401_UNAUTHORIZED)

    if user.status != User.STATUS_ACTIVE:
        return Response({'detail': 'Tai khoan chua san sang de dang nhap.'}, status=status.HTTP_403_FORBIDDEN)

    if not check_password(password, user.password_hash):
        return Response({'detail': 'Email hoac mat khau khong dung.'}, status=status.HTTP_401_UNAUTHORIZED)

    request.session['user_id'] = user.id
    return Response({'message': 'Dang nhap thanh cong.', 'user': UserSerializer(user).data})


@api_view(['POST'])
def logout_view(request):
    request.session.flush()
    return Response({'message': 'Dang xuat thanh cong.'})


@api_view(['GET'])
def me_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return Response({'detail': 'Ban chua dang nhap.'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return Response({'detail': 'Phien dang nhap khong hop le.'}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(UserSerializer(user).data)


@api_view(['GET'])
def google_login_start(request: HttpRequest):
    return _start_social_flow(
        request,
        provider=User.AUTH_PROVIDER_GOOGLE,
        client_id_env='GOOGLE_CLIENT_ID',
        redirect_uri_env='GOOGLE_REDIRECT_URI',
        route_name='google-login-callback',
    )


@api_view(['GET'])
def facebook_login_start(request: HttpRequest):
    return _start_social_flow(
        request,
        provider=User.AUTH_PROVIDER_FACEBOOK,
        client_id_env='FACEBOOK_APP_ID',
        redirect_uri_env='FACEBOOK_REDIRECT_URI',
        route_name='facebook-login-callback',
    )


@api_view(['GET'])
def google_login_callback(request: HttpRequest):
    error_message = request.GET.get('error')
    if error_message:
        return _build_login_page_redirect('Dang nhap Google da bi huy.')

    expected_state = request.session.pop('oauth_state_google', '')
    if not expected_state or expected_state != request.GET.get('state'):
        return _build_login_page_redirect('Phien dang nhap Google khong hop le.')

    code = request.GET.get('code', '').strip()
    if not code:
        return _build_login_page_redirect('Google khong tra ve ma xac thuc.')

    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        return _build_login_page_redirect('Ban can cau hinh GOOGLE_CLIENT_ID va GOOGLE_CLIENT_SECRET trong file .env.')

    redirect_uri = _build_redirect_uri(request, 'GOOGLE_REDIRECT_URI', 'google-login-callback')

    try:
        token_data = _fetch_json_or_raise(
            GOOGLE_TOKEN_URL,
            method='POST',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
        )
        user_info = _fetch_json_or_raise(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f"Bearer {token_data['access_token']}"},
        )
        return _complete_social_login(
            request,
            provider=User.AUTH_PROVIDER_GOOGLE,
            provider_user_id=str(user_info.get('sub', '')),
            email=user_info.get('email', ''),
            full_name=user_info.get('name', ''),
            avatar_url=user_info.get('picture', ''),
        )
    except (KeyError, ValueError) as error:
        return _build_login_page_redirect(f'Dang nhap Google that bai: {error}')


@api_view(['GET'])
def facebook_login_callback(request: HttpRequest):
    error_message = request.GET.get('error') or request.GET.get('error_reason')
    if error_message:
        return _build_login_page_redirect('Dang nhap Facebook da bi huy.')

    expected_state = request.session.pop('oauth_state_facebook', '')
    if not expected_state or expected_state != request.GET.get('state'):
        return _build_login_page_redirect('Phien dang nhap Facebook khong hop le.')

    code = request.GET.get('code', '').strip()
    if not code:
        return _build_login_page_redirect('Facebook khong tra ve ma xac thuc.')

    app_id = os.getenv('FACEBOOK_APP_ID', '').strip()
    app_secret = os.getenv('FACEBOOK_APP_SECRET', '').strip()
    if not app_id or not app_secret:
        return _build_login_page_redirect('Ban can cau hinh FACEBOOK_APP_ID va FACEBOOK_APP_SECRET trong file .env.')

    redirect_uri = _build_redirect_uri(request, 'FACEBOOK_REDIRECT_URI', 'facebook-login-callback')

    try:
        token_data = _fetch_json_or_raise(
            FACEBOOK_TOKEN_URL,
            data={
                'client_id': app_id,
                'client_secret': app_secret,
                'redirect_uri': redirect_uri,
                'code': code,
            },
        )
        user_info = _fetch_json_or_raise(
            f"{FACEBOOK_USERINFO_URL}?{urlencode({'fields': 'id,name,email,picture.type(large)', 'access_token': token_data['access_token']})}"
        )
        picture_data = user_info.get('picture', {}).get('data', {})
        return _complete_social_login(
            request,
            provider=User.AUTH_PROVIDER_FACEBOOK,
            provider_user_id=str(user_info.get('id', '')),
            email=user_info.get('email', ''),
            full_name=user_info.get('name', ''),
            avatar_url=picture_data.get('url', ''),
        )
    except (KeyError, ValueError) as error:
        return _build_login_page_redirect(f'Dang nhap Facebook that bai: {error}')
