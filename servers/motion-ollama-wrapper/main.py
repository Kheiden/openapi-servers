import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import time

app = FastAPI(
    title="Motion Ollama Wrapper",
    version="1.0.0",
    description="A lightweight wrapper that converts incoming Ollama model API requests into external Motion webhook calls and returns the response in Ollama format.",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MOTION_WEBHOOK_URL = os.getenv("MOTION_WEBHOOK_URL")

# -------------------------------
# Pydantic models for Ollama
# -------------------------------

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None

class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: Optional[bool] = False
    options: Optional[Dict[str, Any]] = None

# -------------------------------
# Helper function
# -------------------------------

def forward_to_motion(payload: Dict[str, Any]) -> str:
    if not MOTION_WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="MOTION_WEBHOOK_URL environment variable is not set.")
    
    try:
        # Blocking external HTTP call
        response = requests.post(MOTION_WEBHOOK_URL, json=payload, timeout=300)
        response.raise_for_status()
        
        # The user said: "respond to the original inbound API call with the properly formatted data from the body of the inbound HTTP call."
        # If the response is JSON, we might want to return it as a formatted string or just the text.
        # Most webhooks will return text or a specific JSON field. 
        # For maximum flexibility, we'll return the raw text of the response.
        return response.text
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error connecting to Motion webhook: {e}")

# -------------------------------
# Routes
# -------------------------------

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Handles /api/chat requests by forwarding the messages to the Motion webhook
    and returning the result in Ollama format.
    """
    # For a chat request, we pass the messages to the webhook.
    response_content = forward_to_motion(request.dict())
    
    return {
        "model": request.model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": {
            "role": "assistant",
            "content": response_content
        },
        "done": True
    }

@app.post("/api/generate")
async def generate_endpoint(request: GenerateRequest):
    """
    Handles /api/generate requests by forwarding the prompt to the Motion webhook
    and returning the result in Ollama format.
    """
    # For a generate request, we pass the prompt to the webhook.
    response_content = forward_to_motion(request.dict())
    
    return {
        "model": request.model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "response": response_content,
        "done": True
    }

@app.get("/api/tags")
async def list_models():
    """
    Returns a mock list of models to satisfy clients that check available models.
    """
    return {
        "models": [
            {
                "name": "motion-wrapper",
                "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "size": 0,
                "digest": "motion-wrapper-digest"
            }
        ]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "webhook_configured": bool(MOTION_WEBHOOK_URL)}
