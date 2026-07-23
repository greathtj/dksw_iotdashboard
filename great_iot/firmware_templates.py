# great_iot/firmware_templates.py

ESP32_IOT_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\\nConnecting to WiFi...");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\\nWiFi Connected!");
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");
        StaticJsonDocument<200> doc;
        doc["api_key"] = apiKey;
        JsonObject data = doc.createNestedObject("data");
        data["temperature"] = 20.0 + (random(0, 100) / 10.0); 
        data["humidity"] = 40.0 + (random(0, 200) / 10.0);
        String requestBody;
        serializeJson(doc, requestBody);
        http.POST(requestBody);
        http.end();
    }
    delay({LOGGING_INTERVAL_MS});
}
"""

ESP32_MPU6050_VIB_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_MPU6050 mpu;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    if (!mpu.begin()) while (1) delay(10);
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");
        StaticJsonDocument<300> doc;
        doc["api_key"] = apiKey;
        JsonObject data = doc.createNestedObject("data");
        data["accel_x"] = a.acceleration.x;
        data["accel_y"] = a.acceleration.y;
        data["accel_z"] = a.acceleration.z;
        String requestBody;
        serializeJson(doc, requestBody);
        http.POST(requestBody);
        http.end();
    }
    delay({LOGGING_INTERVAL_MS});
}
"""

ESP32_TIMER_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

unsigned long startTimeEpoch = 0;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    configTime(0, 0, "pool.ntp.org");
    struct tm timeinfo;
    if(getLocalTime(&timeinfo)) startTimeEpoch = time(NULL);
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");
        unsigned long currentEpoch = time(NULL);
        StaticJsonDocument<300> doc;
        doc["api_key"] = apiKey;
        JsonObject data = doc.createNestedObject("data");
        data["start_time"] = (double)startTimeEpoch; 
        data["current_time"] = (double)currentEpoch;
        data["elapsed_time"] = (double)(currentEpoch - startTimeEpoch);
        String requestBody;
        serializeJson(doc, requestBody);
        http.POST(requestBody);
        http.end();
    }
    delay({LOGGING_INTERVAL_MS});
}
"""

ESP32_BME280_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Wire.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_BME280 bme;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    if (!bme.begin(0x76)) while (1) delay(10);
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");
        StaticJsonDocument<300> doc;
        doc["api_key"] = apiKey;
        JsonObject data = doc.createNestedObject("data");
        data["temperature"] = bme.readTemperature();
        data["humidity"] = bme.readHumidity();
        data["pressure"] = bme.readPressure() / 100.0F;
        String requestBody;
        serializeJson(doc, requestBody);
        http.POST(requestBody);
        http.end();
    }
    delay({LOGGING_INTERVAL_MS});
}
"""

ESP32_BH1750_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <BH1750.h>
#include <Wire.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

BH1750 lightMeter;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Wire.begin();
    lightMeter.begin();
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");
        StaticJsonDocument<300> doc;
        doc["api_key"] = apiKey;
        JsonObject data = doc.createNestedObject("data");
        data["light"] = lightMeter.readLightLevel();
        String requestBody;
        serializeJson(doc, requestBody);
        http.POST(requestBody);
        http.end();
    }
    delay({LOGGING_INTERVAL_MS});
}
"""

ARDUINO_ESP01_IOT_TEMPLATE = """
#include <SoftwareSerial.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* apiKey = "{API_KEY}";
const char* host = "{INFLUXDB_HOST}";
const int port = {INFLUXDB_PORT};

SoftwareSerial esp(2, 3);

void connectWiFi() {
  Serial.println(F("Connecting WiFi..."));
  esp.println(F("AT+CIPCLOSE"));
  delay(1000);
  esp.println(F("AT+CWMODE=1"));
  delay(1000);
  esp.println(F("AT+CIPMUX=0"));
  delay(1000);
  String cmd = "AT+CWJAP=\"" + String(ssid) + "\",\"" + String(password) + "\"";
  esp.println(cmd);
  delay(10000);
  Serial.println(F("WiFi Setup Done."));
}

void setup() {
  Serial.begin(115200);
  esp.begin(115200);
  delay(2000);
  Serial.println(F("Activating..."));
  connectWiFi();
}

void loop() {
  float t = 20.0 + (random(0, 100) / 10.0);
  float h = 40.0 + (random(0, 200) / 10.0);

  String payload = "{\\"api_key\\":\\"" + String(apiKey) + "\\",\\"data\\":{\\"temperature\\":" + String(t) + ",\\"humidity\\":" + String(h) + "}}";

  Serial.println("Posting: " + payload);

  esp.println("AT+CIPSTART=\\"TCP\\",\\"" + String(host) + "\\"," + String(port));
  delay(2000);

  String postRequest = "POST /iot/api/ingest/ HTTP/1.1\\r\\n";
  postRequest += "Host: " + String(host) + ":" + String(port) + "\\r\\n";
  postRequest += "Content-Type: application/json\\r\\n";
  postRequest += "Content-Length: " + String(payload.length()) + "\\r\\n";
  postRequest += "Connection: close\\r\\n\\r\\n";
  postRequest += payload;

  esp.print(F("AT+CIPSEND="));
  esp.println(postRequest.length());
  delay(1000);

  esp.print(postRequest);
  delay(3000);

  esp.println(F("AT+CIPCLOSE"));
  delay(1000);

  delay({LOGGING_INTERVAL_MS});
}
"""

ESP32_AHT10_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_AHTX0.h>
#include <Wire.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_AHTX0 aht;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    if (!aht.begin()) while (1) delay(10);
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        sensors_event_t hum, temp;
        aht.getEvent(&hum, &temp);
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");
        StaticJsonDocument<300> doc;
        doc["api_key"] = apiKey;
        JsonObject data = doc.createNestedObject("data");
        data["temperature"] = temp.temperature;
        data["humidity"] = hum.relative_humidity;
        String requestBody;
        serializeJson(doc, requestBody);
        http.POST(requestBody);
        http.end();
    }
    delay({LOGGING_INTERVAL_MS});
}
"""

ESP32_MSENSOR01_TEMPLATE = """#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>

#define SOUND_PIN 35
#define I2C_SDA 21
#define I2C_SCL 22

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_MPU6050 mpu;
Adafruit_BME280 bme;

void setup() {
    Serial.begin(115200);
    
    Serial.println("\\n=== mSensor01 Booting ===");
    delay(100);
    Serial.print("Free heap: ");
    Serial.println(ESP.getFreeHeap());
    
    Serial.println("Initializing I2C...");
    Wire.begin(I2C_SDA, I2C_SCL);
    Serial.println("I2C OK");
    
    Serial.println("Checking MPU6050...");
    if (mpu.begin()) {
        Serial.println("MPU6050 OK");
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    } else {
        Serial.println("MPU6050 NOT FOUND - Check wiring!");
    }
    
    Serial.println("Checking BME280...");
    if (bme.begin(0x76)) {
        Serial.println("BME280 OK");
    } else {
        Serial.println("BME280 NOT FOUND - Check wiring or address!");
    }
    
    Serial.println("\\n=== READY ===");
}

void loop() {
    delay(1000);
}
"""

ESP32_C3_MSENSOR01_TEMPLATE = """#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>

#define SOUND_PIN 0
#define I2C_SDA 8
#define I2C_SCL 9

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_MPU6050* mpu = NULL;
Adafruit_BME280* bme = NULL;

void setup() {
    Serial.begin(115200);
    
    Serial.println("\\n=== START ===");
    delay(100);
    Serial.println("Step 1: OK");
    delay(100);
    
    Serial.print("Free heap: ");
    Serial.println(ESP.getFreeHeap());
    Serial.println("Step 2: OK");
    delay(100);
    
    mpu = new Adafruit_MPU6050();
    bme = new Adafruit_BME280();
    
    Serial.println("Step 3: Allocated sensors");
    delay(100);
    
    Serial.println("Step 4: I2C...");
    Wire.begin(I2C_SDA, I2C_SCL);
    Serial.println("Step 5: OK");
    delay(100);
    
    Serial.println("Step 6: MPU6050 init...");
    if (mpu->begin()) {
        Serial.println("Found!");
    } else {
        Serial.println("Not found!");
    }
}

void loop() {
    Serial.print(".");
    delay(1000);
}
"""

ESP32_C3_MSENSOR01_FULL_TEMPLATE = """#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>
#include "arduinoFFT.h"
#include "esp_task_wdt.h"

#define SOUND_PIN {SOUND_PIN}
#define I2C_SDA {I2C_SDA}
#define I2C_SCL {I2C_SCL}
#define SAMPLES 128

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_MPU6050 mpu;
Adafruit_BME280 bme;

double vRealX[SAMPLES], vImagX[SAMPLES];
double vRealY[SAMPLES], vImagY[SAMPLES];
double vRealZ[SAMPLES], vImagZ[SAMPLES];

unsigned long lastWifiAttempt = 0;
const unsigned long WIFI_RETRY_INTERVAL = 10000;

void ensureWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;
    unsigned long now = millis();
    if (now - lastWifiAttempt < WIFI_RETRY_INTERVAL) return;
    lastWifiAttempt = now;
    Serial.println("WiFi lost, reconnecting...");
    WiFi.disconnect(false);
    WiFi.reconnect();
    esp_task_wdt_reset();
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        esp_task_wdt_reset();
        Serial.print("r");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(" WiFi OK");
    } else {
        Serial.println(" fail (will retry in 10s)");
    }
}

void setup() {
    Serial.begin(115200);
    for (int i = 0; i < 10 && !Serial; i++) delay(500);

    esp_task_wdt_config_t wdtConfig = {
        .timeout_ms = 10000,
        .trigger_panic = true,
    };
    esp_task_wdt_init(&wdtConfig);
    esp_task_wdt_add(NULL);

    Serial.println("\\n--- C3 mSensor01 Booting ---");
    WiFi.begin(ssid, password);
    int dots = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        if (++dots > 40) ESP.restart();
    }
    Serial.println("\\nWiFi Connected!");
    WiFi.setSleep(false);

    Serial.print("Configuring NTP...");
    configTime(9 * 3600, 0, "pool.ntp.org", "time.google.com");
    struct tm timeinfo;
    int retry = 0;
    while (!getLocalTime(&timeinfo) && retry < 30) {
        delay(500);
        Serial.print("t");
        retry++;
    }
    Serial.println(retry < 30 ? " OK" : " FAIL (proceeding without NTP)");

    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000);

    if (!mpu.begin()) {
        Serial.println("MPU6050 NOT FOUND");
    } else {
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setFilterBandwidth(MPU6050_BAND_260_HZ);
        Serial.println("MPU6050 OK");
    }

    if (!bme.begin(0x76)) {
        Serial.println("BME280 NOT FOUND");
    } else {
        Serial.println("BME280 OK");
    }

    Serial.println("--- Ready ---");
}

void loop() {
    esp_task_wdt_reset();
    static unsigned long lastMeasure = 0;
    if (millis() - lastMeasure < {LOGGING_INTERVAL_MS}) return;
    lastMeasure = millis();

    double velSumSqX = 0, velSumSqY = 0, velSumSqZ = 0;
    unsigned int signalMax = 0, signalMin = 4095;

    for (int i = 0; i < SAMPLES; i++) {
        sensors_event_t a, g, temp;
        if (mpu.getEvent(&a, &g, &temp)) {
            vRealX[i] = a.acceleration.x; vImagX[i] = 0;
            vRealY[i] = a.acceleration.y; vImagY[i] = 0;
            vRealZ[i] = a.acceleration.z; vImagZ[i] = 0;
            velSumSqX += pow(a.acceleration.x * 100, 2);
            velSumSqY += pow(a.acceleration.y * 100, 2);
            velSumSqZ += pow((a.acceleration.z - 9.81) * 100, 2);
        }
        int sRaw = analogRead(SOUND_PIN);
        if (sRaw < 4095) {
            if (sRaw > signalMax) signalMax = sRaw;
            if (sRaw < signalMin) signalMin = sRaw;
        }
    }

    auto doFft = [&](double* r, double* im, int n, double fs) {
        ArduinoFFT<double> fft(r, im, n, fs);
        fft.dcRemoval();
        fft.windowing(FFT_WIN_TYP_HAMMING, FFT_FORWARD);
        fft.compute(FFT_FORWARD);
        return fft.majorPeak();
    };

    double fX = doFft(vRealX, vImagX, SAMPLES, SAMPLES / 0.13);
    double fY = doFft(vRealY, vImagY, SAMPLES, SAMPLES / 0.13);
    double fZ = doFft(vRealZ, vImagZ, SAMPLES, SAMPLES / 0.13);

    double vX = sqrt(velSumSqX / SAMPLES) * (0.13 / SAMPLES);
    double vY = sqrt(velSumSqY / SAMPLES) * (0.13 / SAMPLES);
    double vZ = sqrt(velSumSqZ / SAMPLES) * (0.13 / SAMPLES);

    unsigned int peakToPeak = (signalMax > signalMin) ? signalMax - signalMin : 0;
    double sDb = 20.0 * log10((double)peakToPeak + 1.0);

    float tempC = bme.readTemperature();
    float humidity = bme.readHumidity();
    float pressure = bme.readPressure() / 100.0F;

    ensureWiFi();
    if (WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);

    JsonDocument doc;
    doc["api_key"] = apiKey;
    JsonObject data = doc["data"].to<JsonObject>();

    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
        time_t now = mktime(&timeinfo);
        data["timestamp"] = (unsigned long)now;
    }
    data["fX"] = fX;
    data["fY"] = fY;
    data["fZ"] = fZ;
    data["vX"] = vX;
    data["vY"] = vY;
    data["vZ"] = vZ;
    data["sDb"] = sDb;
    data["temperature"] = tempC;
    data["humidity"] = humidity;
    data["pressure"] = pressure;

    String body;
    serializeJson(doc, body);
    int code = http.POST(body);
    if (code <= 0) {
        Serial.print("HTTP POST failed, code: ");
        Serial.println(code);
    }
    http.end();
}
"""

ESP32_MSENSOR01_1S_TEMPLATE = """
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>
#include "arduinoFFT.h"

#define SOUND_PIN {SOUND_PIN}
#define I2C_SDA {I2C_SDA}
#define I2C_SCL {I2C_SCL}
#define SAMPLES 128
#define BUFFER_SIZE 5

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{API_KEY}";

Adafruit_MPU6050 mpu;
Adafruit_BME280 bme;

double vRealX[SAMPLES], vImagX[SAMPLES];
double vRealY[SAMPLES], vImagY[SAMPLES];
double vRealZ[SAMPLES], vImagZ[SAMPLES];

unsigned int signalMax = 0;
unsigned int signalMin = 4095;
unsigned long nextMeasurementTime = 0;

struct SensorData {
    double fX, fY, fZ;
    double vX, vY, vZ;
    double sDb;
    float temp, hum, pres;
    unsigned long timestamp;
};

SensorData buffer[BUFFER_SIZE];
int bufferIndex = 0;

void setup() {
    Serial.begin(115200);
    for(int i = 0; i < 10 && !Serial; i++) delay(500);
    
    Serial.println("\\n--- mSensor01 (Buffered 1s + NTP) Booting ---");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.println("\\nWiFi Connected!");

    Serial.println("Synchronizing time...");
    configTime(0, 0, "pool.ntp.org");
    struct tm timeinfo;
    int retry = 0;
    while(!getLocalTime(&timeinfo) && retry < 20) {
        delay(500);
        Serial.print("t");
        retry++;
    }
    Serial.println("\\nTime synchronized.");

    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000); 

    if (!mpu.begin()) Serial.println("MPU6050 Fail");
    else {
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setFilterBandwidth(MPU6050_BAND_260_HZ);
    }
    if (!bme.begin(0x76)) Serial.println("BME280 Fail");

    nextMeasurementTime = millis() + 1000;
}

void loop() {
    int sRaw = analogRead(SOUND_PIN);
    if (sRaw < 4095) {
        if (sRaw > signalMax) signalMax = sRaw;
        if (sRaw < signalMin) signalMin = sRaw;
    }

    if (millis() >= nextMeasurementTime) {
        nextMeasurementTime = millis() + 1000;

        double velSumSqX = 0, velSumSqY = 0, velSumSqZ = 0;
        unsigned long startTime = micros();

        for (int i = 0; i < SAMPLES; i++) {
            sensors_event_t a, g, temp_m;
            mpu.getEvent(&a, &g, &temp_m);
            vRealX[i] = a.acceleration.x; vImagX[i] = 0;
            vRealY[i] = a.acceleration.y; vImagY[i] = 0;
            vRealZ[i] = a.acceleration.z - 9.81; vImagZ[i] = 0;
            velSumSqX += pow(a.acceleration.x * 100, 2); 
            velSumSqY += pow(a.acceleration.y * 100, 2);
            velSumSqZ += pow((a.acceleration.z - 9.81) * 100, 2); 
            
            int sRaw = analogRead(SOUND_PIN);
            if (sRaw < 4095) {
                if (sRaw > signalMax) signalMax = sRaw;
                if (sRaw < signalMin) signalMin = sRaw;
            }
        }

        unsigned long endTime = micros();
        double duration = (endTime - startTime) / 1000000.0;
        double actualFs = SAMPLES / duration;

        auto getFreq = [&](double* r, double* im) {
            ArduinoFFT<double> FFT = ArduinoFFT<double>(r, im, SAMPLES, actualFs);
            FFT.dcRemoval();
            FFT.windowing(FFT_WIN_TYP_HAMMING, FFT_FORWARD);
            FFT.compute(FFT_FORWARD);
            return FFT.majorPeak();
        };

        buffer[bufferIndex].fX = getFreq(vRealX, vImagX);
        buffer[bufferIndex].fY = getFreq(vRealY, vImagY);
        buffer[bufferIndex].fZ = getFreq(vRealZ, vImagZ);
        buffer[bufferIndex].vX = sqrt(velSumSqX/SAMPLES)*(duration/SAMPLES);
        buffer[bufferIndex].vY = sqrt(velSumSqY/SAMPLES)*(duration/SAMPLES);
        buffer[bufferIndex].vZ = sqrt(velSumSqZ/SAMPLES)*(duration/SAMPLES);
        
        unsigned int peakToPeak = signalMax - signalMin;
        buffer[bufferIndex].sDb = 20.0 * log10((double)peakToPeak + 1.0);
        buffer[bufferIndex].temp = bme.readTemperature();
        buffer[bufferIndex].hum = bme.readHumidity();
        buffer[bufferIndex].pres = bme.readPressure() / 100.0F;
        buffer[bufferIndex].timestamp = time(NULL);

        Serial.printf("Measured [%d/%d]: Temp=%.1f, Time=%lu\\n", bufferIndex+1, BUFFER_SIZE, buffer[bufferIndex].temp, buffer[bufferIndex].timestamp);
        
        signalMax = 0; 
        signalMin = 4095;

        bufferIndex++;

        if (bufferIndex >= BUFFER_SIZE) {
            if (WiFi.status() == WL_CONNECTED) {
                HTTPClient http;
                http.begin(serverUrl);
                http.addHeader("Content-Type", "application/json");
                
                JsonDocument doc;
                doc["api_key"] = apiKey;
                JsonArray dataArr = doc["data"].to<JsonArray>();
                
                for (int i = 0; i < BUFFER_SIZE; i++) {
                    JsonObject obj = dataArr.add<JsonObject>();
                    obj["timestamp"] = buffer[i].timestamp;
                    obj["fX"] = buffer[i].fX;
                    obj["fY"] = buffer[i].fY;
                    obj["fZ"] = buffer[i].fZ;
                    obj["vX"] = buffer[i].vX;
                    obj["vY"] = buffer[i].vY;
                    obj["vZ"] = buffer[i].vZ;
                    obj["sDb"] = buffer[i].sDb;
                    obj["temperature"] = buffer[i].temp;
                    obj["humidity"] = buffer[i].hum;
                    obj["pressure"] = buffer[i].pres;
                }

                String requestBody;
                serializeJson(doc, requestBody);
                int httpResponseCode = http.POST(requestBody);
                Serial.printf("Transmitted %d points. HTTP Code: %d\\n", BUFFER_SIZE, httpResponseCode);
                http.end();
            }
            bufferIndex = 0;
        }
    }
}
"""

ARDUINO_ESP01_AHT10_TEMPLATE = """
#include <SoftwareSerial.h>
#include <Adafruit_AHTX0.h>
#include <Wire.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* apiKey = "{API_KEY}";
const char* host = "{INFLUXDB_HOST}";
const int port = {INFLUXDB_PORT};

SoftwareSerial esp(2, 3);
Adafruit_AHTX0 aht;

void connectWiFi() {
  Serial.println(F("Connecting WiFi..."));
  esp.println(F("AT+CIPCLOSE"));
  delay(1000);
  esp.println(F("AT+CWMODE=1"));
  delay(1000);
  esp.println(F("AT+CIPMUX=0"));
  delay(1000);
  String cmd = "AT+CWJAP=\"" + String(ssid) + "\",\"" + String(password) + "\"";
  esp.println(cmd);
  delay(10000);
  Serial.println(F("WiFi Setup Done."));
}

void setup() {
  Serial.begin(115200);
  esp.begin(115200);
  delay(2000);
  Serial.println(F("Activating AHT10..."));

  Wire.begin();
  if (!aht.begin()) {
    Serial.println(F("AHT10 Fail"));
    while (1);
  }

  connectWiFi();
}

void loop() {
  sensors_event_t hum, temp;
  aht.getEvent(&hum, &temp);

  String payload = "{\\"api_key\\":\\"" + String(apiKey) + "\\",\\"data\\":{\\"temperature\\":" + String(temp.temperature) + ",\\"humidity\\":" + String(hum.relative_humidity) + "}}";

  Serial.println("Posting: " + payload);

  esp.println("AT+CIPSTART=\\"TCP\\",\\"" + String(host) + "\\"," + String(port));
  delay(2000);

  String postRequest = "POST /iot/api/ingest/ HTTP/1.1\\r\\n";
  postRequest += "Host: " + String(host) + ":" + String(port) + "\\r\\n";
  postRequest += "Content-Type: application/json\\r\\n";
  postRequest += "Content-Length: " + String(payload.length()) + "\\r\\n";
  postRequest += "Connection: close\\r\\n\\r\\n";
  postRequest += payload;

  esp.print(F("AT+CIPSEND="));
  esp.println(postRequest.length());
  delay(1000);

  esp.print(postRequest);
  delay(3000);

  esp.println(F("AT+CIPCLOSE"));
  delay(1000);

  delay({LOGGING_INTERVAL_MS});
}
"""

ARDUINO_ESP01_BH1750_TEMPLATE = """
#include <SoftwareSerial.h>
#include <BH1750.h>
#include <Wire.h>

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* apiKey = "{API_KEY}";
const char* host = "{INFLUXDB_HOST}";
const int port = {INFLUXDB_PORT};

SoftwareSerial esp(2, 3);
BH1750 lightMeter;

void connectWiFi() {
  Serial.println(F("Connecting WiFi..."));
  esp.println(F("AT+CIPCLOSE"));
  delay(1000);
  esp.println(F("AT+CWMODE=1"));
  delay(1000);
  esp.println(F("AT+CIPMUX=0"));
  delay(1000);
  String cmd = "AT+CWJAP=\"" + String(ssid) + "\",\"" + String(password) + "\"";
  esp.println(cmd);
  delay(10000);
  Serial.println(F("WiFi Setup Done."));
}

void setup() {
  Serial.begin(115200);
  esp.begin(115200);
  delay(2000);
  Serial.println(F("Activating BH1750..."));

  Wire.begin();
  if (!lightMeter.begin()) {
    Serial.println(F("BH1750 Fail"));
    while (1);
  }

  connectWiFi();
}

void loop() {
  float lux = lightMeter.readLightLevel();

  String payload = "{\\"api_key\\":\\"" + String(apiKey) + "\\",\\"data\\":{\\"light\\":" + String(lux) + "}}";

  Serial.println("Posting: " + payload);

  esp.println("AT+CIPSTART=\\"TCP\\",\\"" + String(host) + "\\"," + String(port));
  delay(2000);

  String postRequest = "POST /iot/api/ingest/ HTTP/1.1\\r\\n";
  postRequest += "Host: " + String(host) + ":" + String(port) + "\\r\\n";
  postRequest += "Content-Type: application/json\\r\\n";
  postRequest += "Content-Length: " + String(payload.length()) + "\\r\\n";
  postRequest += "Connection: close\\r\\n\\r\\n";
  postRequest += payload;

  esp.print(F("AT+CIPSEND="));
  esp.println(postRequest.length());
  delay(1000);

  esp.print(postRequest);
  delay(3000);

  esp.println(F("AT+CIPCLOSE"));
  delay(1000);

  delay({LOGGING_INTERVAL_MS});
}
"""
