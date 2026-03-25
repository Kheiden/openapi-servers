import os
import httpx
import asyncio
import uuid
import time
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union

app = FastAPI(
    title="Motion Ollama Wrapper",
    version="1.2.0",
    description="A lightweight wrapper that converts incoming Ollama model API requests into external Motion webhook calls and awaits an inbound callback before returning the result in Ollama format.",
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
# For local testing, we might want a PUBLIC_URL if we're behind a proxy,
# but for this wrapper, we just assume Motion knows how to call us back.
CALLBACK_BASE_URL = os.getenv("CALLBACK_BASE_URL", "http://localhost:8000")

# In-memory store for pending requests
# Map task_id -> asyncio.Future
pending_requests: Dict[str, asyncio.Future] = {}

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
# Motion Webhook Callback Model
# -------------------------------

class MotionWebhookPayload(BaseModel):
    task_id: str
    result: Union[str, Dict[str, Any]]

# -------------------------------
# Helper function
# -------------------------------

async def wait_for_motion_response(ollama_payload: Dict[str, Any]) -> str:
    if not MOTION_WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="MOTION_WEBHOOK_URL environment variable is not set.")
    
    task_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    
    pending_requests[task_id] = future
    
    # Enrich the payload with task_id and a potential callback URL
    motion_payload = {
        **ollama_payload,
        "task_id": task_id,
        "callback_url": f"{CALLBACK_BASE_URL}/api/motion/webhook"
    }
    
    try:
        # Step 1: Initial call to Motion (blocking-style wait for sending, but async loop continues)
        async with httpx.AsyncClient() as client:
            response = await client.post(MOTION_WEBHOOK_URL, json=motion_payload, timeout=30)
            response.raise_for_status()
        
        # Step 2: Await the inbound webhook (blocking the current request but not the event loop)
        # We'll wait up to 60 seconds for the callback
        try:
            result_data = await asyncio.wait_for(future, timeout=60.0)
            # The result_data is what Motion sent to our callback endpoint
            if isinstance(result_data, dict):
                # If Motion returned a JSON object, maybe it has a 'content' field? 
                # Otherwise, return the whole thing as a string.
                return result_data.get("content", str(result_data))
            return str(result_data)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail=f"Timed out waiting for Motion callback for task {task_id}")
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Motion initial request failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    finally:
        # Always clean up the pending request map
        if task_id in pending_requests:
            del pending_requests[task_id]

# -------------------------------
# Routes
# -------------------------------

@app.get("/")
async def root():
    """
    Root endpoint for health checking by some clients.
    """
    return "Ollama is running"

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Handles /api/chat requests by initializing the Motion webhook and awaiting the callback.
    """
    response_content = await wait_for_motion_response(request.dict())
    
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
    Handles /api/generate requests by initializing the Motion webhook and awaiting the callback.
    """
    response_content = await wait_for_motion_response(request.dict())
    
    return {
        "model": request.model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "response": response_content,
        "done": True
    }

@app.post("/api/motion/webhook")
async def motion_callback_endpoint(
    task_id: Optional[str] = None,
    payload: Any = Body(...)
):
    """
    Endpoint for Motion to call back with the results.
    Expected payload should contain task_id and result, or task_id as query param.
    """
    # Try to find task_id in payload if not in query param
    if not task_id and isinstance(payload, dict):
        task_id = payload.get("task_id")
    
    if not task_id or task_id not in pending_requests:
        return {"status": "ignored", "reason": "No pending request found for this task_id."}
    
    # The result data could be the whole payload or a specific 'result' field
    result_data = payload.get("result", payload) if isinstance(payload, dict) else payload
    
    # Resolve the future, which unblocks the original request
    if not pending_requests[task_id].done():
        pending_requests[task_id].set_result(result_data)
        return {"status": "success", "message": f"Task {task_id} unblocked."}
    else:
        return {"status": "ignored", "reason": "Request already resolved or timed out."}

@app.get("/api/tags")
@app.get("/api/models")
async def list_models():
    """
    Returns the list of models in exact Ollama schema.
    """
    return {
        "models": [
            {
                "name": "motion-wrapper:latest",
                "model": "motion-wrapper:latest",
                "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "size": 0,
                "digest": "motion-wrapper-digest",
                "details": {
                    "format": "gguf",
                    "family": "llama",
                    "families": ["llama"],
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M"
                }
            }
        ]
    }

@app.get("/v1/models")
async def list_v1_models():
    """
    OpenAI-compatible models list.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "motion-wrapper:latest",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "motion"
            }
        ]
    }

@app.get("/api/version")
async def get_version():
    """
    Returns a mock version of Ollama.
    """
    return {"version": "0.1.27"}

@app.post("/ollama/verify")
@app.get("/ollama/verify")
async def ollama_verify():
    """
    Verification endpoint for Open WebUI or other Ollama clients.
    """
    return {"status": True}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "webhook_configured": bool(MOTION_WEBHOOK_URL),
        "pending_requests_count": len(pending_requests)
    }
