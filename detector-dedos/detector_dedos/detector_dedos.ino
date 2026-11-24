/*
  DETECTOR DE DEDOS - Arduino Uno + OLED SSD1306 128x64 (I2C)
  ------------------------------------------------------------
  Un sensor flex por dedo. La pantalla muestra el nombre del dedo levantado.

  Libreria necesaria: "U8g2" de oliver
  (Arduino IDE > Herramientas > Administrar bibliotecas > buscar U8g2)

  CONEXIONES
    Sensor flex pulgar   -> A0
    Sensor flex indice   -> A1
    Sensor flex medio    -> A2
    Sensor flex anular   -> A3
    Sensor flex menique  -> A4
    (cada sensor: una pata a 5V, la otra a su pin analogico
     y a una resistencia de 10k que va a GND)

    OLED VCC -> 5V
    OLED GND -> GND
    OLED SCL -> D2
    OLED SDA -> D3
    (la OLED va por I2C por software porque A4 lo usa el menique)
*/

#include <Arduino.h>
#include <U8g2lib.h>

// ---------- Pantalla ----------
const uint8_t PIN_SCL = 2;
const uint8_t PIN_SDA = 3;

// U8G2_R2 = imagen girada 180 grados (la OLED va con los pines hacia abajo
// en la protoboard). Si el texto te sale de cabeza, cambia U8G2_R2 por U8G2_R0.
U8G2_SSD1306_128X64_NONAME_1_SW_I2C oled(U8G2_R2, PIN_SCL, PIN_SDA, U8X8_PIN_NONE);

// ---------- Dedos ----------
const uint8_t NUM_DEDOS = 5;
const uint8_t PIN_DEDO[NUM_DEDOS] = {A0, A1, A2, A3, A4};
const char *const NOMBRE[NUM_DEDOS] = {"PULGAR", "ÍNDICE", "MEDIO", "ANULAR", "MEÑIQUE"};

// Un dedo pasa a "levantado" sobre 60% y a "doblado" bajo 40%.
// La zona intermedia evita que el nombre parpadee.
const int UMBRAL_SUBE = 60;
const int UMBRAL_BAJA = 40;

int valorAbierto[NUM_DEDOS];   // lectura con el dedo estirado
int valorCerrado[NUM_DEDOS];   // lectura con el dedo doblado
bool levantado[NUM_DEDOS];
bool levantadoAntes[NUM_DEDOS];

// Promedia varias lecturas para quitar ruido
int leerDedo(uint8_t i) {
  long suma = 0;
  for (uint8_t n = 0; n < 8; n++) {
    suma += analogRead(PIN_DEDO[i]);
  }
  return suma / 8;
}

// 0 = dedo doblado, 100 = dedo estirado
int porcentaje(uint8_t i) {
  int rango = valorAbierto[i] - valorCerrado[i];
  if (abs(rango) < 15) {
    return 0;   // sensor desconectado o mal calibrado
  }
  long p = (long)(leerDedo(i) - valorCerrado[i]) * 100L / rango;
  return constrain(p, 0, 100);
}

// Dibuja la pantalla: titulo en la franja amarilla, texto grande en la azul
// y abajo una barra por dedo (alta = levantado).
void dibujar(const char *titulo, const char *texto, bool conBarras) {
  oled.firstPage();
  do {
    oled.setFont(u8g2_font_6x12_tf);
    oled.drawUTF8((128 - oled.getUTF8Width(titulo)) / 2, 12, titulo);

    oled.setFont(u8g2_font_helvB14_tf);
    oled.drawUTF8((128 - oled.getUTF8Width(texto)) / 2, conBarras ? 38 : 46, texto);

    if (conBarras) {
      for (uint8_t i = 0; i < NUM_DEDOS; i++) {
        uint8_t alto = levantado[i] ? 18 : 4;
        oled.drawBox(8 + i * 24, 64 - alto, 16, alto);
      }
    }
  } while (oled.nextPage());
}

// Muestra una instruccion, espera y guarda la lectura de cada dedo
void medir(const char *instruccion, int destino[]) {
  dibujar("CALIBRANDO", instruccion, false);
  delay(2500);
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    destino[i] = leerDedo(i);
  }
}

void calibrar() {
  medir("ABRE", valorAbierto);     // mano abierta, dedos estirados
  medir("CIERRA", valorCerrado);   // puno cerrado
  dibujar("CALIBRANDO", "LISTO", false);
  delay(800);

  Serial.println(F("Calibracion (abierto / cerrado):"));
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    Serial.print(NOMBRE[i]);
    Serial.print(F(": "));
    Serial.print(valorAbierto[i]);
    Serial.print(F(" / "));
    Serial.println(valorCerrado[i]);
  }
}

void mostrarEstado() {
  uint8_t cuantos = 0;
  uint8_t ultimo = 0;
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    if (levantado[i]) {
      cuantos++;
      ultimo = i;
    }
  }

  char texto[12];
  if (cuantos == 0) {
    dibujar("NINGUN DEDO", "PUÑO", true);
  } else if (cuantos == 1) {
    dibujar("DEDO LEVANTADO", NOMBRE[ultimo], true);
  } else if (cuantos == NUM_DEDOS) {
    dibujar("DEDOS LEVANTADOS", "TODOS", true);
  } else {
    snprintf(texto, sizeof(texto), "%u DEDOS", cuantos);
    dibujar("DEDOS LEVANTADOS", texto, true);
  }

  // Lo mismo por el monitor serie (9600 baudios)
  Serial.print(F("Levantados:"));
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    if (levantado[i]) {
      Serial.print(' ');
      Serial.print(NOMBRE[i]);
    }
  }
  Serial.println();
}

void setup() {
  Serial.begin(9600);
  oled.begin();
  calibrar();   // para calibrar de nuevo, presiona RESET en el Arduino
  mostrarEstado();
}

void loop() {
  bool cambio = false;

  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    int p = porcentaje(i);
    if (p >= UMBRAL_SUBE) {
      levantado[i] = true;
    } else if (p <= UMBRAL_BAJA) {
      levantado[i] = false;
    }
    if (levantado[i] != levantadoAntes[i]) {
      levantadoAntes[i] = levantado[i];
      cambio = true;
    }
  }

  // Solo redibuja cuando algo cambia: la pantalla por software es lenta
  if (cambio) {
    mostrarEstado();
  }
  delay(30);
}
