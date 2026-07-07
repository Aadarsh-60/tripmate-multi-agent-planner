import json
import uuid
import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_core.messages import HumanMessage
from backend import travel_graph

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TripMate AI (Advanced)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None
    model: str = "groq"       # groq / openai / gemini
    language: str = "English"  # English / Hindi / Spanish / French / Japanese

class ApproveRequest(BaseModel):
    thread_id: str
    action: str  # "approve" or "reject"
    feedback: str | None = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


def generate_stream(user_input: str, thread_id: str, model: str = "groq", language: str = "English"):
    config = {"configurable": {"thread_id": thread_id}}
    
    # Initialize state with model & language selection
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "user_query": user_input,
        "llm_provider": model,
        "language": language,
        "llm_calls": 0
    }
    
    try:
        # stream_mode="updates" yields the state updates from each node
        for event in travel_graph.stream(initial_state, config, stream_mode="updates"):
            # Each event is a dict like {"node_name": {"key": "value"}}
            for node, state_update in event.items():
                if node == "__interrupt__":
                    continue
                
                # Yield a progress message
                yield f"data: {json.dumps({'type': 'progress', 'node': node})}\n\n"

        # Check if we are paused for Human-in-the-loop
        current_state = travel_graph.get_state(config)
        if len(current_state.next) > 0 and current_state.next[0] == "final_agent":
            draft_data = {
                "flights": current_state.values.get("flight_results", ""),
                "hotels": current_state.values.get("hotel_results", ""),
                "weather": current_state.values.get("weather_results", ""),
                "map": current_state.values.get("map_results", ""),
                "destination": current_state.values.get("destination", ""),
                "destination_image": current_state.values.get("destination_image", ""),
                "destination_lat": current_state.values.get("destination_lat", 0),
                "destination_lon": current_state.values.get("destination_lon", 0),
            }
            yield f"data: {json.dumps({'type': 'hitl_wait', 'draft': draft_data, 'thread_id': thread_id})}\n\n"
        else:
            if "final_plan" in current_state.values and current_state.values["final_plan"]:
                final_json = current_state.values["final_plan"].model_dump()
                meta = {
                    "destination": current_state.values.get("destination", ""),
                    "destination_image": current_state.values.get("destination_image", ""),
                    "destination_lat": current_state.values.get("destination_lat", 0),
                    "destination_lon": current_state.values.get("destination_lon", 0),
                }
                yield f"data: {json.dumps({'type': 'final_plan', 'plan': final_json, 'meta': meta})}\n\n"
                
    except Exception as e:
        print("Error in stream:", e)
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    user_message = request_data.message.strip()
    if not user_message:
        return JSONResponse(status_code=400, content={"error": "Message empty."})

    thread_id = request_data.thread_id or f"user_{uuid.uuid4().hex}"
    
    return StreamingResponse(
        generate_stream(user_message, thread_id, request_data.model, request_data.language),
        media_type="text/event-stream"
    )

def generate_approval_stream(thread_id: str, action: str, feedback: str):
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        if action == "reject":
            # If rejected, we might update state with feedback and restart, 
            # for now let's just abort.
            yield f"data: {json.dumps({'type': 'error', 'error': 'Plan rejected by user.'})}\n\n"
            return
            
        # Resume the graph by passing None to stream
        for event in travel_graph.stream(None, config, stream_mode="updates"):
            for node, state_update in event.items():
                yield f"data: {json.dumps({'type': 'progress', 'node': node})}\n\n"
                
        # Send final output
        current_state = travel_graph.get_state(config)
        if "final_plan" in current_state.values and current_state.values["final_plan"]:
            final_json = current_state.values["final_plan"].model_dump()
            meta = {
                "destination": current_state.values.get("destination", ""),
                "destination_image": current_state.values.get("destination_image", ""),
                "destination_lat": current_state.values.get("destination_lat", 0),
                "destination_lon": current_state.values.get("destination_lon", 0),
            }
            yield f"data: {json.dumps({'type': 'final_plan', 'plan': final_json, 'meta': meta})}\n\n"
            
    except Exception as e:
        print("Error in approval stream:", e)
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@app.post("/api/approve")
async def approve_plan(request_data: ApproveRequest):
    return StreamingResponse(
        generate_approval_stream(request_data.thread_id, request_data.action, request_data.feedback or ""),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)