from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingSerializer


@api_view(['GET', 'POST'])
def booking_list_create(request):
    if request.method == 'GET':
        queryset = Booking.objects.all()
        keyword = request.GET.get('q')
        booking_status = request.GET.get('status')

        if keyword:
            queryset = queryset.filter(full_name__icontains=keyword)
        if booking_status:
            queryset = queryset.filter(status=booking_status)

        return Response(BookingSerializer(queryset, many=True).data)

    serializer = BookingSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
def booking_detail(request, booking_id):
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(BookingSerializer(booking).data)

    if request.method == 'PATCH':
        serializer = BookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    booking.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def booking_test(request):
    return Response({'message': 'Booking API is working'})
