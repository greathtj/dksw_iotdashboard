from django.urls import path
from . import views

app_name = 'great_iot'

urlpatterns = [
    path('', views.iot_dashboard, name='iot_dashboard'),
    path('register/', views.register_sensor, name='register_sensor'),
    path('delete/<int:sensor_id>/', views.delete_sensor, name='delete_sensor'),
    path('sensor/<int:sensor_id>/', views.sensor_detail, name='sensor_detail'),
    path('api/generate-firmware/<int:sensor_id>/', views.generate_firmware, name='generate_firmware'),
    path('api/data/', views.iot_data, name='iot_data'),
    path('api/ingest/', views.ingest_data, name='ingest_data'),
    path('sensor/<int:sensor_id>/purge/', views.purge_sensor_data, name='purge_sensor_data'),
    path('sensor/<int:sensor_id>/ai-analysis/', views.ai_analysis, name='ai_analysis'),
    path('ai/server/add/', views.add_llm_server, name='add_llm_server'),
    path('ai/server/<int:server_id>/delete/', views.delete_llm_server, name='delete_llm_server'),
    path('ai/server/check/', views.check_llm_server, name='check_llm_server'),
    path('ai/report/<int:report_id>/load/', views.load_report, name='load_report'),
]
