from app.evaluation import EvaluationGates, evaluate_results


def test_evaluation_passes_when_real_images_are_not_called_ai() -> None:
    report = evaluate_results(
        [
            {"name": "real", "expected": "real", "result": {"verdict": {"label": "inconclusive", "confidence": "low", "ai_probability": 0.61}}},
            {"name": "ai", "expected": "ai", "result": {"verdict": {"label": "likely_ai_generated", "confidence": "medium", "ai_probability": 0.78}}},
        ],
        EvaluationGates(max_real_false_positive_rate=0.0, min_ai_recall=1.0, max_high_confidence_error_rate=0.0),
    )

    assert report["passed"] is True
    assert report["metrics"]["real_false_positive_rate"] == 0
    assert report["metrics"]["ai_recall"] == 1


def test_evaluation_fails_on_high_confidence_real_false_positive() -> None:
    report = evaluate_results(
        [
            {"name": "real", "expected": "real", "result": {"verdict": {"label": "likely_ai_generated", "confidence": "medium", "ai_probability": 0.82}}},
        ],
        EvaluationGates(max_real_false_positive_rate=0.0, min_ai_recall=0.0, max_high_confidence_error_rate=0.0),
    )

    assert report["passed"] is False
    assert report["counts"]["real_false_positive"] == 1
    assert report["counts"]["high_confidence_errors"] == 1
