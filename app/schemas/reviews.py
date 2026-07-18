from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewCollectionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_id": 1459969523,
                "country": "us",
                "from_date": "2026-01-01",
                "limit": 100,
            }
        }
    )

    app_id: int = Field(
        ...,
        gt=0,
        description="Numeric Apple App Store application ID.",
    )
    country: str = Field(
        default="us",
        min_length=2,
        max_length=2,
        description="Two-letter App Store country code.",
    )
    from_date: date | None = Field(
        default=None,
        description="Return only reviews created on or after this date.",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Maximum number of reviews to return.",
    )

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        country = value.strip().lower()

        if not country.isalpha() or len(country) != 2:
            raise ValueError(
                "country must be a two-letter alphabetic code, for example 'us'"
            )

        return country

    @field_validator("from_date")
    @classmethod
    def validate_from_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("from_date cannot be in the future")

        return value


class SentimentResponse(BaseModel):
    label: str
    score: float
    model: str


class ReviewResponse(BaseModel):
    id: str
    title: str
    text: str
    rating: int = Field(ge=1, le=5)
    author: str | None = None
    created_at: datetime
    sentiment: SentimentResponse | None = None


class ReviewCollectionResponse(BaseModel):
    app_id: int
    country: str
    from_date: date | None
    available_reviews: int
    returned_reviews: int
    reviews: list[ReviewResponse]
