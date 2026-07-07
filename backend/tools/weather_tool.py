import requests

def get_coordinates(city: str):
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city, "count": 1, "language": "en", "format": "json"}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            return result["latitude"], result["longitude"], result.get("country", "")
        return None, None, None
    except Exception:
        return None, None, None

def get_weather(location: str):
    lat, lon, country = get_coordinates(location)
    
    if lat is None or lon is None:
        return f"Could not find coordinates for {location} to fetch weather."
        
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "timezone": "auto"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if "current_weather" in data:
            current = data["current_weather"]
            temp = current.get("temperature", "Unknown")
            windspeed = current.get("windspeed", "Unknown")
            return f"Current weather in {location} ({country}): {temp}°C, Wind Speed: {windspeed} km/h."
        return f"Weather data not available for {location}."
    except Exception as e:
        return f"Error fetching weather: {e}"

if __name__ == "__main__":
    print(get_weather("Delhi"))
