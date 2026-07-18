import re
from collections import Counter, defaultdict

from app.schemas.reviews import (
    KeywordGroupResponse,
    KeywordInsightsResponse,
    ReviewResponse,
)


class KeywordAnalyzer:
    _MIN_WORD_LENGTH = 3
    _TOP_KEYWORDS_LIMIT = 20
    _STOPWORDS = {
        "about",
        "after",
        "again",
        "also",
        "and",
        "any",
        "app",
        "are",
        "because",
        "been",
        "but",
        "can",
        "cant",
        "could",
        "did",
        "didnt",
        "does",
        "doesnt",
        "dont",
        "for",
        "from",
        "get",
        "got",
        "had",
        "has",
        "have",
        "having",
        "her",
        "him",
        "his",
        "how",
        "into",
        "its",
        "just",
        "like",
        "more",
        "much",
        "not",
        "now",
        "off",
        "one",
        "only",
        "our",
        "out",
        "over",
        "really",
        "she",
        "should",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "they",
        "this",
        "too",
        "use",
        "very",
        "was",
        "way",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "going",
        "don",
        "still",
        "didn",
        "doing",
        "first",
        "take",
        "ever",
        "good",
        "even"
    }

    def analyze_reviews(
        self,
        reviews: list[ReviewResponse],
    ) -> KeywordInsightsResponse:
        keyword_reviews = [
            review
            for review in reviews
            if self._include_in_keyword_analysis(review)
        ]

        if not keyword_reviews:
            return KeywordInsightsResponse(
                analyzed_reviews=0,
                keywords=[],
            )

        keyword_counts: Counter[str] = Counter()
        review_keywords: list[tuple[ReviewResponse, list[str]]] = []

        for review in keyword_reviews:
            tokens = [
                token
                for field_tokens in self._tokenize_review_fields(review)
                for token in field_tokens
            ]
            unique_tokens = list(dict.fromkeys(tokens))
            keyword_counts.update(unique_tokens)
            review_keywords.append((review, unique_tokens))

        comments_by_keyword = self._assign_comments_to_keywords(
            review_keywords=review_keywords,
            keyword_counts=keyword_counts,
        )

        total_reviews = len(keyword_reviews)
        groups = [
            KeywordGroupResponse(
                keyword=keyword,
                count=count,
                percentage=self._percentage(count, total_reviews),
                comments=comments_by_keyword[keyword],
            )
            for keyword, count in keyword_counts.most_common(
                self._TOP_KEYWORDS_LIMIT
            )
            if comments_by_keyword[keyword]
        ]

        return KeywordInsightsResponse(
            analyzed_reviews=total_reviews,
            keywords=groups,
        )

    @staticmethod
    def _include_in_keyword_analysis(review: ReviewResponse) -> bool:
        sentiment = review.sentiment.label if review.sentiment else None

        if review.rating == 5 and sentiment == "neutral":
            return False

        return sentiment in {"negative", "neutral"} or review.rating <= 3

    def _tokenize_review_fields(
        self,
        review: ReviewResponse,
    ) -> list[list[str]]:
        return [
            self._tokenize_text(review.title),
            self._tokenize_text(review.text),
        ]

    def _tokenize_text(self, text: str) -> list[str]:
        text = text.lower()
        words = re.findall(r"[a-z][a-z']+", text)

        return [
            word.replace("'", "")
            for word in words
            if self._is_keyword_candidate(word.replace("'", ""))
        ]

    def _is_keyword_candidate(self, word: str) -> bool:
        return (
            len(word) >= self._MIN_WORD_LENGTH
            and word not in self._STOPWORDS
        )

    def _assign_comments_to_keywords(
        self,
        *,
        review_keywords: list[tuple[ReviewResponse, list[str]]],
        keyword_counts: Counter[str],
    ) -> dict[str, list[ReviewResponse]]:
        comments_by_keyword: dict[str, list[ReviewResponse]] = defaultdict(list)

        for review, keywords in review_keywords:
            if not keywords:
                continue

            primary_keyword = self._select_primary_keyword(
                keywords=keywords,
                keyword_counts=keyword_counts,
            )
            comments_by_keyword[primary_keyword].append(review)

        return comments_by_keyword

    @staticmethod
    def _select_primary_keyword(
        *,
        keywords: list[str],
        keyword_counts: Counter[str],
    ) -> str:
        return max(
            keywords,
            key=lambda keyword: keyword_counts[keyword],
        )

    @staticmethod
    def _percentage(count: int, total: int) -> float:
        if total == 0:
            return 0

        return round((count / total) * 100, 2)
