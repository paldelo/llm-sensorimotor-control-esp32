#include <WiFi.h>
#include <WebServer.h>

// Replace with your local 2.4 GHz Wi-Fi credentials
const char* SSID = "YOUR_WIFI_SSID";
const char* PASSWORD = "YOUR_WIFI_PASSWORD";

WebServer server(80);

// Pin mapping (L298N H-bridge driver and TCRT5000 IR sensor array)
const int PIN_MOTOR_ESQ_ENA = 14;
const int PIN_MOTOR_ESQ_IN1 = 26;
const int PIN_MOTOR_ESQ_IN2 = 27;
const int PIN_MOTOR_DIR_IN3 = 32;
const int PIN_MOTOR_DIR_IN4 = 33;
const int PIN_MOTOR_DIR_ENB = 25;
const int PIN_SENSOR_ESQ = 34;
const int PIN_SENSOR_DIR = 35;

// PWM signal configuration (5000 Hz, 8-bit resolution: 0 to 255)
const int PWM_FREQ = 5000;
const int PWM_RESOLUTION = 8;

// Electromechanical parameters for linear translation (symmetric calibration)
const int PWM_RETO_ESQ = 160;
const int PWM_RETO_DIR = 160;

// Electromechanical parameters for differential rotation
const int PWM_GIRO_ESQ = 195;
const int PWM_GIRO_DIR = 195;
const int PWM_IMPULSO_GIRO = 235;

// Retained state for edge-detection interruption during discrete steps
int leituraRetidaEsq = 1;
int leituraRetidaDir = 1;
bool possuiLeituraRetida = false;

void aplicarPotenciaMotores(int velEsq, int velDir) {
  if (velEsq > 0) {
    digitalWrite(PIN_MOTOR_ESQ_IN1, HIGH);
    digitalWrite(PIN_MOTOR_ESQ_IN2, LOW);
  } else if (velEsq < 0) {
    digitalWrite(PIN_MOTOR_ESQ_IN1, LOW);
    digitalWrite(PIN_MOTOR_ESQ_IN2, HIGH);
  } else {
    digitalWrite(PIN_MOTOR_ESQ_IN1, LOW);
    digitalWrite(PIN_MOTOR_ESQ_IN2, LOW);
  }
  ledcWrite(PIN_MOTOR_ESQ_ENA, abs(velEsq));

  if (velDir > 0) {
    digitalWrite(PIN_MOTOR_DIR_IN3, HIGH);
    digitalWrite(PIN_MOTOR_DIR_IN4, LOW);
  } else if (velDir < 0) {
    digitalWrite(PIN_MOTOR_DIR_IN3, LOW);
    digitalWrite(PIN_MOTOR_DIR_IN4, HIGH);
  } else {
    digitalWrite(PIN_MOTOR_DIR_IN3, LOW);
    digitalWrite(PIN_MOTOR_DIR_IN4, LOW);
  }
  ledcWrite(PIN_MOTOR_DIR_ENB, abs(velDir));
}

void handleSensores() {
  int esq = digitalRead(PIN_SENSOR_ESQ);
  int dir = digitalRead(PIN_SENSOR_DIR);

  if (possuiLeituraRetida) {
    esq = leituraRetidaEsq;
    dir = leituraRetidaDir;
    possuiLeituraRetida = false;
  }

  String payload = "{\"esq\": " + String(esq) + ", \"dir\": " + String(dir) + "}";
  server.send(200, "application/json", payload);
}

void handleMover() {
  if (!server.hasArg("e") || !server.hasArg("d")) {
    server.send(400, "text/plain", "Invalid parameters");
    return;
  }

  int cmdEsq = server.arg("e").toInt();
  int cmdDir = server.arg("d").toInt();

  int sinalEsq = (cmdEsq > 0) ? 1 : ((cmdEsq < 0) ? -1 : 0);
  int sinalDir = (cmdDir > 0) ? 1 : ((cmdDir < 0) ? -1 : 0);
  bool manobraRotacional = (sinalEsq * sinalDir < 0);

  int esqInicial = digitalRead(PIN_SENSOR_ESQ);
  int dirInicial = digitalRead(PIN_SENSOR_DIR);
  bool iniciouAlinhado = (esqInicial == 1 && dirInicial == 1);
  possuiLeituraRetida = false;

  if (manobraRotacional) {
    // 60 ms initial boost to overcome caster-wheel static friction
    aplicarPotenciaMotores(sinalEsq * PWM_IMPULSO_GIRO, sinalDir * PWM_IMPULSO_GIRO);
    delay(60);

    // Sustained rotation with 5 ms realignment sampling (up to 400 ms)
    aplicarPotenciaMotores(sinalEsq * PWM_GIRO_ESQ, sinalDir * PWM_GIRO_DIR);
    for (int i = 0; i < 80; i++) {
      delay(5);
      int eAtual = digitalRead(PIN_SENSOR_ESQ);
      int dAtual = digitalRead(PIN_SENSOR_DIR);

      if (!iniciouAlinhado && eAtual == 1 && dAtual == 1) {
        delay(25);
        leituraRetidaEsq = 1;
        leituraRetidaDir = 1;
        possuiLeituraRetida = true;
        break;
      }
    }
  } else {
    // Linear translation with 5 ms edge sampling (up to 350 ms)
    aplicarPotenciaMotores(sinalEsq * PWM_RETO_ESQ, sinalDir * PWM_RETO_DIR);
    for (int i = 0; i < 70; i++) {
      delay(5);
      int eAtual = digitalRead(PIN_SENSOR_ESQ);
      int dAtual = digitalRead(PIN_SENSOR_DIR);

      if (iniciouAlinhado && (eAtual == 0 || dAtual == 0)) {
        leituraRetidaEsq = eAtual;
        leituraRetidaDir = dAtual;
        possuiLeituraRetida = true;
        break;
      }
    }
  }

  aplicarPotenciaMotores(0, 0);
  server.send(200, "text/plain", "OK");
}

void handleParar() {
  aplicarPotenciaMotores(0, 0);
  server.send(200, "text/plain", "OK");
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_MOTOR_ESQ_IN1, OUTPUT);
  pinMode(PIN_MOTOR_ESQ_IN2, OUTPUT);
  pinMode(PIN_MOTOR_DIR_IN3, OUTPUT);
  pinMode(PIN_MOTOR_DIR_IN4, OUTPUT);
  pinMode(PIN_SENSOR_ESQ, INPUT);
  pinMode(PIN_SENSOR_DIR, INPUT);

  ledcAttach(PIN_MOTOR_ESQ_ENA, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(PIN_MOTOR_DIR_ENB, PWM_FREQ, PWM_RESOLUTION);

  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
  }

  Serial.print("ESP32 connected. Local IP: ");
  Serial.println(WiFi.localIP());

  server.on("/sensores", HTTP_GET, handleSensores);
  server.on("/mover", HTTP_GET, handleMover);
  server.on("/parar", HTTP_GET, handleParar);
  server.begin();
}

void loop() {
  server.handleClient();
}