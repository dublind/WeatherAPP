"""
DETECTOR DE DEDOS - parte de Python

Lee la camara con OpenCV, detecta la mano con MediaPipe y le manda al Arduino
que dedos estan levantados. El Arduino enciende un LED por dedo y muestra el
nombre en la pantalla OLED.

La primera vez descarga el modelo de la mano (hand_landmarker.task, 8 MB)
y lo guarda junto a este archivo, asi que necesita internet esa vez.

Instalar:   pip install -r requirements.txt
Ejecutar:   python detector_dedos.py
            python detector_dedos.py --puerto COM3      (Windows)
            python detector_dedos.py --puerto /dev/ttyACM0   (Linux)
Salir:      tecla Q sobre la ventana de video

IMPORTANTE: cierra el Monitor Serie del Arduino IDE antes de ejecutar,
porque el puerto solo puede usarlo un programa a la vez.
"""

import argparse
import math
import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import serial
from serial.tools import list_ports

NOMBRES = ["PULGAR", "INDICE", "MEDIO", "ANULAR", "MENIQUE"]
BAUDIOS = 9600
CUADROS_ESTABLES = 3      # el estado debe repetirse estos cuadros antes de enviarse
SEGUNDOS_REENVIO = 1.0    # se reenvia cada segundo para que el Arduino sepa que seguimos aqui

MODELO = Path(__file__).with_name("hand_landmarker.task")
URL_MODELO = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

# Lineas que unen los 21 puntos de la mano (para dibujarla sobre el video)
HUESOS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

# Puntos de la mano segun MediaPipe
MUNECA = 0
PULGAR_NUDILLO, PULGAR_PUNTA = 3, 4
BASE_MENIQUE = 17
# (punta, articulacion media) de indice, medio, anular y menique
DEDOS_LARGOS = [(8, 6), (12, 10), (16, 14), (20, 18)]


def distancia(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def dedos_levantados(puntos):
    """Devuelve 5 valores True/False: pulgar, indice, medio, anular, menique.

    Compara distancias en vez de alturas, asi funciona aunque la mano
    este inclinada y con cualquiera de las dos manos.
    """
    muneca = puntos[MUNECA]
    base_menique = puntos[BASE_MENIQUE]

    # Pulgar: estirado si la punta se aleja del borde opuesto de la palma
    estado = [
        distancia(puntos[PULGAR_PUNTA], base_menique)
        > distancia(puntos[PULGAR_NUDILLO], base_menique)
    ]
    # Resto: estirado si la punta queda mas lejos de la muneca que su articulacion
    for punta, media in DEDOS_LARGOS:
        estado.append(distancia(puntos[punta], muneca) > distancia(puntos[media], muneca))
    return estado


def a_mensaje(estado):
    """None = sin mano -> 'N'.  Lista de 5 -> por ejemplo '01000'."""
    if estado is None:
        return "N"
    return "".join("1" if e else "0" for e in estado)


def crear_detector():
    if not MODELO.exists():
        print("Descargando el modelo de la mano (solo la primera vez)...")
        urllib.request.urlretrieve(URL_MODELO, MODELO)
    vision = mp.tasks.vision
    opciones = vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELO)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    return vision.HandLandmarker.create_from_options(opciones)


def dibujar_mano(cuadro, puntos):
    alto, ancho = cuadro.shape[:2]
    pix = [(int(p.x * ancho), int(p.y * alto)) for p in puntos]
    for a, b in HUESOS:
        cv2.line(cuadro, pix[a], pix[b], (255, 255, 255), 2)
    for punto in pix:
        cv2.circle(cuadro, punto, 4, (0, 200, 255), -1)


def buscar_puerto():
    """Busca un puerto que parezca un Arduino."""
    pistas = ("arduino", "ch340", "usb serial", "usb-serial", "ttyacm", "ttyusb", "usbmodem")
    for p in list_ports.comports():
        texto = f"{p.device} {p.description} {p.manufacturer or ''}".lower()
        if any(pista in texto for pista in pistas):
            return p.device
    return None


def abrir_arduino(puerto):
    puerto = puerto or buscar_puerto()
    if puerto is None:
        print("No encontre el Arduino. Sigo solo con la camara.")
        print("Puertos disponibles:", [p.device for p in list_ports.comports()] or "ninguno")
        print("Puedes indicarlo con:  --puerto COM3")
        return None
    try:
        arduino = serial.Serial(puerto, BAUDIOS, timeout=0, write_timeout=1)
    except serial.SerialException as error:
        print(f"No pude abrir {puerto}: {error}")
        print("Revisa que el Monitor Serie del Arduino IDE este cerrado. Sigo solo con la camara.")
        return None
    print(f"Arduino conectado en {puerto}. Esperando a que reinicie...")
    time.sleep(2)   # el Uno se reinicia cuando se abre el puerto
    return arduino


def main():
    parser = argparse.ArgumentParser(description="Detecta dedos levantados y avisa al Arduino")
    parser.add_argument("--puerto", help="puerto serie del Arduino (ej: COM3 o /dev/ttyACM0)")
    parser.add_argument("--camara", type=int, default=0, help="numero de camara (0 = la principal)")
    args = parser.parse_args()

    arduino = abrir_arduino(args.puerto)

    camara = cv2.VideoCapture(args.camara)
    if not camara.isOpened():
        raise SystemExit(f"No pude abrir la camara {args.camara}. Prueba con --camara 1")

    detector = crear_detector()
    inicio = time.monotonic()

    candidato, repeticiones = None, 0
    enviado, ultimo_envio = None, 0.0

    try:
        while True:
            ok, cuadro = camara.read()
            if not ok:
                print("La camara dejo de entregar imagen.")
                break

            cuadro = cv2.flip(cuadro, 1)   # efecto espejo
            imagen = mp.Image(
                image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)
            )
            milisegundos = int((time.monotonic() - inicio) * 1000)
            resultado = detector.detect_for_video(imagen, milisegundos)

            estado = None
            if resultado.hand_landmarks:
                puntos = resultado.hand_landmarks[0]
                dibujar_mano(cuadro, puntos)
                estado = dedos_levantados(puntos)

            # Filtro: el mensaje debe repetirse unos cuadros para evitar parpadeos
            mensaje = a_mensaje(estado)
            if mensaje == candidato:
                repeticiones += 1
            else:
                candidato, repeticiones = mensaje, 1

            ahora = time.time()
            estable = repeticiones >= CUADROS_ESTABLES
            if estable and (candidato != enviado or ahora - ultimo_envio > SEGUNDOS_REENVIO):
                if candidato != enviado:
                    print("Enviado:", candidato)
                enviado, ultimo_envio = candidato, ahora
                if arduino is not None:
                    try:
                        arduino.write((candidato + "\n").encode("ascii"))
                    except serial.SerialException as error:
                        print(f"Se perdio la conexion con el Arduino: {error}")
                        arduino = None

            # Texto sobre el video
            if estado is None:
                texto = "Sin mano"
            else:
                arriba = [NOMBRES[i] for i, e in enumerate(estado) if e]
                texto = ", ".join(arriba) if arriba else "Puno"
            cv2.putText(cuadro, texto, (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 5)
            cv2.putText(cuadro, texto, (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

            cv2.imshow("Detector de dedos (Q para salir)", cuadro)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    finally:
        camara.release()
        cv2.destroyAllWindows()
        detector.close()
        if arduino is not None:
            try:
                arduino.write(b"N\n")
                arduino.close()
            except serial.SerialException:
                pass


if __name__ == "__main__":
    main()
