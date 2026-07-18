class ReviewCollectionError(Exception):
    """Base exception for review collection errors."""


class AppNotAvailableError(ReviewCollectionError):
    """Raised when the app is unavailable for the requested country."""


class ExternalReviewServiceError(ReviewCollectionError):
    """Raised when the external review source cannot be reached."""


class SentimentAnalysisError(ReviewCollectionError):
    """Raised when review sentiment analysis fails."""
