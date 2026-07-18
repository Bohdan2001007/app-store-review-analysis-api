import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime

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


logger = logging.getLogger(__name__)


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
        sources = (
            ("app-store-web-scraper", self._fetch_once),
            ("apple-rss-mostrecent", self._fetch_rss_most_recent),
            ("apple-rss-mosthelpful", self._fetch_rss_most_helpful),
        )
        backoff_seconds = (2, 4)

        for source_name, fetcher in sources:
            logger.info(
                "Trying App Store review source '%s' for app_id=%s country=%s",
                source_name,
                app_id,
                country,
            )

            for attempt in range(3):
                try:
                    reviews = fetcher(
                        app_id=app_id,
                        country=country,
                        pool_limit=pool_limit,
                    )
                except AppNotAvailableError:
                    logger.warning(
                        "App Store review source '%s' reported app_id=%s "
                        "country=%s as unavailable",
                        source_name,
                        app_id,
                        country,
                    )
                    raise
                except ExternalReviewServiceError:
                    logger.warning(
                        "App Store review source '%s' failed on attempt %s",
                        source_name,
                        attempt + 1,
                        exc_info=True,
                    )
                    reviews = []

                if reviews:
                    logger.info(
                        "App Store review source '%s' returned %s reviews",
                        source_name,
                        len(reviews),
                    )
                    return reviews

                logger.warning(
                    "App Store review source '%s' returned an empty response "
                    "on attempt %s",
                    source_name,
                    attempt + 1,
                )

                if attempt < len(backoff_seconds):
                    time.sleep(backoff_seconds[attempt])

            logger.warning(
                "App Store review source '%s' returned no reviews after "
                "several attempts; trying next source",
                source_name,
            )

        raise ExternalReviewServiceError(
            "All App Store review sources returned an empty response after "
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

    def _fetch_rss_most_recent(
        self,
        *,
        app_id: int,
        country: str,
        pool_limit: int,
    ) -> list[ReviewResponse]:
        return self._fetch_rss_json(
            app_id=app_id,
            country=country,
            pool_limit=pool_limit,
            sort_by="mostrecent",
        )

    def _fetch_rss_most_helpful(
        self,
        *,
        app_id: int,
        country: str,
        pool_limit: int,
    ) -> list[ReviewResponse]:
        return self._fetch_rss_json(
            app_id=app_id,
            country=country,
            pool_limit=pool_limit,
            sort_by="mosthelpful",
        )

    def _fetch_rss_json(
        self,
        *,
        app_id: int,
        country: str,
        pool_limit: int,
        sort_by: str,
    ) -> list[ReviewResponse]:
        try:
            reviews: list[ReviewResponse] = []

            for page in range(1, 11):
                data = self._request_rss_page(
                    app_id=app_id,
                    country=country,
                    page=page,
                    sort_by=sort_by,
                )
                feed = data.get("feed", {})
                entries = self._normalize_feed_entries(feed.get("entry"))

                for entry in entries:
                    reviews.append(self._parse_rss_review(entry))

                    if len(reviews) == pool_limit:
                        return reviews

            return reviews

        except AppNotAvailableError:
            raise

        except Exception as exc:
            raise ExternalReviewServiceError(
                "Failed to collect reviews from the App Store RSS feed."
            ) from exc

    @staticmethod
    def _request_rss_page(
        *,
        app_id: int,
        country: str,
        page: int,
        sort_by: str,
    ) -> dict:
        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby={sort_by}/json"
        )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json,text/javascript,*/*",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise AppNotAvailableError(
                    f"App {app_id} was not found in the '{country}' "
                    "App Store."
                ) from exc

            raise

    @staticmethod
    def _normalize_feed_entries(entries: object) -> list[dict]:
        if entries is None:
            return []

        if isinstance(entries, list):
            return entries

        if isinstance(entries, dict):
            return [entries]

        return []

    @staticmethod
    def _parse_rss_review(entry: dict) -> ReviewResponse:
        return ReviewResponse(
            id=str(entry["id"]["label"]),
            title=(entry["title"]["label"] or "").strip(),
            text=(entry["content"]["label"] or "").strip(),
            rating=int(entry["im:rating"]["label"]),
            author=(entry["author"]["name"]["label"] or "").strip() or None,
            created_at=datetime.fromisoformat(
                entry["updated"]["label"].replace("Z", "+00:00")
            ),
        )
