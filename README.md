# app-store-review-analysis-api
REST API for collecting and analyzing Apple App Store reviews using NLP and LLM-generated insights.

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the lightweight default dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a local `.env` file from `.env.example` and set `OPENAI_API_KEY`.

Run the API and UI locally:

```bash
python -m uvicorn app.main:app --reload
```

Open the UI:

```text
http://127.0.0.1:8000
```

Check the API health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Runtime logs are written to `logs/`.

Docker uses the lightweight `requirements-docker.txt` by default. It does not
install `torch` or `transformers`; sentiment analysis runs through OpenAI when
`SENTIMENT_ANALYZER_BACKEND=openai`.

### Sentiment Backends

The sentiment backend is selected with the `SENTIMENT_ANALYZER_BACKEND`
environment variable.

Use OpenAI sentiment analysis for the default lightweight setup:

```text
SENTIMENT_ANALYZER_BACKEND=openai
OPENAI_SENTIMENT_MODEL=gpt-4.1-mini
```

This is the recommended mode for Docker and AWS because it does not require
installing `torch` or downloading a local ML model.

To switch to the local Hugging Face ML model, install the extra dependencies:

```bash
pip install -r requirements-local-ml.txt
```

Then set this in `.env`:

```text
SENTIMENT_ANALYZER_BACKEND=local
```

Restart the API after changing `.env`:

```bash
python -m uvicorn app.main:app --reload
```

Local ML mode uses `cardiffnlp/twitter-roberta-base-sentiment-latest` via
`transformers` and `torch`. This is heavier and is not the default Docker mode.

## Review Source Limitations

The official Apple review source is the App Store Connect API. This project uses
public review sources instead, because they are easier to run in a demo without
App Store Connect credentials.

The collector currently tries several sources:

- `app-store-web-scraper`, a third-party library that uses public Apple web
  endpoints.
- Apple RSS most recent reviews.
- Apple RSS most helpful reviews.

These sources are not equally reliable. The third-party scraper itself
recommends using the official App Store Connect API when possible, and public
Apple review endpoints may return only a limited subset of all reviews.

Because public sources can occasionally return an empty or partial response
without a clear error, the client uses retries and fallback sources. If all
sources fail to provide a reliable result, the API treats the response as an
external review service failure instead of returning an empty successful result.

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
