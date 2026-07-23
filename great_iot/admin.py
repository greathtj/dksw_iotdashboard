from django.contrib import admin
from .models import Sensor, LLMServer, SensorAIConfig, AnalysisReport

@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_name', 'board_type', 'attached_sensor', 'owner', 'created_at')
    list_filter = ('board_type', 'attached_sensor', 'owner')
    search_fields = ('name', 'measurement_name', 'api_key')
    readonly_fields = ('api_key', 'created_at')

@admin.register(LLMServer)
class LLMServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'default_model', 'created_by', 'created_at')
    list_filter = ('created_by',)
    search_fields = ('name', 'url')

@admin.register(SensorAIConfig)
class SensorAIConfigAdmin(admin.ModelAdmin):
    list_display = ('user', 'sensor', 'server_url', 'model_name', 'notes', 'updated_at')
    list_filter = ('user',)
    search_fields = ('user__username', 'sensor__name')

@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'sensor', 'model_name', 'time_range')
    list_filter = ('user', 'sensor', 'model_name')
    search_fields = ('user__username', 'sensor__name')
    readonly_fields = ('created_at',)
