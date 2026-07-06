import requests
from geopy.geocoders import Nominatim

class WeatherApp:
    """A simple weather application using Open-Meteo API"""
    
    def __init__(self):
        self.geocoder = Nominatim(user_agent="weather_app")
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        print("Weather app is running...")
    
    def get_coordinates(self, city):
        """Get latitude and longitude from city name"""
        try:
            location = self.geocoder.geocode(city)
            if location:
                return location.latitude, location.longitude
            else:
                print(f"City '{city}' not found")
                return None
        except Exception as e:
            print(f"Error getting coordinates: {e}")
            return None
    
    def get_weather(self, city):
        """Fetch weather data for a given city"""
        coords = self.get_coordinates(city)
        if not coords:
            return None
        
        latitude, longitude = coords
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": True
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching weather data: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def display_weather(self, weather_data, city):
        """Display weather information in a formatted way"""
        if weather_data:
            current_weather = weather_data.get('current_weather', {})
            temperature = current_weather.get('temperature')
            windspeed = current_weather.get('windspeed')
            winddirection = current_weather.get('winddirection')
            time = current_weather.get('time')
            
            print("\n" + "="*40)
            print("Weather Data")
            print("="*40)
            print(f"City: {city}")
            print(f"Current Temperature: {temperature}°C")
            print(f"Current Windspeed: {windspeed} m/s")
            print(f"Current Wind Direction: {winddirection}°")
            print(f"Current Time: {time}")
            print("="*40 + "\n")
        else:
            print("No weather data to display")
    
    def run(self):
        """Main application flow"""
        city = input("Enter the city name to get current weather: ")
        weather_data = self.get_weather(city)
        self.display_weather(weather_data, city)

if __name__ == "__main__":
    app = WeatherApp()
    app.run()
            
            
            
            