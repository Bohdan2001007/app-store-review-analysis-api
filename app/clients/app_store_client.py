import time

from app_store_web_scraper import (
    AppNotFound,
    AppStoreEntry,
    AppStoreError,
    AppStoreSession,
)

from app.core.exceptions import (
    AppNotAvailableError,
    ExternalReviewServiceError,
)
from app.schemas.reviews import ReviewResponse


class AppStoreClient:
    """
    Client responsible only for communication with the App Store review source.

    Filtering, random sampling and other business logic belong to the service
    layer.
    """

    def __init__(self) -> None:
        self._session = AppStoreSession(
            delay=0.5,
            delay_jitter=0.1,
            retries=3,
            retries_backoff_factor=2,
            retries_backoff_max=10,
        )

    def fetch_reviews(
        self,
        *,
        app_id: int,
        country: str,
        pool_limit: int = 500,
    ) -> list[ReviewResponse]:
        backoff_seconds = (2, 4)

        for attempt in range(3):
            reviews = self._fetch_once(
                app_id=app_id,
                country=country,
                pool_limit=pool_limit,
            )

            if reviews:
                return reviews

            if attempt < len(backoff_seconds):
                time.sleep(backoff_seconds[attempt])

        raise ExternalReviewServiceError(
            "The App Store review service returned an empty response after "
            "several attempts."
        )

    def _fetch_once(
        self,
        *,
        app_id: int,
        country: str,
        pool_limit: int,
    ) -> list[ReviewResponse]:
        try:
            app = AppStoreEntry(
                app_id=app_id,
                country=country,
                session=self._session,
            )

            reviews: list[ReviewResponse] = []

            for review in app.reviews(limit=pool_limit):
                reviews.append(
                    ReviewResponse(
                        id=str(review.id),
                        title=(review.title or "").strip(),
                        text=(review.review or "").strip(),
                        rating=int(review.rating),
                        author=(
                            review.user_name.strip()
                            if review.user_name
                            else None
                        ),
                        created_at=review.date,
                    )
                )

            return reviews

        except AppNotFound as exc:
            raise AppNotAvailableError(
                f"App {app_id} was not found in the '{country}' App Store."
            ) from exc

        except AppStoreError as exc:
            raise ExternalReviewServiceError(
                "The App Store review service returned an error."
            ) from exc

        except Exception as exc:
            raise ExternalReviewServiceError(
                "Failed to collect reviews from the App Store."
            ) from exc
