from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.clients.app_store_client import AppStoreClient
from app.core.exceptions import (
    AppNotAvailableError,
    ExternalReviewServiceError,
)
from app.schemas.reviews import (
    ReviewCollectionRequest,
    ReviewCollectionResponse,
)
from app.services.review_collector import ReviewCollector


router = APIRouter(prefix="/api/v1", tags=["reviews"])

app_store_client = AppStoreClient()
review_collector = ReviewCollector(client=app_store_client)


@router.post(
    "/reviews/collect",
    response_model=ReviewCollectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Collect random App Store reviews",
)
async def collect_reviews(
    request: ReviewCollectionRequest,
) -> ReviewCollectionResponse:
    try:
        return await run_in_threadpool(
            review_collector.collect,
            request,
        )

    except AppNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ExternalReviewServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc