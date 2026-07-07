import requests
import time

def search_places(query: str):
    """
    Searches for places using the free OpenStreetMap Nominatim API.
    No API Key required!
    """
    try:
        # Nominatim requires a small delay between requests
        time.sleep(1)
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 8,
            "addressdetails": 1,
            "extratags": 1
        }
        headers = {
            "User-Agent": "TripMateAI/2.0 (Educational Project)",
            "Accept": "application/json"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        # Check if response is valid
        if response.status_code != 200:
            return f"Map API returned status {response.status_code}. Using AI knowledge for places instead."
        
        # Check if response has content
        if not response.text or response.text.strip() == "":
            return f"No map data returned for '{query}'. The AI will use its own knowledge for tourist attractions."
            
        data = response.json()
        
        if data and len(data) > 0:
            output = f"Top Places & Attractions for '{query}':\n"
            for i, place in enumerate(data, 1):
                name = place.get("name", "")
                if not name:
                    name = place.get("display_name", "").split(",")[0]
                    
                address = place.get("display_name", "No address")
                place_type = place.get("type", "place").replace("_", " ").title()
                
                output += f"{i}. {name} ({place_type}) - {address}\n"
            return output
        
        return f"No specific places found for '{query}'. The AI will recommend popular tourist spots based on its knowledge."
    except requests.exceptions.JSONDecodeError:
        return f"Map data parsing failed for '{query}'. The AI will use its knowledge for recommendations."
    except Exception as e:
        return f"Map search encountered an issue: {str(e)}. The AI will use its knowledge for places."

if __name__ == "__main__":
    print(search_places("tourist attractions in Paris"))
