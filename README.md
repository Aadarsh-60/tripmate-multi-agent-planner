# 🌍 TripMate AI: Multi-Agent Travel Planner

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11+-yellow.svg)
![React](https://img.shields.io/badge/React-18-cyan.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

**TripMate AI** is a production-ready, full-stack multi-agent travel planning application. It leverages the power of LangGraph, FastAPI, and React to orchestrate a team of specialized AI agents that collaboratively research, plan, and budget your perfect vacation in real-time.

---

## ✨ Features

- **🤖 Multi-Agent Architecture**: Uses specialized LangGraph agents for extracting preferences, finding flights, booking hotels, checking weather, calculating currency exchange, and finding local attractions.
- **🧠 Multi-LLM Support**: Seamlessly switch between top-tier AI models directly from the UI:
  - `Groq (Llama-3.3-70B)` (Ultra-fast, Default)
  - `OpenAI (GPT-4o)`
  - `Google Gemini (Flash 2.0)`
- **🌍 Multi-Language Output**: Plan your trip in English, Hindi, Spanish, French, or Japanese. The final agent natively translates the entire itinerary and budget breakdown.
- **📸 Dynamic Destination Visuals**: Automatically fetches high-quality hero images of the destination using the Wikipedia API (completely free and keyless).
- **🗺️ Interactive Maps**: Integrates Leaflet.js and OpenStreetMap to dynamically extract coordinates and display an interactive map of your travel destination.
- **⚡ Real-Time SSE Streaming**: Watch the agents work in real-time on the frontend UI without blocking the browser.
- **🐳 Dockerized**: Fully containerized with a multi-stage Nginx React build and FastAPI backend.

---

## 🏗️ Architecture

The backend is powered by **LangGraph** which orchestrates a StateGraph of agents:

1. **Profile Agent**: Extracts destination, user preferences, coordinates (Nominatim), and fetches a Wikipedia image.
2. **Flight Agent**: Finds real-time mock flight options.
3. **Hotel Agent**: Uses Tavily Search to find highly-rated accommodations.
4. **Weather Agent**: Uses Open-Meteo API to forecast destination weather.
5. **Currency Agent**: Uses ExchangeRate API to get live conversion rates for INR.
6. **Map Agent**: Finds local tourist attractions.
7. **Final Agent**: Aggregates all data into a strictly structured JSON payload (via `json_mode`) containing a day-by-day itinerary and budget breakdown.

---

## 🔧 Tool Architecture & Creation

TripMate AI uses a decoupled tool architecture. Tools are standard Python functions that interact with external APIs (like Open-Meteo for weather or Nominatim for coordinates). They are stored in the `backend/tools/` directory.

### How Tools Work
Rather than using traditional LangChain `@tool` decorators which rely on LLM function-calling capabilities (which can be flaky or slow), this architecture uses **Graph Nodes as Agents**. 
1. The LangGraph state (`TravelState`) is passed from node to node.
2. A node (e.g., `weather_agent`) extracts the `destination` from the state.
3. It calls a standard Python tool function (e.g., `get_weather(destination)`).
4. The tool returns a string, which is then appended back to the state (e.g., `weather_results`).

### Creating a New Tool
To add a new capability (e.g., finding local events), follow these steps:

**1. Create the Tool Logic (`backend/tools/event_tool.py`)**
```python
import requests

def get_local_events(city: str) -> str:
    # Example using a mock API
    try:
        # response = requests.get(f"https://api.example.com/events?location={city}")
        # return response.json()['summary']
        return f"Upcoming events in {city}: Local Food Festival, Music Concert."
    except Exception as e:
        return f"Could not fetch events: {e}"
```

**2. Add it to the LangGraph State (`backend/backend.py`)**
Update `TravelState` to hold the new data:
```python
class TravelState(TypedDict):
    ...
    event_results: str  # Add this field
```

**3. Create a Graph Node (`backend/backend.py`)**
```python
from tools.event_tool import get_local_events

def event_agent(state: TravelState):
    destination = state.get("destination", "")
    events = get_local_events(destination)
    return {
        "event_results": events,
        "messages": [AIMessage(content="Local events fetched.")],
        "llm_calls": state.get("llm_calls", 0) + 1
    }
```

**4. Register the Node in the Graph (`backend/backend.py`)**
```python
# Add the node
graph.add_node("event_agent", event_agent)

# Update the edges (e.g., placing it before the final agent)
graph.add_edge("map_agent", "event_agent")
graph.add_edge("event_agent", "final_agent")
```
Finally, update the `final_agent` prompt to include `{state.get('event_results', '')}` so the LLM considers events while planning!

---

## 🚀 Quick Start (Docker)

The absolute easiest way to run TripMate AI locally is via Docker.

### Prerequisites
- Docker and Docker Compose installed.
- API Keys (See Environment Variables below).

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/tripmate-ai.git
cd tripmate-ai
```

### 2. Setup Environment Variables
Create a `.env` file in the root directory:
```env
# Required for web research
TAVILY_API_KEY=your_tavily_key_here

# Required (Default Model)
GROQ_API_KEY=your_groq_key_here

# Optional (Only needed if selected in UI)
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_gemini_key_here
```

### 3. Run with Docker Compose
```bash
docker compose up --build
```
*That's it!* Navigate to `http://localhost` in your browser. The frontend is served by Nginx on port 80, which automatically proxies API requests to the FastAPI backend on port 8000.

---

## 🛠️ Manual Setup (Without Docker)

If you prefer to run the development servers manually:

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
*Backend runs on `http://127.0.0.1:8000`*

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*Frontend runs on `http://localhost:5173`*

---

## ☁️ Deployment (Railway)

This project is configured out-of-the-box for 1-click deployment on **Railway.app**.

1. Push this repository to your GitHub account.
2. Log in to [Railway.app](https://railway.app/).
3. Click **New Project** -> **Deploy from GitHub repo**.
4. Select your `tripmate-ai` repository.
5. Railway will automatically detect the `docker-compose.yml` file and spin up both the Frontend and Backend services in a private network.
6. Add your `.env` variables in the Railway dashboard.
7. Generate a public URL for your Frontend service in Railway to share with the world!

---

## 📝 Example Prompts to Try

- *"Plan a 4-day budget trip to Manali under ₹30,000. I am a vegetarian."*
- *"I need a luxury 1-week itinerary for Paris for a couple. Include museum visits."*
- *"5 days in Tokyo focusing on anime culture and street food."*

---

## 📄 License
This project is licensed under the MIT License.
