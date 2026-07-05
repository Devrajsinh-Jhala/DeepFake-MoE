from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.analysis import analyze_image_bytes
from app.config import Settings
from app.evaluation import EvaluationGates, evaluate_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AI Deepfake Analyzer against a labeled golden image manifest.")
    parser.add_argument("manifest", type=Path, help="JSON manifest with samples: name, path, expected.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path for the evaluation report.")
    parser.add_argument("--enable-hf-model", action="store_true", help="Enable the configured Hugging Face detector ensemble.")
    parser.add_argument("--hf-model-ids", default=None, help="Comma-separated Hugging Face model ids to evaluate.")
    parser.add_argument("--max-real-fpr", type=float, default=0.0, help="Maximum allowed real-image false positive rate.")
    parser.add_argument("--min-ai-recall", type=float, default=0.5, help="Minimum required AI-image recall.")
    parser.add_argument("--max-high-confidence-error-rate", type=float, default=0.0)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = manifest_path.parent
    settings = Settings(
        enable_hf_model=args.enable_hf_model,
        hf_model_ids=args.hf_model_ids or Settings().hf_model_ids,
    )
    samples = []

    for item in payload.get("samples", []):
        image_path = (base_dir / item["path"]).resolve()
        result = analyze_image_bytes(
            image_path.read_bytes(),
            source_context={
                "input_filename": image_path.name,
                "content_type": _content_type(image_path),
                "attribution_boundary": "Golden-set local evaluation; no public attribution attempted.",
            },
            settings=settings,
        )
        samples.append(
            {
                "name": item.get("name") or image_path.name,
                "path": str(image_path),
                "expected": item["expected"],
                "result": result,
            }
        )

    report = evaluate_results(
        samples,
        EvaluationGates(
            max_real_false_positive_rate=args.max_real_fpr,
            min_ai_recall=args.min_ai_recall,
            max_high_confidence_error_rate=args.max_high_confidence_error_rate,
        ),
    )
    serialized = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0 if report["passed"] else 1


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suffix, "application/octet-stream")


if __name__ == "__main__":
    sys.exit(main())
