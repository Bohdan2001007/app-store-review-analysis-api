import json
import logging
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.reviews import (
    ActionableInsightResponse,
    ActionableInsightsResponse,
    KeywordGroupResponse,
    KeywordInsightsResponse,
    ReviewResponse,
)


logger = logging.getLogger(__name__)


class ActionableInsightsGenerator:
    _DEFAULT_MODEL = "gpt-4.1-mini"
    _DEFAULT_MIN_KEYWORD_COUNT = 4
    _DEFAULT_MAX_COMMENTS_PER_KEYWORD = 8
    _DEFAULT_FALLBACK_KEYWORD_GROUPS = 3
    _PROMPT_PATH = (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "actionable_insights_system_prompt.txt"
    )
    _PROMPT_LOG_PATH = (
        Path(__file__).resolve().parents[2]
        / "logs"
        / "actionable_insights_prompt.log"
    )

    def __init__(self) -> None:
        self._load_env_file()
        self._client = None
        self._model = os.getenv(
            "OPENAI_INSIGHTS_MODEL",
            self._DEFAULT_MODEL,
        )
        self._min_keyword_count = self._read_positive_int_env(
            name="OPENAI_INSIGHTS_MIN_KEYWORD_COUNT",
            default=self._DEFAULT_MIN_KEYWORD_COUNT,
        )
        self._max_comments_per_keyword = self._read_positive_int_env(
            name="OPENAI_INSIGHTS_MAX_COMMENTS_PER_KEYWORD",
            default=self._DEFAULT_MAX_COMMENTS_PER_KEYWORD,
        )
        self._fallback_keyword_groups = self._read_positive_int_env(
            name="OPENAI_INSIGHTS_FALLBACK_KEYWORD_GROUPS",
            default=self._DEFAULT_FALLBACK_KEYWORD_GROUPS,
        )

    def generate(
        self,
        *,
        reviews: list[ReviewResponse],
        keyword_insights: KeywordInsightsResponse,
    ) -> ActionableInsightsResponse:
        selected_keyword_groups = self._select_keyword_groups(
            keyword_insights.keywords
        )
        if not selected_keyword_groups:
            selected_keyword_groups = keyword_insights.keywords[
                : self._fallback_keyword_groups
            ]

        prompt_variables = self._build_prompt_variables(
            reviews=reviews,
            keyword_insights=keyword_insights,
            selected_keyword_groups=selected_keyword_groups,
        )
        system_prompt = self._build_system_prompt(prompt_variables)
        log_timestamp = self._write_prompt_log(system_prompt)

        if not os.getenv("OPENAI_API_KEY"):
            skipped_reason = "OPENAI_API_KEY is not configured."
            self._write_log_section(
                timestamp=log_timestamp,
                title="SKIPPED",
                content=skipped_reason,
            )
            return ActionableInsightsResponse(
                generated=False,
                model=self._model,
                skipped_reason=skipped_reason,
            )

        if not selected_keyword_groups:
            skipped_reason = "No keyword groups are available for insights."
            self._write_log_section(
                timestamp=log_timestamp,
                title="SKIPPED",
                content=skipped_reason,
            )
            return ActionableInsightsResponse(
                generated=False,
                model=self._model,
                skipped_reason=skipped_reason,
            )

        try:
            response = self._get_client().responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Generate actionable insights from the App Store "
                            "review data in the system prompt."
                        ),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "actionable_insights",
                        "strict": True,
                        "schema": self._response_schema(),
                    }
                },
            )
            self._write_log_section(
                timestamp=log_timestamp,
                title="OPENAI RESPONSE",
                content=response.output_text,
            )
            parsed_response = json.loads(response.output_text)

        except Exception as exc:
            logger.warning("Failed to generate actionable insights", exc_info=True)
            error_message = f"{type(exc).__name__}: {exc}"
            self._write_log_section(
                timestamp=log_timestamp,
                title="ERROR",
                content=error_message,
            )
            return ActionableInsightsResponse(
                generated=False,
                model=self._model,
                skipped_reason=(
                    "Failed to generate actionable insights: "
                    f"{error_message}"
                ),
            )

        actionable_insights = self._parse_response(parsed_response)
        self._write_log_section(
            timestamp=log_timestamp,
            title="PARSED ACTIONABLE INSIGHTS",
            content=actionable_insights.model_dump_json(indent=2),
        )

        return actionable_insights

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()

        return self._client

    def _select_keyword_groups(
        self,
        keyword_groups: list[KeywordGroupResponse],
    ) -> list[KeywordGroupResponse]:
        return [
            group
            for group in keyword_groups
            if group.count >= self._min_keyword_count
        ]

    def _build_prompt_variables(
        self,
        *,
        reviews: list[ReviewResponse],
        keyword_insights: KeywordInsightsResponse,
        selected_keyword_groups: list[KeywordGroupResponse],
    ) -> dict[str, Any]:
        review_statistics = self._build_review_statistics(reviews)

        return {
            "total_reviews": review_statistics["total_reviews"],
            "average_rating": review_statistics["average_rating"],
            "rating_distribution": self._to_prompt_json(
                review_statistics["rating_distribution"]
            ),
            "sentiment_distribution": self._to_prompt_json(
                review_statistics["sentiment_distribution"]
            ),
            "keyword_analyzed_reviews": keyword_insights.analyzed_reviews,
            "selected_keywords": self._to_prompt_json(
                [
                    self._serialize_keyword_group(group)
                    for group in selected_keyword_groups
                ]
            ),
        }

    def _build_review_statistics(
        self,
        reviews: list[ReviewResponse],
    ) -> dict[str, Any]:
        total_reviews = len(reviews)
        rating_counts = Counter(review.rating for review in reviews)
        sentiment_counts = Counter(
            review.sentiment.label
            for review in reviews
            if review.sentiment is not None
        )
        average_rating = (
            round(
                sum(review.rating for review in reviews) / total_reviews,
                2,
            )
            if total_reviews
            else 0
        )

        return {
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "rating_distribution": {
                str(rating): {
                    "count": rating_counts[rating],
                    "percentage": self._percentage(
                        rating_counts[rating],
                        total_reviews,
                    ),
                }
                for rating in range(1, 6)
            },
            "sentiment_distribution": {
                label: {
                    "count": sentiment_counts[label],
                    "percentage": self._percentage(
                        sentiment_counts[label],
                        total_reviews,
                    ),
                }
                for label in ("positive", "neutral", "negative")
            },
        }

    def _serialize_keyword_group(
        self,
        group: KeywordGroupResponse,
    ) -> dict[str, Any]:
        return {
            "keyword": group.keyword,
            "percentage": group.percentage,
            "comments": [
                self._serialize_comment(comment)
                for comment in group.comments[
                    : self._max_comments_per_keyword
                ]
            ],
        }

    @staticmethod
    def _serialize_comment(review: ReviewResponse) -> dict[str, Any]:
        return {
            "title": review.title,
            "text": review.text,
            "rating": review.rating,
            "sentiment": (
                review.sentiment.label if review.sentiment else None
            ),
            "sentiment_score": (
                review.sentiment.score if review.sentiment else None
            ),
            "created_at": review.created_at.isoformat(),
        }

    def _build_system_prompt(self, variables: dict[str, Any]) -> str:
        template = self._PROMPT_PATH.read_text(encoding="utf-8")

        return template.format(**variables)

    def _write_prompt_log(self, prompt: str) -> str:
        timestamp = datetime.now(UTC).isoformat()

        try:
            self._PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self._PROMPT_LOG_PATH.open(
                mode="a",
                encoding="utf-8",
            ) as prompt_log:
                prompt_log.write(
                    f"\n--- actionable insights prompt {timestamp} ---\n"
                )
                prompt_log.write(prompt)
                prompt_log.write("\n")
        except OSError:
            logger.warning("Failed to write actionable insights prompt log")

        return timestamp

    def _write_log_section(
        self,
        *,
        timestamp: str,
        title: str,
        content: str,
    ) -> None:
        try:
            self._PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self._PROMPT_LOG_PATH.open(
                mode="a",
                encoding="utf-8",
            ) as prompt_log:
                prompt_log.write(
                    f"\n--- actionable insights {title.lower()} "
                    f"{timestamp} ---\n"
                )
                prompt_log.write(content)
                prompt_log.write("\n")
        except OSError:
            logger.warning("Failed to write actionable insights log section")

    @staticmethod
    def _to_prompt_json(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "insights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "area": {"type": "string"},
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "summary": {"type": "string"},
                            "evidence_keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "recommended_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "area",
                            "severity",
                            "summary",
                            "evidence_keywords",
                            "recommended_actions",
                        ],
                    },
                },
            },
            "required": ["summary", "insights"],
        }

    def _parse_response(
        self,
        response: dict[str, Any],
    ) -> ActionableInsightsResponse:
        return ActionableInsightsResponse(
            generated=True,
            model=self._model,
            summary=response.get("summary"),
            insights=[
                ActionableInsightResponse(
                    area=insight.get("area", ""),
                    severity=insight.get("severity", "medium"),
                    summary=insight.get("summary", ""),
                    evidence_keywords=insight.get("evidence_keywords", []),
                    recommended_actions=insight.get(
                        "recommended_actions",
                        [],
                    ),
                )
                for insight in response.get("insights", [])
                if isinstance(insight, dict)
            ],
        )

    @staticmethod
    def _load_env_file() -> None:
        try:
            from dotenv import load_dotenv
        except ImportError:
            return

        load_dotenv()

    @staticmethod
    def _read_positive_int_env(
        *,
        name: str,
        default: int,
    ) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError:
            return default

        return value if value > 0 else default

    @staticmethod
    def _percentage(count: int, total: int) -> float:
        if total == 0:
            return 0

        return round((count / total) * 100, 2)
