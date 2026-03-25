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

- **POST `/api/chat`**: Forwards chat messages to the webhook.
- **POST `/api/generate`**: Forwards a single prompt to the webhook.
- **GET `/api/tags`**: Returns a list of available (mocked) models.
- **GET `/health`**: Check the status of the wrapper and configuration.

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

The wrapper will take the response body from the Motion webhook and wrap it in a standard Ollama chat response JSON.
