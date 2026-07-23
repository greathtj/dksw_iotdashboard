from django import forms
from .models import Sensor

SENSOR_TYPE_CHOICES = [
    ('mSensor00_complex', '복합센서_00 (ESP32-30pin + 진동, 소음, 온습도_기압)'),
    ('mSensor01_complex', '복합센서_01 (ESP32-c3 supermini + 진동, 소음, 온습도_기압)'),
    ('aht10_arduino_uno', 'AHT10(온습도) + 아두이노 Uno + ESP01'),
]

SENSOR_TYPE_MAPPING = {
    'dht11_basic': {
        'measurement_name': 'IoT_Edu_Float',
        'board_type': 'esp32',
        'attached_sensor': 'dht11',
        'data_fields': 'temperature, humidity',
    },
    'bme280_basic': {
        'measurement_name': 'IoT_Edu_Float',
        'board_type': 'esp32',
        'attached_sensor': 'bme280',
        'data_fields': 'temperature, humidity, pressure',
    },
    'bh1750_basic': {
        'measurement_name': 'IoT_Edu_Float',
        'board_type': 'esp32',
        'attached_sensor': 'bh1750',
        'data_fields': 'light',
    },
    'aht10_basic': {
        'measurement_name': 'IoT_Edu_Float',
        'board_type': 'esp32',
        'attached_sensor': 'aht10',
        'data_fields': 'temperature, humidity',
    },
    'mpu6050_vib': {
        'measurement_name': 'IoT_Edu_Float',
        'board_type': 'esp32',
        'attached_sensor': 'MPU6050_vib',
        'data_fields': 'accel_x, accel_y, accel_z',
    },
    'timer_basic': {
        'measurement_name': 'IoT_Timer',
        'board_type': 'esp32',
        'attached_sensor': 'timer',
        'data_fields': 'start_time, end_time, current_time, elapsed_time, time_left',
    },
    'mSensor00_complex': {
        'measurement_name': 'mSensor00',
        'board_type': 'esp32',
        'attached_sensor': 'mSensor01',
        'data_fields': 'fX, fY, fZ, vX, vY, vZ, sDb, temperature, humidity, pressure',
    },
    'mSensor01_complex': {
        'measurement_name': 'mSensor01',
        'board_type': 'esp32c3_supermini',
        'attached_sensor': 'mSensor01',
        'data_fields': 'fX, fY, fZ, vX, vY, vZ, sDb, temperature, humidity, pressure',
    },
    'aht10_arduino_uno': {
        'measurement_name': 'IoT_Edu_Float',
        'board_type': 'arduino_esp01',
        'attached_sensor': 'aht10',
        'data_fields': 'temperature, humidity',
    },
}

class SensorForm(forms.ModelForm):
    sensor_type = forms.ChoiceField(
        choices=SENSOR_TYPE_CHOICES,
        label="센서종류",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    description = forms.CharField(
        required=False,
        label="상세설명 (선택사항)",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '센서에 대한 상세 설명을 입력하세요...'})
    )

    class Meta:
        model = Sensor
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 1층 현관 복합센서'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        sensor_type = cleaned_data.get('sensor_type')
        if sensor_type and sensor_type in SENSOR_TYPE_MAPPING:
            mapping = SENSOR_TYPE_MAPPING[sensor_type]
            cleaned_data['measurement_name'] = mapping['measurement_name']
            cleaned_data['board_type'] = mapping['board_type']
            cleaned_data['attached_sensor'] = mapping['attached_sensor']
            cleaned_data['data_fields'] = mapping['data_fields']
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        for field in ['measurement_name', 'board_type', 'attached_sensor', 'data_fields']:
            if field in self.cleaned_data:
                setattr(instance, field, self.cleaned_data[field])
        if commit:
            instance.save()
        return instance
