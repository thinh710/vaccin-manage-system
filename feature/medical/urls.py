from django.urls import path
from .views import medical_record_detail, medical_record_list_create, medical_test

urlpatterns = [
    path('test/', medical_test, name='medical-test'),
    path('', medical_record_list_create, name='medical-record-list-create'),
    path('<int:medical_id>/', medical_record_detail, name='medical-record-detail'),
]
