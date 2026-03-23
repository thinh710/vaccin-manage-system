from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpRequest
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


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
        return Response({'email': ['Email đã tồn tại.']}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create(
        full_name=full_name,
        email=email,
        password_hash=make_password(password),
        role=role,
        status='active',
    )
    request.session['user_id'] = user.id

    return Response(
        {
            'message': 'Đăng ký thành công.',
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
        return Response({'detail': 'Email hoặc mật khẩu không đúng.'}, status=status.HTTP_401_UNAUTHORIZED)

    if user.status != 'active':
        return Response({'detail': 'Tài khoản chưa sẵn sàng để đăng nhập.'}, status=status.HTTP_403_FORBIDDEN)

    if not check_password(password, user.password_hash):
        return Response({'detail': 'Email hoặc mật khẩu không đúng.'}, status=status.HTTP_401_UNAUTHORIZED)

    request.session['user_id'] = user.id
    return Response({'message': 'Đăng nhập thành công.', 'user': UserSerializer(user).data})


@api_view(['POST'])
def logout_view(request):
    request.session.flush()
    return Response({'message': 'Đăng xuất thành công.'})


@api_view(['GET'])
def me_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return Response({'detail': 'Bạn chưa đăng nhập.'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return Response({'detail': 'Phiên đăng nhập không hợp lệ.'}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(UserSerializer(user).data)
