import logging

from app.core.exceptions import SentimentAnalysisError
from app.schemas.reviews import ReviewResponse, SentimentResponse


logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"

    def __init__(self) -> None:
        self._pipeline = None

    def analyze_reviews(
        self,
        reviews: list[ReviewResponse],
    ) -> list[ReviewResponse]:
        if not reviews:
            return reviews

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

    @staticmethod
    def _build_model_input(review: ReviewResponse) -> str:
        return f"{review.title}\n\n{review.text}".strip()
