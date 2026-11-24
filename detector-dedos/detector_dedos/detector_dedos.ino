/*
  DETECTOR DE DEDOS - Arduino Uno + OLED SSD1306 128x64 + 5 LEDs
  ---------------------------------------------------------------
  La camara y Python (OpenCV) detectan que dedos estan levantados y se lo
  mandan al Arduino por el cable USB. El Arduino enciende un LED por dedo
  y muestra el nombre en la pantalla.

  Libreria necesaria: "U8g2" de oliver
  (Arduino IDE > Herramientas > Administrar bibliotecas > buscar U8g2)

  CONEXIONES
    LED pulgar   -> D2
    LED indice   -> D3
    LED medio    -> D4
    LED anular   -> D5
    LED menique  -> D6
    (pata larga del LED al pin; pata corta a una resistencia de 220 ohm
     que va a GND)

    OLED VCC -> 5V
    OLED GND -> GND
    OLED SDA -> A4
    OLED SCL -> A5

  MENSAJES QUE LLEGAN DESDE PYTHON (9600 baudios, terminados en salto de linea)
    "01000"  cinco caracteres, uno por dedo (pulgar..menique): 1 = levantado
    "N"      no se ve ninguna mano
*/

#include <Arduino.h>

// Pon 0 si todavia NO tienes la pantalla OLED conectada: el proyecto funciona
// solo con los LEDs (y no hace falta instalar U8g2). Pon 1 cuando la conectes.
#define USAR_PANTALLA 1

#if USAR_PANTALLA
#include <Wire.h>
#include <U8g2lib.h>

// U8G2_R2 = imagen girada 180 grados (la OLED va con los pines hacia abajo
// en la protoboard). Si el texto te sale de cabeza, cambia U8G2_R2 por U8G2_R0.
U8G2_SSD1306_128X64_NONAME_1_HW_I2C oled(U8G2_R2, U8X8_PIN_NONE);
#endif

const uint8_t NUM_DEDOS = 5;
const uint8_t PIN_LED[NUM_DEDOS] = {2, 3, 4, 5, 6};
const char *const NOMBRE[NUM_DEDOS] = {"PULGAR", "ÍNDICE", "MEDIO", "ANULAR", "MEÑIQUE"};

// Si Python deja de hablar por este tiempo, se apagan los LEDs
const unsigned long TIEMPO_SIN_DATOS = 3000;

bool levantado[NUM_DEDOS];
bool hayMano = false;
bool conectado = false;
unsigned long ultimoMensaje = 0;

char linea[8];
uint8_t largo = 0;

// Titulo en la franja amarilla, texto grande en la azul
// y abajo una barra por dedo (alta = levantado).
void dibujar(const char *titulo, const char *texto) {
#if USAR_PANTALLA
  oled.firstPage();
  do {
    oled.setFont(u8g2_font_6x12_tf);
    oled.drawUTF8((128 - oled.getUTF8Width(titulo)) / 2, 12, titulo);

    oled.setFont(u8g2_font_helvB14_tf);
    oled.drawUTF8((128 - oled.getUTF8Width(texto)) / 2, 38, texto);

    for (uint8_t i = 0; i < NUM_DEDOS; i++) {
      uint8_t alto = levantado[i] ? 18 : 4;
      oled.drawBox(8 + i * 24, 64 - alto, 16, alto);
    }
  } while (oled.nextPage());
#else
  (void)titulo;   // sin pantalla no hay nada que dibujar
  (void)texto;
#endif
}

void mostrarEstado() {
  uint8_t cuantos = 0;
  uint8_t ultimo = 0;
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    digitalWrite(PIN_LED[i], levantado[i] ? HIGH : LOW);
    if (levantado[i]) {
      cuantos++;
      ultimo = i;
    }
  }

  char texto[12];
  if (!conectado) {
    dibujar("ESPERANDO A PYTHON", "SIN DATOS");
  } else if (!hayMano) {
    dibujar("MUESTRA TU MANO", "SIN MANO");
  } else if (cuantos == 0) {
    dibujar("NINGUN DEDO", "PUÑO");
  } else if (cuantos == 1) {
    dibujar("DEDO LEVANTADO", NOMBRE[ultimo]);
  } else if (cuantos == NUM_DEDOS) {
    dibujar("DEDOS LEVANTADOS", "TODOS");
  } else {
    snprintf(texto, sizeof(texto), "%u DEDOS", cuantos);
    dibujar("DEDOS LEVANTADOS", texto);
  }
}

void apagarTodo() {
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    levantado[i] = false;
  }
}

// Interpreta una linea completa. Devuelve true si cambio algo.
bool procesarLinea() {
  bool nuevo[NUM_DEDOS] = {false, false, false, false, false};
  bool nuevaMano;

  if (largo == 1 && linea[0] == 'N') {
    nuevaMano = false;
  } else if (largo == NUM_DEDOS) {
    for (uint8_t i = 0; i < NUM_DEDOS; i++) {
      if (linea[i] != '0' && linea[i] != '1') {
        return false;   // linea con basura: se ignora
      }
      nuevo[i] = (linea[i] == '1');
    }
    nuevaMano = true;
  } else {
    return false;
  }

  ultimoMensaje = millis();
  bool cambio = !conectado || (nuevaMano != hayMano);
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    if (nuevo[i] != levantado[i]) {
      cambio = true;
    }
    levantado[i] = nuevo[i];
  }
  hayMano = nuevaMano;
  conectado = true;
  return cambio;
}

void setup() {
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    pinMode(PIN_LED[i], OUTPUT);
  }
  Serial.begin(9600);
#if USAR_PANTALLA
  oled.begin();
#endif

  // Prueba de LEDs: se encienden uno por uno al arrancar
  for (uint8_t i = 0; i < NUM_DEDOS; i++) {
    digitalWrite(PIN_LED[i], HIGH);
    delay(120);
    digitalWrite(PIN_LED[i], LOW);
  }
  mostrarEstado();
}

void loop() {
  bool cambio = false;

  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      if (procesarLinea()) {
        cambio = true;
      }
      largo = 0;
    } else if (c != '\r') {
      if (largo < sizeof(linea) - 1) {
        linea[largo] = c;
      }
      if (largo < 255) {
        largo++;   // una linea demasiado larga queda con largo invalido y se ignora
      }
    }
  }

  if (conectado && millis() - ultimoMensaje > TIEMPO_SIN_DATOS) {
    conectado = false;
    hayMano = false;
    apagarTodo();
    cambio = true;
  }

  // Solo redibuja cuando algo cambia
  if (cambio) {
    mostrarEstado();
  }
}
