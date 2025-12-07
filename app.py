#making the weather app

from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# ========================================
# PUT YOUR API KEY HERE:
API_KEY = "YOUR_API_KEY_HERE"
# ========================================

# OpenWeatherMap API endpoint
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

@app.route('/', methods=['GET', 'POST'])
def Weather():
    weather_data = None
    error = None

    if request.method == 'POST':
        city = request.form.get('city')

        if city:
            # Make API request
            params = {
                'q': f'{city},CL',  # CL for Chile
                'appid': API_KEY,
                'units': 'metric',  # Celsius
                'lang': 'es'  # Spanish
            }

            try:
                response = requests.get(BASE_URL, params=params)

                if response.status_code == 200:
                    data = response.json()
                    weather_data = {
                        'city': data['name'],
                        'temperature': round(data['main']['temp']),
                        'description': data['weather'][0]['description'],
                        'humidity': data['main']['humidity'],
                        'wind_speed': data['wind']['speed'],
                        'icon': data['weather'][0]['icon']
                    }
                else:
                    error = "Ciudad no encontrada. Intenta con otra ciudad chilena."
            except Exception as e:
                error = "Error al obtener datos del clima. Verifica tu API key."
        else:
            error = "Por favor ingresa una ciudad."

    return render_template('index.html', weather=weather_data, error=error)

if __name__ == '__main__':
    app.run(debug=True)



