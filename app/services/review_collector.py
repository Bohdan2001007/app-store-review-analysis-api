import random
from datetime import date

from app.clients.app_store_client import AppStoreClient
from app.schemas.reviews import (
    ReviewCollectionRequest,
    ReviewCollectionResponse,
    ReviewResponse,
)
from app.services.sentiment_analyzer import SentimentAnalyzer


class ReviewCollector:
    def __init__(
        self,
        client: AppStoreClient,
        sentiment_analyzer: SentimentAnalyzer | None = None,
        *,
        max_pool_size: int = 500,
    ) -> None:
        self._client = client
        self._sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
        self._max_pool_size = max_pool_size

    def collect(
        self,
        request: ReviewCollectionRequest,
    ) -> ReviewCollectionResponse:
        reviews = self._client.fetch_reviews(
            app_id=request.app_id,
            country=request.country,
            from_date=request.from_date,
            pool_limit=self._max_pool_size,
        )

        filtered_reviews = self._filter_by_date(
            reviews=reviews,
            from_date=request.from_date,
        )

        selected_reviews = self._random_sample(
            reviews=filtered_reviews,
            limit=request.limit,
        )
        analyzed_reviews = self._sentiment_analyzer.analyze_reviews(
            selected_reviews
        )

        return ReviewCollectionResponse(
            app_id=request.app_id,
            country=request.country,
            from_date=request.from_date,
            available_reviews=len(filtered_reviews),
            returned_reviews=len(analyzed_reviews),
            reviews=analyzed_reviews,
        )

    @staticmethod
    def _filter_by_date(
        *,
        reviews: list[ReviewResponse],
        from_date: date | None,
    ) -> list[ReviewResponse]:
        if from_date is None:
            return reviews

        return [
            review
            for review in reviews
            if review.created_at.date() >= from_date
        ]

    @staticmethod
    def _random_sample(
        *,
        reviews: list[ReviewResponse],
        limit: int,
    ) -> list[ReviewResponse]:
        if len(reviews) <= limit:
            return reviews

        return random.sample(reviews, k=limit)
