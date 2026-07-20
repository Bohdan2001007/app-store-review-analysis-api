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

The official Apple review source is the App Store Connect API. This project
does not have access to that API, so it uses public review sources instead.

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

## Analysis Limits and Rules

The API is intentionally bounded to keep requests stable, affordable, and fast
enough for a synchronous demo workflow.

### Review Collection

- The public endpoint accepts `limit` from `1` to `100`.
- Internally, the collector fetches up to `500` reviews before applying the
  user-facing `limit`.
- `available_reviews` means the number of reviews found after filters such as
  `from_date`, but before applying the user-facing `limit`.
- `returned_reviews` means the number of reviews actually returned in the API
  response.
- If more reviews are available than requested, the API returns a random sample
  from the collected pool.
- The internal `500` review pool is not a guarantee that the App Store has only
  500 reviews. It is a safety limit for the current public-source collection
  strategy.

### Sentiment Analysis

- Default sentiment backend: OpenAI with `OPENAI_SENTIMENT_MODEL`, currently
  `gpt-4.1-mini`.
- Optional local ML backend:
  `cardiffnlp/twitter-roberta-base-sentiment-latest`.
- For OpenAI sentiment analysis, each review text is truncated to `1200`
  characters before classification to reduce latency, token usage, and request
  size.
- The full review text is still returned in the API response.

### Keyword Analysis

Only reviews that may contain issues or constructive criticism are included in
keyword analysis:

- negative sentiment;
- neutral sentiment with rating lower than `5`;
- or rating `<= 3`.

Keyword extraction rules:

- text is built from review title and review body;
- text is lowercased;
- stopwords are removed;
- words shorter than `3` characters are ignored;
- keyword frequency is counted by unique review coverage, not by repeated word
  occurrences inside the same review;
- keyword `count` means the number of unique analyzed reviews where the keyword
  appears;
- there is no minimum count of `2` or `3` for a keyword to appear in
  `keyword_insights.keywords`; a keyword can appear with `count=1`;
- at most `20` keyword groups are returned.

Each analyzed review is assigned to one primary keyword group. If a review
contains multiple candidate keywords, the service selects the keyword with the
highest global coverage. If coverage is tied, the keyword that appears first in
the review is selected. This prevents the same review from duplicating across
multiple keyword groups and inflating the statistics.

### LLM Actionable Insights

The LLM does not receive every raw review blindly. It receives structured review
statistics and selected keyword groups.

Default limits:

- `OPENAI_INSIGHTS_MIN_KEYWORD_COUNT=3`: keyword groups with at least this count
  are selected for LLM insights.
- `OPENAI_INSIGHTS_FALLBACK_KEYWORD_GROUPS=2`: if no keyword group meets the
  minimum count, the top `2` keyword groups are used as fallback, even if their
  count is lower than `3`.
- `OPENAI_INSIGHTS_MAX_COMMENTS_PER_KEYWORD=6`: at most this many full comments
  are sent to the LLM per selected keyword group.

The prompt includes:

- total returned reviews;
- average rating;
- rating distribution;
- sentiment distribution;
- number of reviews used for keyword analysis;
- selected keyword groups with coverage and evidence comments.

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
