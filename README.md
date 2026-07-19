# app-store-review-analysis-api
REST API for collecting and analyzing Apple App Store reviews using NLP and LLM-generated insights.

## Docker

Create a local `.env` file from `.env.example` and set `OPENAI_API_KEY`.

Build and run the production container:

```bash
docker compose up --build
```

Open the UI:

```text
http://127.0.0.1:8000
```

Check the API health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Stop the container:

```bash
docker compose down
```

The container runs FastAPI with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Runtime logs are written to `logs/`.

Docker uses the lightweight `requirements-docker.txt` by default. It does not
install `torch` or `transformers`; sentiment analysis runs through OpenAI when
`SENTIMENT_ANALYZER_BACKEND=openai`.

### Sentiment Backends

Default Docker/AWS-friendly mode:

```text
SENTIMENT_ANALYZER_BACKEND=openai
OPENAI_SENTIMENT_MODEL=gpt-4.1-mini
```

Local Hugging Face ML mode:

```bash
pip install -r requirements-local-ml.txt
```

```text
SENTIMENT_ANALYZER_BACKEND=local
```

Local ML mode uses `cardiffnlp/twitter-roberta-base-sentiment-latest` through
`transformers` and `torch`. This is heavier and is not the default Docker mode.

### Estimate AWS Memory Needs

Start the container:

```bash
docker compose up
```

In another terminal, watch container memory:

```bash
docker stats app-store-review-analysis-api
```

Run a small pipeline request:

```bash
curl -X POST \
  "http://127.0.0.1:8000/api/v1/reviews/collect" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": 1459969523,
    "country": "us",
    "from_date": "2026-01-01",
    "limit": 2
  }'
```

Then run a fuller request:

```bash
curl -X POST \
  "http://127.0.0.1:8000/api/v1/reviews/collect" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": 1459969523,
    "country": "us",
    "from_date": "2026-01-01",
    "limit": 100
  }'
```

Check image size:

```bash
docker images app-store-review-analysis-api-review-analysis-api
```

Use the peak memory shown by `docker stats` as the baseline for choosing an AWS
instance or container memory limit.
