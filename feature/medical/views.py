from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import MedicalRecord
from .serializers import MedicalRecordSerializer


@api_view(['GET', 'POST'])
def medical_record_list_create(request):
    if request.method == 'GET':
        queryset = MedicalRecord.objects.select_related('booking').all().order_by('-id')
        booking_id = request.GET.get('booking_id')
        fit = request.GET.get('fit')

        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        if fit in {'true', 'false'}:
            queryset = queryset.filter(is_fit_for_vaccination=(fit == 'true'))

        return Response(MedicalRecordSerializer(queryset, many=True).data)

    serializer = MedicalRecordSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
def medical_record_detail(request, medical_id):
    try:
        record = MedicalRecord.objects.select_related('booking').get(pk=medical_id)
    except MedicalRecord.DoesNotExist:
        return Response({'detail': 'Medical record not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(MedicalRecordSerializer(record).data)

    if request.method == 'PATCH':
        serializer = MedicalRecordSerializer(record, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    record.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def medical_test(request):
    return Response({'message': 'Medical API is working'})
