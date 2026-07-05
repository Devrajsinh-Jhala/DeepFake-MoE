from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AI_EXPECTED = {"ai", "ai_generated", "synthetic", "fake"}
REAL_EXPECTED = {"real", "camera", "human", "authentic"}


@dataclass
class EvaluationGates:
    max_real_false_positive_rate: float = 0.0
    min_ai_recall: float = 0.5
    max_high_confidence_error_rate: float = 0.0


def evaluate_results(samples: list[dict[str, Any]], gates: EvaluationGates | None = None) -> dict[str, Any]:
    gates = gates or EvaluationGates()
    rows = []
    counts = {
        "total": 0,
        "expected_ai": 0,
        "expected_real": 0,
        "ai_true_positive": 0,
        "ai_false_negative_or_abstain": 0,
        "real_true_negative_or_abstain": 0,
        "real_false_positive": 0,
        "high_confidence_errors": 0,
    }

    for sample in samples:
        expected = _normalize_expected(sample.get("expected"))
        verdict = sample.get("result", {}).get("verdict", sample.get("verdict", {}))
        label = str(verdict.get("label") or "missing")
        confidence = str(verdict.get("confidence") or "none")
        ai_probability = verdict.get("ai_probability")
        counts["total"] += 1

        if expected == "ai":
            counts["expected_ai"] += 1
            correct = label == "likely_ai_generated"
            if correct:
                counts["ai_true_positive"] += 1
            else:
                counts["ai_false_negative_or_abstain"] += 1
        else:
            counts["expected_real"] += 1
            correct = label != "likely_ai_generated"
            if correct:
                counts["real_true_negative_or_abstain"] += 1
            else:
                counts["real_false_positive"] += 1

        if not correct and confidence in {"medium", "high"}:
            counts["high_confidence_errors"] += 1

        rows.append(
            {
                "name": sample.get("name") or sample.get("path") or f"sample_{counts['total']}",
                "expected": expected,
                "verdict": label,
                "confidence": confidence,
                "ai_probability": ai_probability,
                "correct_for_gate": correct,
            }
        )

    metrics = _metrics(counts)
    passed = (
        metrics["real_false_positive_rate"] <= gates.max_real_false_positive_rate
        and metrics["ai_recall"] >= gates.min_ai_recall
        and metrics["high_confidence_error_rate"] <= gates.max_high_confidence_error_rate
    )
    return {
        "passed": passed,
        "gates": {
            "max_real_false_positive_rate": gates.max_real_false_positive_rate,
            "min_ai_recall": gates.min_ai_recall,
            "max_high_confidence_error_rate": gates.max_high_confidence_error_rate,
        },
        "metrics": metrics,
        "counts": counts,
        "samples": rows,
    }


def _normalize_expected(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in AI_EXPECTED:
        return "ai"
    if normalized in REAL_EXPECTED:
        return "real"
    raise ValueError(f"Unknown expected label: {value!r}")


def _metrics(counts: dict[str, int]) -> dict[str, float]:
    expected_ai = counts["expected_ai"]
    expected_real = counts["expected_real"]
    total = counts["total"]
    return {
        "ai_recall": _ratio(counts["ai_true_positive"], expected_ai),
        "real_false_positive_rate": _ratio(counts["real_false_positive"], expected_real),
        "real_safety_rate": _ratio(counts["real_true_negative_or_abstain"], expected_real),
        "high_confidence_error_rate": _ratio(counts["high_confidence_errors"], total),
        "coverage_likely_ai_on_ai": _ratio(counts["ai_true_positive"], expected_ai),
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)
