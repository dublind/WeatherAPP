#meaking the weather app

#making the weather app

from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# ========================================
# PUT YOUR API KEY HERE:
API_KEY = "c4b7e7b3343675d5062be8406e137fb4"
# ========================================

# OpenWeatherMap API endpoints
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
AIR_QUALITY_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

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
                    
                    # Get air quality data
                    lat = data['coord']['lat']
                    lon = data['coord']['lon']
                    air_params = {
                        'lat': lat,
                        'lon': lon,
                        'appid': API_KEY
                    }
                    air_response = requests.get(AIR_QUALITY_URL, params=air_params)
                    
                    air_quality_data = None
                    if air_response.status_code == 200:
                        air_data = air_response.json()
                        aqi = air_data['list'][0]['main']['aqi']
                        components = air_data['list'][0]['components']
                        
                        # AQI levels: 1=Bueno, 2=Regular, 3=Moderado, 4=Malo, 5=Muy Malo
                        aqi_labels = {
                            1: {'label': 'Bueno', 'color': '#a8e6cf'},
                            2: {'label': 'Regular', 'color': '#ffd89b'},
                            3: {'label': 'Moderado', 'color': '#ffb88c'},
                            4: {'label': 'Malo', 'color': '#ff8b94'},
                            5: {'label': 'Muy Malo', 'color': '#c3a5d4'}
                        }
                        
                        air_quality_data = {
                            'aqi': aqi,
                            'label': aqi_labels[aqi]['label'],
                            'color': aqi_labels[aqi]['color'],
                            'pm2_5': round(components.get('pm2_5', 0), 1),
                            'pm10': round(components.get('pm10', 0), 1),
                            'co': round(components.get('co', 0), 1),
                            'no2': round(components.get('no2', 0), 1),
                            'o3': round(components.get('o3', 0), 1)
                        }
                    
                    weather_data = {
                        'city': data['name'],
                        'temperature': round(data['main']['temp']),
                        'description': data['weather'][0]['description'],
                        'humidity': data['main']['humidity'],
                        'wind_speed': data['wind']['speed'],
                        'icon': data['weather'][0]['icon'],
                        'air_quality': air_quality_data
                    }
                else:
                    error = "Ciudad no encontrada. Intenta con otra ciudad chilena."
            except Exception as e:
                error = "Error al obtener datos del clima. Verifica tu API key."
        else:
            error = "Por favor ingresa una ciudad."

    return render_template('index.html', weather=weather_data, error=error)

@app.route('/weather-by-coords')
def weather_by_coords():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if lat and lon:
        params = {
            'lat': lat,
            'lon': lon,
            'appid': API_KEY,
            'units': 'metric',
            'lang': 'es'
        }
        
        try:
            response = requests.get(BASE_URL, params=params)
            if response.status_code == 200:
                data = response.json()
                return {'success': True, 'city': data['name']}
        except:
            pass
    
    return {'success': False}

if __name__ == '__main__':
    app.run(debug=True)
