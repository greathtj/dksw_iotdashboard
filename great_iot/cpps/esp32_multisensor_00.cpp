#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <time.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>
#include "arduinoFFT.h"

#define SAMPLES 128          
#define SAMPLING_FREQ 200    
#define SOUND_PIN 35
#define I2C_SDA 21
#define I2C_SCL 22

const char* ssid = "{WIFI_SSID}";
const char* password = "{WIFI_PASSWORD}";
const char* serverUrl = "{SERVER_URL}";
const char* apiKey = "{INFLUXDB_APIKEY}";

const long measurement_interval = {MEASUREMENT_INTERVAL};
const long logging_interval = {LOGGING_INTERVAL};

const long gmtOffset_sec = 9 * 3600; 
const int daylightOffset_sec = 0;

Adafruit_MPU6050 mpu;
Adafruit_BME280 bme; 

struct MeasurementRow {
  unsigned long timestamp;
  double fX, fY, fZ;
  float vX, vY, vZ;
  float sDb;
  float temp;
  float humid;
  float press;
};

struct BatchPacket {
  MeasurementRow rows[10];
};

#define BACKUP_BUFFER_SIZE 30
BatchPacket backupBuffer[BACKUP_BUFFER_SIZE];
int backupHead = 0; 
int backupTail = 0; 
int backupCount = 0; 

QueueHandle_t dataQueue;

TaskHandle_t MeasurementTaskHandle = NULL;
TaskHandle_t LoggingTaskHandle = NULL;

void MeasurementTask(void *parameter);
void LoggingTask(void *parameter);

void printLocalTimeWithMs() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  time_t nowtime = tv.tv_sec;
  struct tm *timeinfo = localtime(&nowtime);
  long long mills = tv.tv_usec / 1000;

  char timeStringBuff[30]; 
  strftime(timeStringBuff, sizeof(timeStringBuff), "%Y-%m-%d_%H:%M:%S", timeinfo);
  
  Serial.print("Time:");
  Serial.print(timeStringBuff);
  Serial.print(".");
  if(mills < 100) Serial.print("0"); 
  if(mills < 10)  Serial.print("0");
  Serial.print((int)mills);
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 10 && !Serial; i++) delay(500);

  Serial.println("\n--- ESP32 DevKit Booting ---");
  WiFi.begin(ssid, password);
  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
      if (++dots > 40) ESP.restart();
  }
  Serial.println("\nWiFi Connected!");
  
  Serial.print("Configuring NTP...");
  configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.google.com");
  struct tm timeinfo;
  int retry = 0;
  while(!getLocalTime(&timeinfo) && retry < 30){
     delay(500);
     Serial.print("t");
     retry++;
  }
  Serial.println(retry < 30 ? " OK" : " FAIL");

  Wire.begin(I2C_SDA, I2C_SCL); 
  Wire.setClock(100000);
  pinMode(SOUND_PIN, INPUT);

  if (!mpu.begin()) {
    Serial.println("MPU6050 NOT FOUND");
    while (1) { delay(10); }
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  if (!bme.begin(0x76, &Wire)) {
    if (!bme.begin(0x77, &Wire)) {
      Serial.println("BME280 NOT FOUND");
      while (1) { delay(10); }
    }
  }

  dataQueue = xQueueCreate(15, sizeof(MeasurementRow));

  xTaskCreatePinnedToCore(MeasurementTask, "MeasureTask", 8192, NULL, 2, &MeasurementTaskHandle, 1);
  xTaskCreatePinnedToCore(LoggingTask, "LogTask", 8192, NULL, 1, &LoggingTaskHandle, 0);

  Serial.println("--- Dual-Core FreeRTOS Threads Initialized ---");
}

void loop() {
  vTaskDelete(NULL); 
}

void MeasurementTask(void *parameter) {
  ArduinoFFT<double> FFT = ArduinoFFT<double>();
  double vRealX[SAMPLES], vImagX[SAMPLES];
  double vRealY[SAMPLES], vImagY[SAMPLES];
  double vRealZ[SAMPLES], vImagZ[SAMPLES];
  
  float velX = 0, velY = 0, velZ = 0;
  float alpha = 0.98;
  unsigned long sampling_period_us = round(1000000 * (1.0 / SAMPLING_FREQ));
  unsigned long microseconds;

  while(1) {
    sensors_event_t a, g, temp;
    float dt = 1.0 / SAMPLING_FREQ;

    for (int i = 0; i < SAMPLES; i++) {
      microseconds = micros();
      mpu.getEvent(&a, &g, &temp);
      
      vRealX[i] = a.acceleration.x;
      vRealY[i] = a.acceleration.y;
      vRealZ[i] = a.acceleration.z - 9.81; 
      
      vImagX[i] = 0; vImagY[i] = 0; vImagZ[i] = 0;

      velX = alpha * (velX + vRealX[i] * dt);
      velY = alpha * (velY + vRealY[i] * dt);
      velZ = alpha * (velZ + vRealZ[i] * dt);

      while (micros() < (microseconds + sampling_period_us)) { }
    }

    int soundMin = 4095;
    int soundMax = 0;
    unsigned long startSoundSample = millis();
    
    while (millis() - startSoundSample < 10) {
      int soundRaw = analogRead(SOUND_PIN);
      if (soundRaw < 4096) { 
        if (soundRaw < soundMin) soundMin = soundRaw;
        if (soundRaw > soundMax) soundMax = soundRaw;
      }
    }

    int peakToPeak = soundMax - soundMin;
    float volts = ((float)peakToPeak * 3.3f) / 4095.0f; 
    
    float currentSDb = 0.0f;
    if (volts > 0.001f) {
      currentSDb = 20.0f * log10(volts / 0.00005f); 
    }
    if (currentSDb < 0.0f) currentSDb = 0.0f; 

    float currentTempC = bme.readTemperature();    
    float currentPressure = bme.readPressure() / 100.0F; 
    float currentHumidity = bme.readHumidity();        

    FFT.windowing(vRealX, SAMPLES, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
    FFT.compute(vRealX, vImagX, SAMPLES, FFT_FORWARD);
    FFT.complexToMagnitude(vRealX, vImagX, SAMPLES);
    double currentFX = FFT.majorPeak(vRealX, SAMPLES, SAMPLING_FREQ);

    FFT.windowing(vRealY, SAMPLES, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
    FFT.compute(vRealY, vImagY, SAMPLES, FFT_FORWARD);
    FFT.complexToMagnitude(vRealY, vImagY, SAMPLES);
    double currentFY = FFT.majorPeak(vRealY, SAMPLES, SAMPLING_FREQ);

    FFT.windowing(vRealZ, SAMPLES, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
    FFT.compute(vRealZ, vImagZ, SAMPLES, FFT_FORWARD);
    FFT.complexToMagnitude(vRealZ, vImagZ, SAMPLES);
    double currentFZ = FFT.majorPeak(vRealZ, SAMPLES, SAMPLING_FREQ);

    Serial.print(">"); 
    printLocalTimeWithMs(); Serial.print(",");
    Serial.print("Freq_X:"); Serial.print(currentFX); Serial.print(",");
    Serial.print("Freq_Y:"); Serial.print(currentFY); Serial.print(",");
    Serial.print("Freq_Z:"); Serial.print(currentFZ); Serial.print(",");
    Serial.print("Vel_X:");  Serial.print(velX);  Serial.print(",");
    Serial.print("Vel_Y:");  Serial.print(velY);  Serial.print(",");
    Serial.print("Vel_Z:");  Serial.print(velZ);  Serial.print(","); 
    Serial.print("Sound_dB:"); Serial.print(currentSDb); Serial.print(",");
    Serial.print("Temp:");     Serial.print(currentTempC);  Serial.print(",");
    Serial.print("Hum:");      Serial.print(currentHumidity);   Serial.print(",");
    Serial.print("Press:");    Serial.print(currentPressure);
    Serial.println(); 

    time_t nowSecs;
    time(&nowSecs);

    MeasurementRow newRow;
    newRow.timestamp = (unsigned long)nowSecs;
    newRow.fX = currentFX; newRow.fY = currentFY; newRow.fZ = currentFZ;
    newRow.vX = velX; newRow.vY = velY; newRow.vZ = velZ;
    newRow.sDb = currentSDb;
    newRow.temp = currentTempC; newRow.humid = currentHumidity; newRow.press = currentPressure;

    xQueueSend(dataQueue, &newRow, 0);

    vTaskDelay(pdMS_TO_TICKS(340));
  }
}

bool transmitBatch(BatchPacket &packet) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["api_key"] = apiKey;
  JsonArray dataArray = doc["data"].to<JsonArray>();

  for (int i = 0; i < 10; i++) {
    JsonObject row = dataArray.add<JsonObject>();
    row["timestamp"]   = packet.rows[i].timestamp; 
    row["fX"]          = packet.rows[i].fX;
    row["fY"]          = packet.rows[i].fY;
    row["fZ"]          = packet.rows[i].fZ;
    row["vX"]          = packet.rows[i].vX;
    row["vY"]          = packet.rows[i].vY;
    row["vZ"]          = packet.rows[i].vZ;
    row["sDb"]         = packet.rows[i].sDb;
    row["temperature"] = packet.rows[i].temp;
    row["humidity"]    = packet.rows[i].humid;
    row["pressure"]    = packet.rows[i].press;
  }

  String body;
  serializeJson(doc, body);
  int responseCode = http.POST(body);
  http.end();

  return (responseCode >= 200 && responseCode < 300); 
}

void LoggingTask(void *parameter) {
  BatchPacket currentBatch;
  int rowsCollected = 0;

  while(1) {
    MeasurementRow receivedRow;
    
    if (xQueueReceive(dataQueue, &receivedRow, pdMS_TO_TICKS(1000)) == pdPASS) {
      currentBatch.rows[rowsCollected] = receivedRow;
      rowsCollected++;

      if (rowsCollected >= 10) {
        bool success = transmitBatch(currentBatch);

        if (!success) {
          if (backupCount < BACKUP_BUFFER_SIZE) {
            backupBuffer[backupHead] = currentBatch;
            backupHead = (backupHead + 1) % BACKUP_BUFFER_SIZE;
            backupCount++;
            Serial.println("[Offline Storage] Connection lost. Data cached.");
          } else {
            Serial.println("[Offline Storage] Cache Full! Overwriting oldest data.");
            backupTail = (backupTail + 1) % BACKUP_BUFFER_SIZE;
            backupBuffer[backupHead] = currentBatch;
            backupHead = (backupHead + 1) % BACKUP_BUFFER_SIZE;
          }
        }
        rowsCollected = 0; 
      }
    }

    if (backupCount > 0 && WiFi.status() == WL_CONNECTED) {
      Serial.printf("[Recovery] Syncing %d cached packets to InfluxDB...\n", backupCount);
      
      while (backupCount > 0 && WiFi.status() == WL_CONNECTED) {
        if (transmitBatch(backupBuffer[backupTail])) {
          backupTail = (backupTail + 1) % BACKUP_BUFFER_SIZE;
          backupCount--;
          vTaskDelay(pdMS_TO_TICKS(100)); 
        } else {
          Serial.println("[Recovery] Transmission failed mid-sync. Retrying later...");
          break; 
        }
      }
    }

    if (WiFi.status() != WL_CONNECTED) {
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      vTaskDelay(pdMS_TO_TICKS(5000));
    }
  }
}
