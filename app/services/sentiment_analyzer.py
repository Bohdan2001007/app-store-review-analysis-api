import logging
import os
from typing import Any

from app.core.exceptions import SentimentAnalysisError
from app.schemas.reviews import ReviewResponse, SentimentResponse


logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    _DEFAULT_BACKEND = "openai"
    _DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
    _MAX_OPENAI_REVIEW_TEXT_LENGTH = 1200

    def __init__(self) -> None:
        self._pipeline = None
        self._client = None
        self._backend = os.getenv(
            "SENTIMENT_ANALYZER_BACKEND",
            self._DEFAULT_BACKEND,
        ).strip().lower()
        self._openai_model = os.getenv(
            "OPENAI_SENTIMENT_MODEL",
            self._DEFAULT_OPENAI_MODEL,
        )

    def analyze_reviews(
        self,
        reviews: list[ReviewResponse],
    ) -> list[ReviewResponse]:
        if not reviews:
            return reviews

        if self._backend == "local":
            return self._analyze_reviews_locally(reviews)

        if self._backend == "openai":
            return self._analyze_reviews_with_openai(reviews)

        raise SentimentAnalysisError(
            "Unsupported sentiment analyzer backend."
        )

    def _analyze_reviews_locally(
        self,
        reviews: list[ReviewResponse],
    ) -> list[ReviewResponse]:
        try:
            classifier = self._get_pipeline()
            texts = [self._build_model_input(review) for review in reviews]
            logger.info(
                "Analyzing sentiment for %s reviews with model '%s'",
                len(reviews),
                self.MODEL_NAME,
            )
            results = classifier(
                texts,
                truncation=True,
                max_length=512,
            )
        except ImportError as exc:
            raise SentimentAnalysisError(
                "Sentiment analysis dependencies are not installed."
            ) from exc
        except Exception as exc:
            raise SentimentAnalysisError(
                "Failed to analyze review sentiment."
            ) from exc

        return [
            review.model_copy(
                update={
                    "sentiment": SentimentResponse(
                        label=result["label"],
                        score=float(result["score"]),
                        model=self.MODEL_NAME,
                    )
                }
            )
            for review, result in zip(reviews, results, strict=True)
        ]

    def _analyze_reviews_with_openai(
        self,
        reviews: list[ReviewResponse],
    ) -> list[ReviewResponse]:
        if not os.getenv("OPENAI_API_KEY"):
            raise SentimentAnalysisError(
                "OPENAI_API_KEY is not configured."
            )

        try:
            response = self._get_client().responses.create(
                model=self._openai_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Classify App Store review sentiment. Use only "
                            "the supplied reviews. Return positive, neutral, "
                            "or negative for every review id."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_openai_input(reviews),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "review_sentiment",
                        "strict": True,
                        "schema": self._openai_response_schema(),
                    }
                },
            )
            parsed_response = response.output_text
        except Exception as exc:
            raise SentimentAnalysisError(
                "Failed to analyze review sentiment with OpenAI."
            ) from exc

        return self._apply_openai_sentiment(
            reviews=reviews,
            response_json=parsed_response,
        )

    def _get_pipeline(self):
        if self._pipeline is None:
            logger.info(
                "Loading sentiment analysis model '%s'",
                self.MODEL_NAME,
            )
            from transformers import pipeline

            self._pipeline = pipeline(
                task="sentiment-analysis",
                model=self.MODEL_NAME,
                tokenizer=self.MODEL_NAME,
            )

        return self._pipeline

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()

        return self._client

    def _build_openai_input(
        self,
        reviews: list[ReviewResponse],
    ) -> str:
        import json

        return json.dumps(
            {
                "reviews": [
                    {
                        "id": review.id,
                        "title": review.title,
                        "text": self._truncate_text(
                            review.text,
                            self._MAX_OPENAI_REVIEW_TEXT_LENGTH,
                        ),
                        "rating": review.rating,
                    }
                    for review in reviews
                ]
            },
            ensure_ascii=False,
        )

    def _apply_openai_sentiment(
        self,
        *,
        reviews: list[ReviewResponse],
        response_json: str,
    ) -> list[ReviewResponse]:
        import json

        payload = json.loads(response_json)
        sentiments_by_id = {
            item["id"]: item
            for item in payload.get("reviews", [])
            if isinstance(item, dict) and "id" in item
        }

        return [
            review.model_copy(
                update={
                    "sentiment": self._build_openai_sentiment_response(
                        sentiments_by_id.get(review.id)
                    )
                }
            )
            for review in reviews
        ]

    def _build_openai_sentiment_response(
        self,
        item: dict[str, Any] | None,
    ) -> SentimentResponse:
        if not item:
            return SentimentResponse(
                label="neutral",
                score=0,
                model=self._openai_model,
            )

        return SentimentResponse(
            label=item["label"],
            score=float(item["score"]),
            model=self._openai_model,
        )

    @staticmethod
    def _openai_response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "reviews": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "label": {
                                "type": "string",
                                "enum": ["positive", "neutral", "negative"],
                            },
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": ["id", "label", "score"],
                    },
                },
            },
            "required": ["reviews"],
        }

    @staticmethod
    def _build_model_input(review: ReviewResponse) -> str:
        return f"{review.title}\n\n{review.text}".strip()

    @staticmethod
    def _truncate_text(value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value

        return value[: max_length - 3] + "..."
