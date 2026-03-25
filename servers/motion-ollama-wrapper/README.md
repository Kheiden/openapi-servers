# 🤖 Motion Ollama Wrapper

This server acts as a lightweight wrapper that converts incoming [Ollama](https://ollama.ai/) model API requests into external HTTP calls to a Motion webhook. It allows you to use any external service that responds to webhooks as if it were a local Ollama model.

## 🚀 Quickstart

### Environment Variables

Before running the server, set the `MOTION_WEBHOOK_URL` environment variable to your target webhook URL.

```bash
export MOTION_WEBHOOK_URL="https://your-motion-webhook-url.com"
```

### Installation

Using `uv` (recommended):
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Using `pip`:
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker compose up
```

## 🔌 API Endpoints

The wrapper mimics common Ollama API endpoints:

- **POST `/api/chat`**: Initiates a chat request, sends it to Motion, and awaits a callback.
- **POST `/api/generate`**: Initiates a generation request, sends it to Motion, and awaits a callback.
- **POST `/api/motion/webhook`**: The inbound callback endpoint that Motion should call with the results.
- **GET `/api/tags`**: Returns a list of available (mocked) models.
- **GET `/api/version`**: Returns the mock version of the Ollama server.
- **GET `/health`**: Check the status of the wrapper and configuration.

### How it Works

1.  A client sends a request to `/api/chat`.
2.  The wrapper generates a unique `task_id` and registers a pending request.
3.  The wrapper sends the request to Motion at `MOTION_WEBHOOK_URL`, including the `task_id` and `callback_url` in the JSON payload.
4.  The wrapper `awaits` the response (with a 60s timeout).
5.  Motion processes the request and POSTs the result back to the wrapper's `/api/motion/webhook` endpoint.
6.  The wrapper matches the `task_id`, resolves the pending request, and returns the data to the original client in Ollama format.

### Example Request (Chat)

```bash
curl http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{
  "model": "motion-wrapper",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how can you help me today?"
    }
  ]
}'
```
