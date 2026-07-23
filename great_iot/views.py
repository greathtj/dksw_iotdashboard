from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from django.conf import settings
from .forms import SensorForm
from .models import Sensor, LLMServer, SensorAIConfig, AnalysisReport
from .firmware_templates import *
import urllib.request
import urllib.error

try:
    from .influxdb import InfluxDBConnection
except ImportError:
    InfluxDBConnection = None

try:
    from development.utils import compile_sketch
except ImportError:
    compile_sketch = None



@login_required
def iot_dashboard(request):
    sensors = Sensor.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'great_iot/iot_dashboard.html', {'sensors': sensors})

@login_required
def register_sensor(request):
    if request.method == 'POST':
        form = SensorForm(request.POST)
        if form.is_valid():
            sensor = form.save(commit=False)
            sensor.owner = request.user
            sensor.save()
            messages.success(request, f"센서 '{sensor.name}'가 성공적으로 등록되었습니다!")
            return redirect('great_iot:iot_dashboard')
    else:
        form = SensorForm()

    return render(request, 'great_iot/register_sensor.html', {'form': form})

@login_required
def delete_sensor(request, sensor_id):
    sensor = get_object_or_404(Sensor, id=sensor_id, owner=request.user)
    if request.method == 'POST':
        name = sensor.name

        if InfluxDBConnection is not None:
            try:
                influx_conn = InfluxDBConnection()
                tags = {
                    'sensor_name': sensor.name,
                    'owner_id': str(sensor.owner.id)
                }
                influx_conn.delete_data(sensor.measurement_name, tags=tags)
                influx_conn.close()
            except Exception as e:
                print(f"Error deleting sensor data: {e}")
                messages.warning(request, f"센서 정보는 삭제되었으나, InfluxDB에서 데이터를 삭제하는 중 오류가 발생했습니다: {e}")

        sensor.delete()
        messages.success(request, f"센서 '{name}' 및 관련 데이터가 성공적으로 삭제되었습니다.")
    return redirect('great_iot:iot_dashboard')

@login_required
def sensor_detail(request, sensor_id):
    sensor = get_object_or_404(Sensor, id=sensor_id, owner=request.user)

    latest_data = {}
    if sensor.attached_sensor == 'timer':
        try:
            latest_data = json.loads(sensor.latest_data)
        except Exception as e:
            print(f"Error parsing latest_data for timer: {e}")
    else:
        if InfluxDBConnection is not None:
            try:
                influx_conn = InfluxDBConnection()
                latest_data = influx_conn.get_latest_data(sensor.measurement_name, tags={'sensor_name': sensor.name})
                influx_conn.close()
            except Exception as e:
                print(f"Error fetching latest data: {e}")
                messages.warning(request, "InfluxDB에서 최신 실시간 데이터를 가져올 수 없습니다.")

    FIELD_LABELS = {
        'bh1750': {'light': '조도 (lux)'},
        'dht11': {'temperature': '온도 (°C)', 'humidity': '습도 (%)'},
        'aht10': {'temperature': '온도 (°C)', 'humidity': '습도 (%)'},
        'bme280': {'temperature': '온도 (°C)', 'humidity': '습도 (%)', 'pressure': '기압 (hPa)'},
        'MPU6050_vib': {'accel_x': 'X축 진동', 'accel_y': 'Y축 진동', 'accel_z': 'Z축 진동'},
        'timer': {'start_time': '시작 시간', 'current_time': '현재 시간', 'elapsed_time': '경과 시간', 'elapsed_left': '남은 시간'},
        'mSensor01': {
            'fX': 'X축 진동 주파수 (Hz)', 'fY': 'Y축 진동 주파수 (Hz)', 'fZ': 'Z축 진동 주파수 (Hz)',
            'vX': 'X축 진동 속도', 'vY': 'Y축 진동 속도', 'vZ': 'Z축 진동 속도',
            'sDb': '소음 (dB)', 'temperature': '온도 (°C)', 'humidity': '습도 (%)', 'pressure': '기압 (hPa)'
        },
    }

    sensor_field_labels = FIELD_LABELS.get(sensor.attached_sensor, {})

    latest_data_with_labels = {}
    for field, value in latest_data.items():
        label = sensor_field_labels.get(field, field.replace('_', ' ').upper())
        latest_data_with_labels[field] = {'value': value, 'label': label}

    influx_url = settings.INFLUXDB_SETTINGS['url'].rstrip('/')
    default_server_url = f"{influx_url}/iot/api/ingest/"

    BOARD_COMPILE_CONFIG = {
        'esp32': {
            'fqbn': 'esp32:esp32:esp32',
            'flash_size': '4MB',
            'flash_mode': 'DIO',
            'cdc_on_boot': 'N/A',
            'partition_scheme': 'Default',
        },
        'esp32c3_supermini': {
            'fqbn': 'esp32:esp32:esp32c3',
            'flash_size': '4MB',
            'flash_mode': 'DIO',
            'cdc_on_boot': 'Enabled',
            'partition_scheme': 'Default',
        },
        'arduino_esp01': {
            'fqbn': 'arduino:avr:uno',
            'flash_size': 'N/A',
            'flash_mode': 'N/A',
            'cdc_on_boot': 'N/A',
            'partition_scheme': 'N/A',
        },
    }
    board_config = BOARD_COMPILE_CONFIG.get(sensor.board_type, {})

    field_labels_json = json.dumps(sensor_field_labels)

    return render(request, 'great_iot/sensor_detail.html', {
        'sensor': sensor,
        'latest_data': latest_data_with_labels,
        'default_server_url': default_server_url,
        'field_labels_json': field_labels_json,
        'board_config': board_config,
    })

@csrf_exempt
def ingest_data(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            api_key = payload.get('api_key')
            data = payload.get('data')

            if not api_key or not data:
                return JsonResponse({'success': False, 'error': 'api_key 또는 data가 누락되었습니다.'}, status=400)

            try:
                print(f"DEBUG: Ingesting data for API Key: {api_key}")
                sensor = Sensor.objects.get(api_key=api_key)
                print(f"DEBUG: Found sensor: {sensor.name} (ID: {sensor.id})")
            except Sensor.DoesNotExist:
                print(f"DEBUG: Sensor NOT FOUND for API Key: {api_key}")
                all_keys = list(Sensor.objects.values_list('api_key', flat=True))
                return JsonResponse({
                    'success': False, 
                    'error': f'유효하지 않은 API 키입니다. (수신된 키: {api_key[:8]}..., 서버 보유 키 개수: {len(all_keys)})',
                    'debug_keys': all_keys
                }, status=401)

            if sensor.attached_sensor == 'timer':
                sensor.latest_data = json.dumps(data)
                sensor.save(update_fields=['latest_data'])
                return JsonResponse({'success': True, 'message': '타이머 데이터가 성공적으로 업데이트되었습니다.'})

            if InfluxDBConnection is None:
                return JsonResponse({'success': False, 'error': 'InfluxDB가 설정되지 않았습니다. timeseries 앱이 필요합니다.'}, status=500)

            influx_conn = InfluxDBConnection()
            try:
                tags = {
                    'sensor_name': sensor.name,
                    'owner_id': str(sensor.owner.id)
                }

                processed_points = []
                data_list = data if isinstance(data, list) else [data]

                for i, d in enumerate(data_list):
                    processed_data = {}
                    timestamp = d.pop('timestamp', None)
                    
                    for key, value in d.items():
                        if isinstance(value, (int, float)):
                            processed_data[key] = float(value)
                        else:
                            processed_data[key] = value
                    
                    influx_conn.write_point(sensor.measurement_name, tags, processed_data, timestamp=timestamp)
                    processed_points.append(processed_data)

                sensor.latest_data = json.dumps(processed_points[-1])
                sensor.save(update_fields=['latest_data'])

                return JsonResponse({'success': True, 'message': f'{len(processed_points)}개의 데이터가 성공적으로 수집되었습니다.'})
            finally:
                influx_conn.close()

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '유효하지 않은 JSON 형식입니다.'}, status=400)
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"INGEST ERROR: {error_msg}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def purge_sensor_data(request, sensor_id):
    sensor = get_object_or_404(Sensor, id=sensor_id, owner=request.user)

    if request.method == 'POST':
        if InfluxDBConnection is None:
            messages.error(request, 'InfluxDB가 설정되지 않았습니다.')
            return redirect('great_iot:sensor_detail', sensor_id=sensor.id)

        influx_conn = InfluxDBConnection()
        try:
            influx_conn.delete_data(
                measurement=sensor.measurement_name,
                tags={
                    'sensor_name': sensor.name,
                    'owner_id': str(sensor.owner.id)
                }
            )
            messages.success(request, f"센서 '{sensor.name}'의 모든 과거 데이터가 성공적으로 초기화되었습니다.")
        except Exception as e:
            messages.error(request, f"데이터 초기화 실패: {str(e)}")
        finally:
            influx_conn.close()

    return redirect('great_iot:sensor_detail', sensor_id=sensor.id)

@login_required
def iot_data(request):
    try:
        start_time_str = request.GET.get('start_time')
        end_time_str = request.GET.get('end_time')
        measurement = request.GET.get('measurement')
        sensor_id = request.GET.get('sensor_id')

        if not measurement:
             return JsonResponse({'success': False, 'error': 'Measurement 파라미터가 필요합니다.'}, status=400)

        if InfluxDBConnection is None:
            return JsonResponse({'success': False, 'error': 'InfluxDB가 설정되지 않았습니다.'}, status=500)

        tags = {}
        if sensor_id:
            sensor = get_object_or_404(Sensor, id=sensor_id, owner=request.user)
            tags['sensor_name'] = sensor.name
            tags['owner_id'] = str(request.user.id)
        
        if not start_time_str:
            time_range = '-1h'
        else:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            end_time = datetime.now(timezone.utc)
            total_seconds = (end_time - start_time).total_seconds()
            time_range = f'-{int(total_seconds)}s'

        influx_conn = InfluxDBConnection()
        try:
            fields = influx_conn.get_fields(measurement)
            result_data = {}
            labels = []

            for field in fields:
                series_data = influx_conn.get_time_series_data(measurement, field, time_range, tags=tags)
                current_labels = [point['time'] for point in series_data]
                current_values = [point['value'] for point in series_data]

                if len(current_labels) > len(labels):
                    labels = current_labels

                result_data[f'{field}_values'] = current_values

            if not result_data:
                return JsonResponse({'success': True, 'message': '데이터를 찾을 수 없습니다.'})

            response_payload = {
                'success': True,
                'labels': labels,
            }
            response_payload.update(result_data)
            return JsonResponse(response_payload)

        finally:
            influx_conn.close()

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@login_required
def generate_firmware(request, sensor_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST 요청만 허용됩니다.'}, status=405)

    if compile_sketch is None:
        return JsonResponse({'success': False, 'message': '펌웨어 컴파일러가 설정되지 않았습니다. development 앱이 필요합니다.'}, status=500)

    sensor = get_object_or_404(Sensor, id=sensor_id, owner=request.user)

    try:
        data = json.loads(request.body)
        wifi_ssid = data.get('ssid', 'YOUR_WIFI_SSID')
        wifi_password = data.get('password', 'YOUR_WIFI_PASSWORD')
        server_url = data.get('server_url')
        influx_url = settings.INFLUXDB_SETTINGS['url'].rstrip('/')
        parsed = urlparse(influx_url)
        influx_host = parsed.hostname or 'localhost'
        influx_port = parsed.port or 8086
        
        if not server_url:
            server_url = f"{influx_url}/iot/api/ingest/"
        
        is_multisensor = (
            sensor.board_type in ('esp32', 'esp32c3_supermini') and 
            sensor.attached_sensor == 'mSensor01'
        )
        
        logging_interval = data.get('logging_interval', 10)
        transmission_interval = data.get('transmission_interval', 10)
        
        try:
            logging_interval = int(logging_interval) if logging_interval is not None else 10
            transmission_interval = int(transmission_interval) if transmission_interval is not None else 10
        except (ValueError, TypeError):
            logging_interval = 10
            transmission_interval = 10
            
        if sensor.board_type == 'esp32':
            fqbn = 'esp32:esp32:esp32'
            options = ''
        elif sensor.board_type == 'esp32c3_supermini':
            fqbn = 'esp32:esp32:esp32c3'
            options = 'CDCOnBoot=cdc,FlashSize=4M,FlashMode=dio,PartitionScheme=default'
        elif sensor.board_type == 'arduino_esp01':
            fqbn = 'arduino:avr:uno'
            options = ''
        else:
            fqbn = 'esp32:esp32:esp32'
            options = ''
            
        if is_multisensor:
            import os
            if sensor.board_type == 'esp32c3_supermini':
                template_filename = 'esp32-c3_supermini_multisensor_00.cpp'
            else:
                template_filename = 'esp32_multisensor_00.cpp'
            template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cpps', template_filename)
            with open(template_path, 'r') as f:
                template = f.read()
            
            source_code = template.replace("{WIFI_SSID}", wifi_ssid) \
                                  .replace("{WIFI_PASSWORD}", wifi_password) \
                                  .replace("{SERVER_URL}", server_url) \
                                  .replace("{INFLUXDB_APIKEY}", sensor.api_key) \
                                  .replace("{INFLUXDB_HOST}", influx_host) \
                                  .replace("{INFLUXDB_PORT}", str(influx_port)) \
                                  .replace("{MEASUREMENT_INTERVAL}", str(logging_interval * 1000)) \
                                  .replace("{LOGGING_INTERVAL}", str(transmission_interval * 1000))
        else:
            template = ESP32_IOT_TEMPLATE
            if sensor.board_type == 'arduino_esp01':
                if sensor.attached_sensor == 'aht10':
                    template = ARDUINO_ESP01_AHT10_TEMPLATE
                elif sensor.attached_sensor == 'bh1750':
                    template = ARDUINO_ESP01_BH1750_TEMPLATE
                else:
                    template = ARDUINO_ESP01_IOT_TEMPLATE
            elif sensor.attached_sensor == 'timer':
                template = ESP32_TIMER_TEMPLATE
            elif sensor.attached_sensor == 'MPU6050_vib':
                template = ESP32_MPU6050_VIB_TEMPLATE
            elif sensor.attached_sensor == 'bme280':
                template = ESP32_BME280_TEMPLATE
            elif sensor.attached_sensor == 'bh1750':
                template = ESP32_BH1750_TEMPLATE
            elif sensor.attached_sensor == 'aht10':
                template = ESP32_AHT10_TEMPLATE
            elif sensor.attached_sensor == 'mSensor01':
                if sensor.board_type == 'esp32c3_supermini':
                    template = ESP32_C3_MSENSOR01_FULL_TEMPLATE
                elif logging_interval == 1:
                    template = ESP32_MSENSOR01_1S_TEMPLATE
                else:
                    template = ESP32_MSENSOR01_TEMPLATE

            if sensor.board_type == 'esp32c3_supermini':
                pin_subs = {"{SOUND_PIN}": "4", "{I2C_SDA}": "8", "{I2C_SCL}": "9"}
            else:
                pin_subs = {"{SOUND_PIN}": "35", "{I2C_SDA}": "21", "{I2C_SCL}": "22"}

            source_code = template.replace("{WIFI_SSID}", wifi_ssid) \
                                  .replace("{WIFI_PASSWORD}", wifi_password) \
                                  .replace("{API_KEY}", sensor.api_key) \
                                  .replace("{SERVER_URL}", server_url) \
                                  .replace("{INFLUXDB_HOST}", influx_host) \
                                  .replace("{INFLUXDB_PORT}", str(influx_port)) \
                                  .replace("{LOGGING_INTERVAL_MS}", str(logging_interval * 1000)) \
                                  .replace("{TRANSMISSION_INTERVAL_MS}", str(transmission_interval * 1000))

            for old, new in pin_subs.items():
                source_code = source_code.replace(old, new)

        preview_only = data.get('preview_only', False)
        if preview_only:
            return JsonResponse({
                'success': True,
                'source_code': source_code,
                'message': 'Source code preview generated.'
            })

        result = compile_sketch(source_code, board_fqbn=fqbn, board_options=options)
        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def probe_llm_server(base_url):
    base_url = base_url.rstrip('/')
    result = {'success': False, 'server_type': '', 'server_type_label': '', 'models': [], 'chat_url': ''}

    models_url = f"{base_url}/v1/models" if not base_url.endswith('/v1') else f"{base_url}/models"
    chat_url = f"{base_url.rstrip('/')}/v1/chat/completions"
    openai_models = None

    try:
        req = urllib.request.Request(models_url, headers={'User-Agent': 'Django-IoT/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            model_data = data.get('data', [])
            if model_data and all(isinstance(m, dict) and 'id' in m for m in model_data):
                openai_models = sorted([m['id'] for m in model_data])
    except Exception:
        pass

    ollama_url = f"{base_url}/api/tags"
    ollama_models = None

    try:
        req = urllib.request.Request(ollama_url, headers={'User-Agent': 'Django-IoT/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            models = data.get('models', [])
            if models and all(isinstance(m, dict) and 'name' in m for m in models):
                ollama_models = sorted([m['name'] for m in models])
    except Exception:
        pass

    if openai_models and ollama_models:
        result.update({
            'success': True,
            'server_type': 'ollama',
            'server_type_label': 'Ollama (OpenAI 호환 모드)',
            'models': ollama_models,
            'chat_url': chat_url,
        })
        return result

    if openai_models:
        result.update({
            'success': True,
            'server_type': 'openai',
            'server_type_label': 'OpenAI 호환 (LM Studio 등)',
            'models': openai_models,
            'chat_url': chat_url,
        })
        return result

    if ollama_models:
        ollama_chat = f"{base_url.rstrip('/')}/v1/chat/completions"
        result.update({
            'success': True,
            'server_type': 'ollama',
            'server_type_label': 'Ollama',
            'models': ollama_models,
            'chat_url': ollama_chat,
        })
        return result

    return result


@login_required
def check_llm_server(request):
    if request.method == 'POST':
        url = request.POST.get('url', '').strip()
        if not url:
            return JsonResponse({'success': False, 'error': '서버 URL이 필요합니다.'})
        result = probe_llm_server(url)
        return JsonResponse(result)
    return JsonResponse({'success': False, 'error': 'POST 요청만 허용됩니다.'})


TIME_RANGE_LABELS = {
    '1h': '최근 1시간',
    '24h': '최근 24시간',
    '7d': '최근 1주일',
    '30d': '최근 1개월',
    '180d': '최근 6개월',
    '365d': '최근 1년',
}


@login_required
def ai_analysis(request, sensor_id):
    sensor = get_object_or_404(Sensor, id=sensor_id, owner=request.user)
    servers = LLMServer.objects.filter(created_by=request.user)

    selected_range = request.GET.get('range', '1h')
    selected_server_id = request.GET.get('server_id')
    selected_model = request.GET.get('model', '')

    range_map = {
        '1h': '-1h', '24h': '-24h', '7d': '-7d',
        '30d': '-30d', '180d': '-180d', '365d': '-365d',
    }
    influx_range = range_map.get(selected_range, '-1h')

    raw_data = {}
    fields = []
    if sensor.attached_sensor != 'timer':
        if InfluxDBConnection is not None:
            try:
                influx_conn = InfluxDBConnection()
                fields = influx_conn.get_fields(sensor.measurement_name)
                for field in fields:
                    series = influx_conn.get_time_series_data(
                        sensor.measurement_name, field, influx_range,
                        tags={'sensor_name': sensor.name, 'owner_id': str(sensor.owner.id)}
                    )
                    raw_data[field] = [{'time': p['time'], 'value': p['value']} for p in series]
                influx_conn.close()
            except Exception as e:
                messages.warning(request, f"InfluxDB 데이터 조회 중 오류: {e}")
        else:
            messages.warning(request, "InfluxDB 연결 모듈이 없습니다. timeseries 앱을 설치하세요.")
    else:
        try:
            raw_data = json.loads(sensor.latest_data)
        except Exception:
            raw_data = {}

    stats = {}
    for field, points in raw_data.items():
        values = [p['value'] for p in points if isinstance(p.get('value'), (int, float))]
        if values:
            stats[field] = {
                'min': min(values), 'max': max(values),
                'avg': sum(values) / len(values),
                'count': len(values),
            }

    config = SensorAIConfig.objects.filter(user=request.user, sensor=sensor).first()

    analysis_result = None

    if request.method == 'POST':
        post_url = request.POST.get('url', '').strip()
        model_name = request.POST.get('model', '').strip()
        post_range = request.POST.get('range', selected_range)
        post_notes = request.POST.get('notes', '').strip()

        if post_url and model_name:
            SensorAIConfig.objects.update_or_create(
                user=request.user, sensor=sensor,
                defaults={
                    'server_url': post_url,
                    'model_name': model_name,
                    'notes': post_notes,
                },
            )
            if post_range != selected_range:
                selected_range = post_range
                influx_range = range_map.get(selected_range, '-1h')
                raw_data = {}
                fields = []
                if sensor.attached_sensor != 'timer':
                    if InfluxDBConnection is not None:
                        try:
                            influx_conn = InfluxDBConnection()
                            fields = influx_conn.get_fields(sensor.measurement_name)
                            for field in fields:
                                series = influx_conn.get_time_series_data(
                                    sensor.measurement_name, field, influx_range,
                                    tags={'sensor_name': sensor.name, 'owner_id': str(sensor.owner.id)}
                                )
                                raw_data[field] = [{'time': p['time'], 'value': p['value']} for p in series]
                            influx_conn.close()
                        except Exception:
                            pass
                else:
                    try:
                        raw_data = json.loads(sensor.latest_data)
                    except Exception:
                        raw_data = {}
                stats = {}
                for field, points in raw_data.items():
                    values = [p['value'] for p in points if isinstance(p.get('value'), (int, float))]
                    if values:
                        stats[field] = {
                            'min': min(values), 'max': max(values),
                            'avg': sum(values) / len(values),
                            'count': len(values),
                        }

            time_label = TIME_RANGE_LABELS.get(selected_range, selected_range)

            stats_lines = [f"- {f}: 평균={s['avg']:.2f}, 최소={s['min']:.2f}, 최대={s['max']:.2f}, 데이터 수={s['count']}" for f, s in stats.items()]
            stats_summary = '\n'.join(stats_lines)

            raw_sample = {f: points[:50] for f, points in raw_data.items()}

            prompt = (
                f"다음은 IoT 센서 '{sensor.name}'({sensor.get_attached_sensor_display()})의 "
                f"{time_label} 동안 수집된 데이터입니다.\n\n"
                f"## 데이터 요약\n{stats_summary}\n\n"
                f"## 원시 데이터 샘플 (최대 50행)\n{json.dumps(raw_sample, ensure_ascii=False, indent=2)}\n\n"
            )

            if post_notes:
                prompt += (
                    f"## 분석 시 주의사항\n{post_notes}\n\n"
                )

            prompt += (
                "위 데이터를 분석하여 다음 항목에 대해 한글로 상세한 리포트를 작성해주세요:\n"
                "1. 데이터 개요 및 수집 현황\n"
                "2. 각 측정 항목별 통계 분석 (평균, 최소, 최대, 변동 추이)\n"
                "3. 이상 징후 및 특이 사항\n"
                "4. 종합 평가 및 권장 조치 사항"
            )

            probe = probe_llm_server(post_url)
            api_url = probe.get('chat_url', '')
            if not api_url:
                api_url = post_url.rstrip('/')
                if not api_url.endswith('/chat/completions'):
                    api_url += '/chat/completions'

            try:
                payload = json.dumps({
                    'model': model_name,
                    'messages': [
                        {'role': 'system', 'content': '당신은 전문 IoT 데이터 분석가입니다. 주어진 센서 데이터를 분석하여 한글로 상세한 리포트를 작성해주세요.'},
                        {'role': 'user', 'content': prompt},
                    ],
                    'temperature': 0.3,
                    'max_tokens': 4096,
                    'stream': False,
                }).encode('utf-8')

                headers = {'Content-Type': 'application/json'}

                req = urllib.request.Request(api_url, data=payload, headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    analysis_result = result.get('choices', [{}])[0].get('message', {}).get('content', '응답을 파싱할 수 없습니다.')
                    if analysis_result:
                        AnalysisReport.objects.create(
                            user=request.user, sensor=sensor,
                            server_url=post_url, model_name=model_name,
                            notes=post_notes, time_range=selected_range,
                            result=analysis_result,
                        )
                    messages.success(request, 'AI 분석이 완료되었습니다.')

            except urllib.error.HTTPError as e:
                messages.error(request, f"LLM 서버 오류 ({e.code}): {e.read().decode('utf-8', errors='replace')}")
            except urllib.error.URLError as e:
                messages.error(request, f"LLM 서버 연결 실패: {e.reason}")
            except Exception as e:
                messages.error(request, f"분석 중 오류 발생: {e}")

    selected_range_label = TIME_RANGE_LABELS.get(selected_range, selected_range)
    raw_data_json = json.dumps(raw_data, ensure_ascii=False, indent=2)
    servers = LLMServer.objects.filter(created_by=request.user)
    reports = AnalysisReport.objects.filter(user=request.user, sensor=sensor)[:30]

    server_url = request.POST.get('url', '') or (config.server_url if config else '')
    selected_model = request.POST.get('model', '') or (config.model_name if config else '')
    config_notes = request.POST.get('notes', '') or (config.notes if config else '')

    return render(request, 'great_iot/ai_analysis.html', {
        'sensor': sensor,
        'servers': servers,
        'selected_range': selected_range,
        'selected_range_label': selected_range_label,
        'stats': stats,
        'raw_data': raw_data,
        'analysis_result': analysis_result,
        'server_url': server_url,
        'selected_model': selected_model,
        'config_notes': config_notes,
        'time_ranges': TIME_RANGE_LABELS,
        'fields': fields,
        'raw_data_json': raw_data_json,
        'reports': reports,
    })


@login_required
def add_llm_server(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        url = request.POST.get('url', '').strip()
        api_key = request.POST.get('api_key', '').strip()
        default_model = request.POST.get('default_model', 'gemma3:12b').strip()

        if not name or not url:
            messages.error(request, '서버 이름과 URL은 필수입니다.')
            return redirect(request.META.get('HTTP_REFERER', 'great_iot:iot_dashboard'))

        LLMServer.objects.create(
            name=name, url=url, api_key=api_key,
            default_model=default_model, created_by=request.user,
        )
        messages.success(request, f'LLM 서버 "{name}"가 추가되었습니다.')

    return redirect(request.META.get('HTTP_REFERER', 'great_iot:iot_dashboard'))


@login_required
def load_report(request, report_id):
    report = get_object_or_404(AnalysisReport, id=report_id, user=request.user)
    return JsonResponse({
        'success': True,
        'result': report.result,
        'created_at': report.created_at.isoformat(),
        'model_name': report.model_name,
        'time_range': report.time_range,
        'notes': report.notes,
    })

@login_required
def delete_llm_server(request, server_id):
    server = get_object_or_404(LLMServer, id=server_id, created_by=request.user)
    if request.method == 'POST':
        server.delete()
        messages.success(request, f'LLM 서버 "{server.name}"가 삭제되었습니다.')
    return redirect(request.META.get('HTTP_REFERER', 'great_iot:iot_dashboard'))
