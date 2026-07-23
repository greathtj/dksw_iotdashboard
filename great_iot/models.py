from django.db import models
from django.contrib.auth.models import User
import uuid

class LLMServer(models.Model):
    name = models.CharField(max_length=100, verbose_name="LLM 서버 이름")
    url = models.URLField(max_length=500, verbose_name="서버 URL", help_text="OpenAI 호환 API 엔드포인트 (예: http://192.168.0.100:11434/v1)")
    api_key = models.CharField(max_length=500, blank=True, verbose_name="API 키", help_text="필요한 경우 API 키 입력 (Ollama는 비워둠)")
    default_model = models.CharField(max_length=100, default='gemma3:12b', verbose_name="기본 모델")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='llm_servers')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.url})"

    class Meta:
        verbose_name = "LLM 서버"
        verbose_name_plural = "LLM 서버 목록"

class AnalysisReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analysis_reports')
    sensor = models.ForeignKey('Sensor', on_delete=models.CASCADE, related_name='analysis_reports')
    server_url = models.URLField(max_length=500, blank=True, default='')
    model_name = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    time_range = models.CharField(max_length=10, blank=True, default='')
    result = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '분석 리포트'
        verbose_name_plural = '분석 리포트 목록'

    def __str__(self):
        return f'[{self.created_at:%Y-%m-%d %H:%M}] {self.sensor.name} ({self.time_range})'

class SensorAIConfig(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sensor_ai_configs')
    sensor = models.ForeignKey('Sensor', on_delete=models.CASCADE, related_name='ai_configs')
    server_url = models.URLField(max_length=500, blank=True, default='')
    model_name = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='', verbose_name='분석 주의사항')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'sensor')
        verbose_name = 'AI 분석 설정'
        verbose_name_plural = 'AI 분석 설정 목록'

    def __str__(self):
        return f'{self.user.username}/{self.sensor.name} AI 설정'

class Sensor(models.Model):
    BOARD_CHOICES = [
        ('esp32', 'ESP32'),
        ('esp32c3_supermini', 'ESP32-C3 SuperMini'),
        ('arduino_esp01', 'Arduino with ESP-01'),
    ]

    SENSOR_HARDWARE_CHOICES = [
        ('custom', '사용자 정의 / 기타'),
        ('dht11', 'DHT11 (온도 및 습도)'),
        ('timer', '타이머 (시작, 종료, 현재, 경과, 남은 시간)'),
        ('MPU6050_vib', 'MPU6050 진동 (x, y, z)'),
        ('bme280', 'BME280 (온도, 습도, 기압)'),
        ('bh1750', 'BH1750 (조도)'),
        ('aht10', 'AHT10 (온도 및 습도)'),
        ('mSensor01', '복합 센서 (Vib, Temp, Hum, Sound)'),
    ]

    name = models.CharField(max_length=100, verbose_name="센서 이름")
    measurement_name = models.CharField(max_length=100, help_text="InfluxDB에서 사용될 측정 항목 이름 (예: IoT_Edu_Float)", verbose_name="데이터 식별자 (Measurement)")
    board_type = models.CharField(max_length=50, choices=BOARD_CHOICES, default='esp32', verbose_name="보드 종류")
    attached_sensor = models.CharField(max_length=50, choices=SENSOR_HARDWARE_CHOICES, default='custom', verbose_name="연결된 센서")
    data_fields = models.CharField(max_length=255, default='temperature', help_text="수집할 데이터 필드 목록 (쉼표로 구분, 예: temperature,humidity)", verbose_name="데이터 필드")
    description = models.TextField(blank=True, verbose_name="상세 설명")
    api_key = models.CharField(max_length=36, default=uuid.uuid4, unique=True, editable=False, verbose_name="API 키")
    latest_data = models.TextField(default='{}', help_text="센서로부터 수신된 최신 데이터 (JSON 형식)", verbose_name="최신 수집 데이터")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록 일시")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sensors', verbose_name="소유자")

    def __str__(self):
        return f"{self.name} ({self.measurement_name}) - {self.get_board_type_display()}"
