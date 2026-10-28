"""
Deterministic keyword-based complaint classifier.

Uses category keyword lists from config/categories.yaml.
Confidence is the ratio of matched keywords to total keywords in the winning category.
This is NOT a statistically calibrated probability — it is a rule-matching score.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from app.config import get_settings


@dataclass
class ClassificationResult:
    category_code: str
    category_name: str
    confidence: float
    matched_keywords: list[str]
    evidence: str
    rule_id: str
    rule_version: str


class ComplaintClassifier:
    """Deterministic keyword-based classifier."""

    RULE_ID = "KEYWORD_CLASSIFIER_V1"
    RULE_VERSION = "1.0.0"
    FALLBACK_CODE = "OTHER"

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_settings().config_dir / "categories.yaml"
        self._categories = self._load_categories(config_path)
        self._version = "1.0.0"

    def _load_categories(self, path: Path) -> list[dict]:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data["categories"]

    def classify(self, text: str, subject: str = "") -> ClassificationResult:
        """
        Classify complaint text using keyword matching.

        Args:
            text: The complaint description/body
            subject: Optional complaint subject line

        Returns:
            ClassificationResult with category, confidence, and evidence
        """
        combined = f"{subject} {text}".lower()

        best_category = None
        best_count = 0
        best_matched = []

        for cat in self._categories:
            if cat["code"] == self.FALLBACK_CODE:
                continue
            keywords = cat.get("keywords", [])
            matched = [kw for kw in keywords if kw.lower() in combined]
            if len(matched) > best_count:
                best_count = len(matched)
                best_category = cat
                best_matched = matched

        if best_category is None or best_count == 0:
            # Fall back to OTHER
            fallback = next(c for c in self._categories if c["code"] == self.FALLBACK_CODE)
            return ClassificationResult(
                category_code=self.FALLBACK_CODE,
                category_name=fallback["name"],
                confidence=0.0,
                matched_keywords=[],
                evidence="No keywords matched; defaulting to OTHER",
                rule_id=self.RULE_ID,
                rule_version=self.RULE_VERSION,
            )

        total_kws = len(best_category.get("keywords", []))
        confidence = round(best_count / total_kws, 4) if total_kws > 0 else 0.0

        evidence = json.dumps({
            "matched_keywords": best_matched,
            "total_category_keywords": total_kws,
            "match_count": best_count,
        })

        return ClassificationResult(
            category_code=best_category["code"],
            category_name=best_category["name"],
            confidence=confidence,
            matched_keywords=best_matched,
            evidence=evidence,
            rule_id=self.RULE_ID,
            rule_version=self.RULE_VERSION,
        )

    def get_category_names(self) -> dict[str, str]:
        """Return mapping of code -> name."""
        return {cat["code"]: cat["name"] for cat in self._categories}

    def is_safety_category(self, category_code: str) -> bool:
        """Return True if the category has safety_risk=True."""
        for cat in self._categories:
            if cat["code"] == category_code:
                return cat.get("safety_risk", False)
        return False


# Module-level singleton
_classifier: Optional[ComplaintClassifier] = None


def get_classifier() -> ComplaintClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ComplaintClassifier()
    return _classifier
