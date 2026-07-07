import os 
import certifi
import requests
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated, Optional
import operator
import uuid

from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from tools.weather_tool import get_weather, get_coordinates
from tools.currency_tool import get_exchange_rate
from tools.map_tool import search_places

# =========================
# Multi-LLM Factory
# =========================
def get_llm(provider: str = "groq"):
    """Returns an LLM instance based on the selected provider."""
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing. Add it to .env")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.3)
    
    elif provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing. Add it to .env")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key, temperature=0.3)
    
    else:  # Default: groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing. Add it to .env")
        return ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key, temperature=0.3)

# We will instantiate LLMs dynamically at runtime to avoid crash on startup if API keys are missing


# =========================
# Destination Image (Wikipedia API - FREE)
# =========================
def fetch_destination_image(destination: str) -> str:
    """Fetches a destination image from Wikipedia. Completely free, no API key needed."""
    try:
        headers = {"User-Agent": "TripMateAI/2.0"}
        # First, search for the most relevant page (avoids disambiguation pages like "Manali")
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={destination} tourism&utf8=&format=json"
        search_res = requests.get(search_url, headers=headers, timeout=5)
        if search_res.status_code == 200:
            search_data = search_res.json()
            if search_data.get("query", {}).get("search"):
                best_title = search_data["query"]["search"][0]["title"]
                
                # Fetch summary and image for best_title
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{best_title}"
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # Try originalimage first (higher quality), then thumbnail
                    if "originalimage" in data:
                        return data["originalimage"]["source"]
                    elif "thumbnail" in data:
                        return data["thumbnail"]["source"]
    except Exception as e:
        print(f"Error fetching image: {e}")
    return ""

# =========================
# Structured Output Schema
# =========================
class DayPlan(BaseModel):
    day: int = Field(description="Day number")
    title: str = Field(description="Brief title for the day's activities")
    activities: list[str] = Field(description="List of activities for the day")

class FlightInfo(BaseModel):
    airline: str
    flight_number: str
    departure: str
    arrival: str
    status: str

class TravelPlan(BaseModel):
    trip_summary: str = Field(description="A brief engaging summary of the trip")
    weather_info: str = Field(description="Expected weather during the trip")
    exchange_rates: str = Field(description="Relevant exchange rates")
    flights: list[FlightInfo] = Field(description="List of recommended flights")
    hotels_and_places: list[str] = Field(description="Recommended hotels and attractions")
    itinerary: list[DayPlan] = Field(description="Day by day itinerary")
    estimated_budget: str = Field(description="Estimated budget for the trip")

# =========================
# State
# =========================
class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    destination: str
    destination_image: str      # Wikipedia image URL
    destination_lat: float      # Latitude for map
    destination_lon: float      # Longitude for map
    language: str               # Response language
    llm_provider: str           # groq / openai / gemini
    flight_results: str
    hotel_results: str
    weather_results: str
    currency_results: str
    map_results: str
    user_profile: str
    final_plan: Optional[TravelPlan]
    llm_calls: int

# =========================
# Agents
# =========================

def _get_active_llm(state: TravelState):
    """Gets the LLM based on the user's selection in state."""
    provider = state.get("llm_provider", "groq")
    try:
        return get_llm(provider)
    except Exception:
        return get_llm("groq")  # Fallback to Groq at runtime

def profile_agent(state: TravelState):
    """Extracts user preferences, destination city, image, and coordinates."""
    llm = _get_active_llm(state)
    
    prompt = f"""From this travel query, extract TWO things:
1. User preferences (e.g. vegetarian, budget traveler, prefers window seat). If none found, say 'None'.
2. The main DESTINATION CITY name only (e.g. 'Paris', 'Tokyo', 'Goa', 'London'). Just the city name, nothing else.

Format your response EXACTLY like this:
PREFERENCES: <preferences here>
DESTINATION: <city name here>

Query: {state['user_query']}"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    
    destination = ""
    preferences = ""
    for line in content.split("\n"):
        line = line.strip()
        if line.upper().startswith("DESTINATION:"):
            destination = line.split(":", 1)[1].strip()
        elif line.upper().startswith("PREFERENCES:"):
            preferences = line.split(":", 1)[1].strip()
    
    if not destination:
        destination = state["user_query"]
    
    # Fetch destination image from Wikipedia
    image_url = fetch_destination_image(destination)
    
    # Fetch coordinates for interactive map
    lat, lon, country = get_coordinates(destination)
    
    return {
        "user_profile": preferences or "None",
        "destination": destination,
        "destination_image": image_url,
        "destination_lat": lat or 0.0,
        "destination_lon": lon or 0.0,
        "messages": [AIMessage(content=f"Profile extracted. Destination: {destination}")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def flight_agent(state: TravelState):
    flight_data = search_flights(state["user_query"])
    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight results fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def hotel_agent(state: TravelState):
    destination = state.get("destination", "")
    hotel_results = tavily_search(f"Best hotels in {destination} for tourists")
    return {
        "hotel_results": hotel_results,
        "messages": [AIMessage(content="Hotel information fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def weather_agent(state: TravelState):
    destination = state.get("destination", "")
    weather_results = get_weather(destination)
    return {
        "weather_results": weather_results,
        "messages": [AIMessage(content="Weather data fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def currency_agent(state: TravelState):
    currency_results = get_exchange_rate("INR")
    return {
        "currency_results": currency_results,
        "messages": [AIMessage(content="Currency exchange rates fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def map_agent(state: TravelState):
    destination = state.get("destination", "")
    map_results = search_places(f"tourist attractions in {destination}")
    return {
        "map_results": map_results,
        "messages": [AIMessage(content="Map places fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def final_agent(state: TravelState):
    llm = _get_active_llm(state)
    language = state.get("language", "English")
    
    prompt = f"""You are generating a COMPLETE and DETAILED travel plan. Fill every single field thoroughly.
RESPOND ENTIRELY IN {language.upper()} LANGUAGE.

=== USER REQUEST ===
{state['user_query']}

=== USER PREFERENCES ===
{state.get('user_profile', 'None')}

=== DESTINATION ===
{state.get('destination', 'Unknown')}

=== GATHERED DATA ===

FLIGHT DATA:
{state.get('flight_results', 'No flight data available')}

HOTEL & ACCOMMODATION DATA:
{state.get('hotel_results', 'No hotel data available')}

WEATHER DATA:
{state.get('weather_results', 'No weather data available')}

CURRENCY EXCHANGE DATA:
{state.get('currency_results', 'No currency data available')}

MAP & PLACES DATA:
{state.get('map_results', 'No places data available')}

=== INSTRUCTIONS ===
You MUST fill ALL fields in the JSON response. Do NOT leave anything empty or "N/A":

1. **trip_summary**: Write a 3-4 sentence engaging summary of the trip in {language}.
2. **estimated_budget**: Provide a DETAILED budget breakdown in Indian Rupees (₹/INR). Use newlines for each item. Example:
"Total: ₹85,000
Flights: ₹35,000
Hotels: ₹25,000
Food: ₹10,000
Transport: ₹8,000
Activities: ₹7,000". Stay within user's budget limit if mentioned.
3. **weather_info**: Describe expected weather in {language}.
4. **exchange_rates**: Summarize key exchange rates in {language}.
5. **flights**: List 2-3 recommended flights with realistic airline names, flight numbers, departure/arrival cities, and status.
6. **hotels_and_places**: List at LEAST 5-8 items combining hotels AND tourist attractions. Include famous landmarks, restaurants, and must-visit spots.
7. **itinerary**: Create a detailed day-by-day plan. Each day should have 4-6 specific activities with timings. Include meals.

IMPORTANT: The user is from India. Use INR (₹) for budget. Be specific. Write in {language}.
CRITICAL REQUIREMENT: DO NOT translate the JSON schema keys. Keys like "trip_summary", "weather_info", "flights", "airline", "day", "title", "activities", etc. MUST remain exactly as defined in the schema (in English). ONLY translate the values.

OUTPUT FORMAT: You MUST return a RAW JSON object matching this schema. NO markdown formatting, NO backticks.
{{
    "trip_summary": "str",
    "weather_info": "str",
    "exchange_rates": "str",
    "flights": [{{"airline": "str", "flight_number": "str", "departure": "str", "arrival": "str", "status": "str"}}],
    "hotels_and_places": ["str"],
    "itinerary": [{{"day": int, "title": "str", "activities": ["str"]}}],
    "estimated_budget": "str"
}}
"""
    # Use raw JSON mode to bypass Groq's tool calling token limits
    json_llm = llm.bind(response_format={"type": "json_object"})
    response = json_llm.invoke([
        SystemMessage(content=f"You are a world-class AI travel planner. Always respond in {language}. Provide complete, detailed, actionable travel plans with specific budget breakdowns in INR. Never leave any field empty. Do NOT translate JSON keys. Return ONLY valid JSON."),
        HumanMessage(content=prompt)
    ])
    
    import json
    try:
        raw_json = response.content.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
        raw_json = raw_json.strip()
        parsed_data = json.loads(raw_json)
        final_plan = TravelPlan(**parsed_data)
    except Exception as e:
        print("Failed to parse JSON:", e)
        # Fallback empty plan
        final_plan = TravelPlan(trip_summary="Failed to parse itinerary.", weather_info="", exchange_rates="", flights=[], hotels_and_places=[], itinerary=[], estimated_budget="")
        
    return {
        "final_plan": final_plan,
        "messages": [AIMessage(content="Final itinerary generated.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# =========================
# Build Graph
# =========================
graph = StateGraph(TravelState)

graph.add_node("profile_agent", profile_agent)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("weather_agent", weather_agent)
graph.add_node("currency_agent", currency_agent)
graph.add_node("map_agent", map_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "profile_agent")
graph.add_edge("profile_agent", "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "weather_agent")
graph.add_edge("weather_agent", "currency_agent")
graph.add_edge("currency_agent", "map_agent")
graph.add_edge("map_agent", "final_agent")
graph.add_edge("final_agent", END)

# =========================
# In-Memory Checkpointer
# =========================
checkpointer = MemorySaver()

travel_graph = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["final_agent"]
)
