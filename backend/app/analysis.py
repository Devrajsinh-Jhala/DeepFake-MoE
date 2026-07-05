from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import ExifTags, Image, ImageChops, ImageFilter, ImageStat, PngImagePlugin, UnidentifiedImageError

from .config import Settings, get_settings


GENERATIVE_MARKERS = {
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dalle",
    "comfyui",
    "automatic1111",
    "invokeai",
    "firefly",
    "imagen",
    "flux",
    "fooocus",
    "novelai",
}

EDITING_MARKERS = {
    "photoshop",
    "lightroom",
    "gimp",
    "affinity",
    "snapseed",
    "canva",
    "pixlr",
}

DEFAULT_MODEL_PROFILE = {
    "weight": 0.55,
    "ai_threshold": 0.72,
    "real_threshold": 0.28,
    "note": "Default detector calibration. Validate this model on the local golden set before trusting it in production.",
}

MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "Ateeqq/ai-vs-human-image-detector": {
        "weight": 0.72,
        "ai_threshold": 0.72,
        "real_threshold": 0.28,
        "note": "Strong visual detector; kept below full weight because portrait-style real photos can false-positive.",
    },
    "dima806/ai_vs_real_image_detection": {
        "weight": 0.35,
        "ai_threshold": 0.82,
        "real_threshold": 0.22,
        "note": "CIFAKE-lineage detector; down-weighted for real-world social, portrait, and compressed images.",
    },
    "jacoballessio/ai-image-detect-distilled": {
        "weight": 0.70,
        "ai_threshold": 0.60,
        "real_threshold": 0.30,
        "note": "Distilled detector used as a counterbalance against portrait false positives.",
    },
    "SadraCoding/SDXL-Deepfake-Detector": {
        "weight": 0.65,
        "ai_threshold": 0.70,
        "real_threshold": 0.30,
        "portrait_only": True,
        "min_portrait_score": 0.65,
        "expert_group": "portrait_specialist",
        "note": "Portrait-only specialist. It is skipped for non-portrait images so it cannot dominate generic scenes.",
    },
}


@dataclass
class DetectorSignal:
    name: str
    status: str
    label: str
    ai_probability: float | None
    manipulation_probability: float | None
    confidence: str
    evidence: list[str]
    weight: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "label": self.label,
            "ai_probability": self.ai_probability,
            "manipulation_probability": self.manipulation_probability,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "weight": self.weight,
        }


def analyze_image_bytes(
    image_bytes: bytes,
    *,
    source_context: dict | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    started = time.perf_counter()
    image = _load_image(image_bytes, settings)
    metadata = extract_metadata(image, image_bytes)
    hashes = compute_hashes(image, image_bytes)
    c2pa = inspect_c2pa(image_bytes, metadata["format"])
    forensics = compute_forensics(image, image_bytes)

    detectors = [
        metadata_detector(metadata, c2pa),
        forensic_detector(forensics),
    ]
    detectors.extend(huggingface_detectors(image, settings))
    verdict = aggregate_verdict(detectors, metadata, c2pa, forensics)
    layers = build_layers(metadata, hashes, c2pa, forensics, detectors, source_context)
    analytical_layers = build_analytical_layer_breakdown(image, image_bytes, metadata, c2pa, forensics, detectors)
    explainability = build_explainability(verdict, detectors, metadata, c2pa, forensics, analytical_layers)

    result = {
        "schema_version": "0.1.0",
        "status": "completed",
        "verdict": verdict,
        "summary": {
            "headline": _headline(verdict["label"]),
            "plain_language": _plain_language(verdict),
            "limitations": [
                "Image authenticity cannot be proven from pixels alone.",
                "Social platforms often strip metadata, so missing EXIF is not proof of AI generation.",
                "No login scraping, private account access, face-search, or private identity inference was performed.",
            ],
        },
        "explainability": explainability,
        "analytical_layers": analytical_layers,
        "source_context": source_context or {},
        "layers": layers,
        "technical_appendix": {
            "metadata": metadata,
            "hashes": hashes,
            "c2pa": c2pa,
            "forensics": forensics,
            "analytical_layers": analytical_layers,
            "detectors": [detector.as_dict() for detector in detectors],
            "runtime_ms": round((time.perf_counter() - started) * 1000, 2),
            "reproducibility": {
                "pipeline": "metadata + C2PA/provenance + perceptual hashes + compression/noise checks + pretrained open-source model ensemble",
                "model_training": "No custom model was trained by this application.",
            },
        },
        "next_steps": [
            "Preserve the original file and URLs if this may become evidence.",
            "Use platform reporting tools for non-consensual intimate imagery or impersonation.",
            "Treat the verdict as an evidence summary, not a legal or forensic certificate.",
        ],
    }
    return result


def _load_image(image_bytes: bytes, settings: Settings) -> Image.Image:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded content is not a readable image.") from exc

    width, height = image.size
    if width * height > settings.max_image_pixels:
        raise ValueError("Image dimensions exceed the configured safety limit.")
    return image


def extract_metadata(image: Image.Image, image_bytes: bytes) -> dict[str, Any]:
    exif = {}
    gps_present = False
    try:
        raw_exif = image.getexif()
        for tag_id, value in raw_exif.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            if tag == "GPSInfo":
                gps_present = True
                exif[tag] = "[redacted: GPS metadata present]"
                continue
            exif[tag] = _safe_metadata_value(value)
    except Exception:
        exif = {}

    png_text = {}
    if isinstance(image, PngImagePlugin.PngImageFile):
        for key, value in image.text.items():
            png_text[key] = str(value)[:1000]

    xmp = extract_xmp(image_bytes)
    marker_text = _metadata_marker_text(exif, png_text, xmp)
    generative_markers = sorted(marker for marker in GENERATIVE_MARKERS if marker in marker_text)
    editing_markers = sorted(marker for marker in EDITING_MARKERS if marker in marker_text)
    software_values = _collect_software_values(exif, png_text, xmp, generative_markers, editing_markers)

    return {
        "format": image.format or "unknown",
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "has_exif": bool(exif),
        "gps_present": gps_present,
        "exif": exif,
        "png_text": png_text,
        "xmp_present": bool(xmp),
        "xmp_excerpt": _xmp_report_summary(xmp, generative_markers, editing_markers),
        "software_values": software_values,
        "generative_markers": generative_markers,
        "editing_markers": editing_markers,
    }


def extract_xmp(image_bytes: bytes) -> str | None:
    lower = image_bytes.lower()
    start = lower.find(b"<x:xmpmeta")
    if start == -1:
        start = lower.find(b"<?xpacket")
    if start == -1:
        return None
    end = lower.find(b"</x:xmpmeta>", start)
    if end == -1:
        end = lower.find(b"<?xpacket end=", start)
    if end == -1:
        end = min(start + 6000, len(image_bytes))
    else:
        end = min(end + 12, len(image_bytes))
    return image_bytes[start:end].decode("utf-8", errors="replace")


def compute_hashes(image: Image.Image, image_bytes: bytes) -> dict[str, Any]:
    rgb = image.convert("RGB")
    return {
        "sha256": hashlib.sha256(image_bytes).hexdigest(),
        "average_hash": _average_hash(rgb),
        "difference_hash": _difference_hash(rgb),
    }


def inspect_c2pa(image_bytes: bytes, image_format: str | None) -> dict[str, Any]:
    executable = shutil.which("c2patool") or shutil.which("c2pa")
    if not executable:
        return {
            "status": "unavailable",
            "claim": None,
            "evidence": ["No c2patool/c2pa executable was found on PATH."],
        }

    suffix = f".{(image_format or 'img').lower()}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(image_bytes)
        temp_path = Path(handle.name)

    try:
        completed = subprocess.run(
            [executable, str(temp_path), "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        if completed.returncode != 0:
            return {
                "status": "not_found",
                "claim": None,
                "evidence": ["No readable C2PA manifest was found."],
            }
        parsed = json.loads(completed.stdout)
        text = json.dumps(parsed).lower()
        generated = any(marker in text for marker in ("ai", "generated", "synthetic", "model"))
        return {
            "status": "found",
            "claim": "ai_generated_or_synthetic" if generated else "content_credentials_present",
            "manifest": parsed,
            "evidence": ["C2PA/content credentials metadata was readable."],
        }
    except Exception as exc:
        return {
            "status": "error",
            "claim": None,
            "evidence": [f"C2PA inspection failed: {exc.__class__.__name__}."],
        }
    finally:
        temp_path.unlink(missing_ok=True)


def compute_forensics(image: Image.Image, image_bytes: bytes) -> dict[str, Any]:
    rgb = image.convert("RGB")
    ela = _ela_metrics(rgb)
    noise = _noise_metrics(rgb)
    entropy = round(float(image.convert("L").entropy()), 4)
    jpeg_markers = _jpeg_marker_summary(image_bytes)
    quality = _input_quality_metrics(image, image_bytes, entropy)

    manipulation_score = _clamp(
        0.42 * ela["normalized_mean"]
        + 0.38 * noise["tile_inconsistency"]
        + 0.20 * jpeg_markers["double_quantization_hint"]
    )
    artificiality_score = _clamp(
        0.35 * (1.0 - min(entropy / 8.0, 1.0))
        + 0.30 * noise["low_noise_hint"]
        + 0.35 * ela["normalized_mean"]
    )

    return {
        "ela": ela,
        "noise": noise,
        "entropy": entropy,
        "jpeg_markers": jpeg_markers,
        "quality": quality,
        "manipulation_score": round(manipulation_score, 4),
        "artificiality_score": round(artificiality_score, 4),
        "notes": [
            "Forensic scores are heuristic signals and are weaker than a validated detector or signed provenance.",
            "Cropping, screenshots, and social-media recompression can mimic manipulation artifacts.",
        ],
    }


def build_analytical_layer_breakdown(
    image: Image.Image,
    image_bytes: bytes,
    metadata: dict[str, Any],
    c2pa: dict[str, Any],
    forensics: dict[str, Any],
    detectors: list[DetectorSignal],
) -> list[dict[str, Any]]:
    rgb = image.convert("RGB")
    gray = rgb.convert("L")
    rgb_array = np.asarray(rgb, dtype=np.float32)
    gray_array = np.asarray(gray, dtype=np.float32)
    edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    luminance = _luminance_layer(gray_array)
    chroma = _chroma_layer(rgb_array)
    edge_geometry = _edge_geometry_layer(edges)
    frequency = _frequency_layer(gray_array)
    tile_anomalies = _tile_anomaly_layer(gray_array, edges)
    model_layer = _model_consensus_layer(detectors)

    return [
        _evidence_layer(
            layer_id="source_provenance",
            name="Source, Metadata, And Provenance",
            layer_type="container_metadata",
            question="Does the file carry provenance or generation/editing metadata?",
            method="EXIF/XMP/PNG text extraction plus optional C2PA manifest inspection.",
            ai_signal=0.9 if metadata["generative_markers"] or c2pa.get("claim") == "ai_generated_or_synthetic" else 0.5,
            manipulation_signal=0.62 if metadata["editing_markers"] else 0.25,
            confidence="medium" if metadata["generative_markers"] or c2pa.get("claim") else "low",
            evidence=[
                f"Generative markers: {', '.join(metadata['generative_markers']) or 'none'}.",
                f"Editing markers: {', '.join(metadata['editing_markers']) or 'none'}.",
                f"C2PA status: {c2pa['status']}.",
                "EXIF metadata present." if metadata["has_exif"] else "No EXIF metadata found.",
            ],
            metrics={
                "has_exif": metadata["has_exif"],
                "c2pa_status": c2pa["status"],
                "generative_marker_count": len(metadata["generative_markers"]),
                "editing_marker_count": len(metadata["editing_markers"]),
            },
            limitations=[
                "Most social platforms strip metadata.",
                "Metadata can be added, removed, or forged.",
            ],
        ),
        _evidence_layer(
            layer_id="input_quality",
            name="Input Quality And Robustness",
            layer_type="robustness_check",
            question="Is the file quality strong enough for high-confidence automated detection?",
            method="Check resolution, file size, aspect ratio, entropy, and format conditions known to affect detector reliability.",
            ai_signal=0.5,
            manipulation_signal=forensics["quality"]["risk_score"],
            confidence="low",
            evidence=forensics["quality"]["evidence"],
            metrics=forensics["quality"],
            limitations=[
                "Low quality does not mean fake.",
                "This layer adjusts confidence; it is not an AI detector by itself.",
            ],
        ),
        model_layer,
        _evidence_layer(
            layer_id="luminance",
            name="Luminance Layer",
            layer_type="pixel_decomposition",
            question="Do brightness/contrast statistics look unusually flat, clipped, or over-regularized?",
            method="Analyze grayscale entropy, contrast, clipping, and local brightness variation.",
            ai_signal=luminance["ai_signal"],
            manipulation_signal=luminance["manipulation_signal"],
            confidence="low",
            evidence=luminance["evidence"],
            metrics=luminance["metrics"],
            limitations=[
                "Studio lighting, compression, and screenshots can look smooth or clipped.",
                "This layer is a weak supporting signal only.",
            ],
        ),
        _evidence_layer(
            layer_id="chroma",
            name="Chroma And Color Layer",
            layer_type="pixel_decomposition",
            question="Do color statistics show unusually uniform or synthetic-looking saturation?",
            method="Analyze RGB channel spread, channel correlation, and saturation distribution.",
            ai_signal=chroma["ai_signal"],
            manipulation_signal=chroma["manipulation_signal"],
            confidence="low",
            evidence=chroma["evidence"],
            metrics=chroma["metrics"],
            limitations=[
                "Color grading and camera profiles can dominate this signal.",
                "This does not identify which generator, if any, created the image.",
            ],
        ),
        _evidence_layer(
            layer_id="edge_geometry",
            name="Edge And Geometry Layer",
            layer_type="structural_decomposition",
            question="Are edges too inconsistent, too clean, or locally unnatural?",
            method="Run edge extraction and compare edge density/variance across tiles.",
            ai_signal=edge_geometry["ai_signal"],
            manipulation_signal=edge_geometry["manipulation_signal"],
            confidence="low",
            evidence=edge_geometry["evidence"],
            metrics=edge_geometry["metrics"],
            limitations=[
                "Texture-rich real scenes and bokeh-heavy portraits can both skew edge statistics.",
                "This is anomaly evidence, not identity or attribution evidence.",
            ],
        ),
        _evidence_layer(
            layer_id="noise_residual",
            name="Noise Residual Layer",
            layer_type="forensic_residual",
            question="Is sensor-like noise consistent across image regions?",
            method="Estimate edge/noise residual variance across a 4x4 tile grid.",
            ai_signal=round(0.35 + forensics["noise"]["low_noise_hint"] * 0.45, 4),
            manipulation_signal=forensics["noise"]["tile_inconsistency"],
            confidence="low",
            evidence=[
                f"Noise tile variance mean: {forensics['noise']['tile_variance_mean']}.",
                f"Noise tile inconsistency: {forensics['noise']['tile_inconsistency']}.",
                f"Low-noise hint: {forensics['noise']['low_noise_hint']}.",
            ],
            metrics=forensics["noise"],
            limitations=[
                "Denoising, resizing, and platform recompression can erase normal sensor noise.",
                "Generated images can also contain synthetic noise.",
            ],
        ),
        _evidence_layer(
            layer_id="compression_ela",
            name="Compression And ELA Layer",
            layer_type="forensic_residual",
            question="Do recompression artifacts suggest editing, screenshots, or pasted regions?",
            method="Recompress image to JPEG quality 90 and measure error-level deltas plus JPEG markers.",
            ai_signal=forensics["artificiality_score"],
            manipulation_signal=forensics["manipulation_score"],
            confidence="low",
            evidence=[
                f"ELA normalized mean: {forensics['ela']['normalized_mean']}.",
                f"JPEG DQT marker count: {forensics['jpeg_markers']['dqt_marker_count']}.",
                f"Double-quantization hint: {forensics['jpeg_markers']['double_quantization_hint']}.",
            ],
            metrics={
                "ela": forensics["ela"],
                "jpeg_markers": forensics["jpeg_markers"],
                "manipulation_score": forensics["manipulation_score"],
                "artificiality_score": forensics["artificiality_score"],
            },
            limitations=[
                "ELA is fragile and often reacts to normal recompression.",
                "A clean ELA result does not prove authenticity.",
            ],
        ),
        _evidence_layer(
            layer_id="frequency",
            name="Frequency Spectrum Layer",
            layer_type="frequency_decomposition",
            question="Does the image have unusual high-frequency or overly smooth spectral structure?",
            method="Compute grayscale FFT energy distribution across low/mid/high frequency bands.",
            ai_signal=frequency["ai_signal"],
            manipulation_signal=frequency["manipulation_signal"],
            confidence="low",
            evidence=frequency["evidence"],
            metrics=frequency["metrics"],
            limitations=[
                "Frequency patterns are affected by camera sharpening, resizing, and compression.",
                "This layer is useful for consistency checks, not stand-alone classification.",
            ],
        ),
        _evidence_layer(
            layer_id="tile_regions",
            name="Tile Region Anomaly Layer",
            layer_type="spatial_decomposition",
            question="Do any local regions behave differently from the rest of the image?",
            method="Split the image into a 4x4 grid and compare brightness/noise/edge residual z-scores.",
            ai_signal=tile_anomalies["ai_signal"],
            manipulation_signal=tile_anomalies["manipulation_signal"],
            confidence="low",
            evidence=tile_anomalies["evidence"],
            metrics=tile_anomalies["metrics"],
            limitations=[
                "This identifies suspicious regions, not the cause.",
                "Natural subject/background boundaries often produce regional differences.",
            ],
        ),
    ]


def _evidence_layer(
    *,
    layer_id: str,
    name: str,
    layer_type: str,
    question: str,
    method: str,
    ai_signal: float,
    manipulation_signal: float,
    confidence: str,
    evidence: list[str],
    metrics: dict[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    ai_signal = round(_clamp(ai_signal), 4)
    manipulation_signal = round(_clamp(manipulation_signal), 4)
    if ai_signal >= 0.72 and confidence in {"medium", "high"}:
        conclusion = "supports_ai_generated"
    elif ai_signal <= 0.28 and manipulation_signal < 0.45:
        conclusion = "supports_real_or_camera_origin"
    elif manipulation_signal >= 0.65 and confidence in {"medium", "high"}:
        conclusion = "supports_manipulation_or_editing"
    elif ai_signal >= 0.58 or manipulation_signal >= 0.5:
        conclusion = "weak_anomaly"
    else:
        conclusion = "neutral_or_inconclusive"

    return {
        "id": layer_id,
        "name": name,
        "type": layer_type,
        "question": question,
        "method": method,
        "conclusion": conclusion,
        "ai_signal": ai_signal,
        "manipulation_signal": manipulation_signal,
        "confidence": confidence,
        "evidence": evidence,
        "metrics": metrics,
        "limitations": limitations,
    }


def _luminance_layer(gray_array: np.ndarray) -> dict[str, Any]:
    normalized = gray_array / 255.0
    entropy = _array_entropy(gray_array)
    contrast = float(np.std(normalized))
    clipped_dark = float(np.mean(gray_array <= 3))
    clipped_bright = float(np.mean(gray_array >= 252))
    tile_means = _tile_feature_values(gray_array, lambda tile: float(np.mean(tile) / 255.0))
    local_variation = float(np.std(tile_means)) if tile_means else 0.0
    flatness_hint = _clamp((0.12 - contrast) / 0.12)
    clipping_hint = _clamp((clipped_dark + clipped_bright - 0.04) / 0.16)
    uneven_lighting_hint = _clamp((local_variation - 0.24) / 0.36)
    ai_signal = _clamp(0.35 + 0.25 * flatness_hint + 0.20 * clipping_hint + 0.20 * (1 - min(entropy / 8.0, 1.0)))
    evidence = [
        f"Grayscale entropy: {entropy:.3f}.",
        f"Luminance contrast standard deviation: {contrast:.3f}.",
        f"Clipped dark/bright pixels: {(clipped_dark + clipped_bright):.2%}.",
        f"Local brightness variation across tiles: {local_variation:.3f}.",
    ]
    return {
        "ai_signal": ai_signal,
        "manipulation_signal": _clamp(0.25 + clipping_hint * 0.35 + uneven_lighting_hint * 0.25),
        "evidence": evidence,
        "metrics": {
            "entropy": round(entropy, 4),
            "contrast_std": round(contrast, 4),
            "clipped_dark_ratio": round(clipped_dark, 4),
            "clipped_bright_ratio": round(clipped_bright, 4),
            "tile_brightness_std": round(local_variation, 4),
            "uneven_lighting_hint": round(uneven_lighting_hint, 4),
        },
    }


def _chroma_layer(rgb_array: np.ndarray) -> dict[str, Any]:
    normalized = rgb_array / 255.0
    channel_means = np.mean(normalized, axis=(0, 1))
    channel_stds = np.std(normalized, axis=(0, 1))
    max_channel = np.max(normalized, axis=2)
    min_channel = np.min(normalized, axis=2)
    saturation = np.where(max_channel == 0, 0, (max_channel - min_channel) / (max_channel + 1e-6))
    saturation_mean = float(np.mean(saturation))
    saturation_std = float(np.std(saturation))
    channel_balance = float(np.std(channel_means))
    uniform_color_hint = _clamp((0.12 - saturation_std) / 0.12)
    oversaturation_hint = _clamp((saturation_mean - 0.62) / 0.28)
    ai_signal = _clamp(0.35 + 0.25 * uniform_color_hint + 0.20 * oversaturation_hint + 0.10 * _clamp(channel_balance / 0.2))
    evidence = [
        f"Mean saturation: {saturation_mean:.3f}.",
        f"Saturation variation: {saturation_std:.3f}.",
        f"RGB channel mean balance spread: {channel_balance:.3f}.",
    ]
    return {
        "ai_signal": ai_signal,
        "manipulation_signal": _clamp(0.25 + 0.35 * oversaturation_hint + 0.25 * uniform_color_hint),
        "evidence": evidence,
        "metrics": {
            "rgb_channel_means": [round(float(value), 4) for value in channel_means],
            "rgb_channel_stds": [round(float(value), 4) for value in channel_stds],
            "saturation_mean": round(saturation_mean, 4),
            "saturation_std": round(saturation_std, 4),
            "channel_balance_spread": round(channel_balance, 4),
        },
    }


def _edge_geometry_layer(edges: np.ndarray) -> dict[str, Any]:
    normalized = edges / 255.0
    edge_density = float(np.mean(normalized > 0.12))
    edge_strength = float(np.mean(normalized))
    tile_edges = _tile_feature_values(edges, lambda tile: float(np.mean(tile) / 255.0))
    tile_std = float(np.std(tile_edges)) if tile_edges else 0.0
    too_clean_hint = _clamp((0.045 - edge_density) / 0.045)
    inconsistency_hint = _clamp(tile_std / 0.18)
    ai_signal = _clamp(0.35 + 0.25 * too_clean_hint + 0.25 * inconsistency_hint)
    evidence = [
        f"Edge density: {edge_density:.3f}.",
        f"Average edge strength: {edge_strength:.3f}.",
        f"Edge variation across tiles: {tile_std:.3f}.",
    ]
    return {
        "ai_signal": ai_signal,
        "manipulation_signal": _clamp(0.25 + 0.5 * inconsistency_hint),
        "evidence": evidence,
        "metrics": {
            "edge_density": round(edge_density, 4),
            "edge_strength_mean": round(edge_strength, 4),
            "tile_edge_std": round(tile_std, 4),
        },
    }


def _frequency_layer(gray_array: np.ndarray) -> dict[str, Any]:
    small = np.asarray(Image.fromarray(gray_array.astype(np.uint8)).resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32)
    small = small - float(np.mean(small))
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(small)))
    energy = spectrum**2
    height, width = energy.shape
    y, x = np.ogrid[:height, :width]
    center_y = (height - 1) / 2.0
    center_x = (width - 1) / 2.0
    radius = np.sqrt((y - center_y) ** 2 + (x - center_x) ** 2)
    max_radius = float(np.max(radius)) or 1.0
    low = energy[radius <= max_radius * 0.18].sum()
    mid = energy[(radius > max_radius * 0.18) & (radius <= max_radius * 0.45)].sum()
    high = energy[radius > max_radius * 0.45].sum()
    total = float(low + mid + high + 1e-6)
    low_ratio = float(low / total)
    mid_ratio = float(mid / total)
    high_ratio = float(high / total)
    smooth_hint = _clamp((0.07 - high_ratio) / 0.07)
    noisy_hint = _clamp((high_ratio - 0.38) / 0.22)
    ai_signal = _clamp(0.35 + 0.3 * smooth_hint + 0.15 * noisy_hint)
    evidence = [
        f"Low-frequency energy ratio: {low_ratio:.3f}.",
        f"Mid-frequency energy ratio: {mid_ratio:.3f}.",
        f"High-frequency energy ratio: {high_ratio:.3f}.",
    ]
    return {
        "ai_signal": ai_signal,
        "manipulation_signal": _clamp(0.25 + 0.35 * noisy_hint + 0.2 * smooth_hint),
        "evidence": evidence,
        "metrics": {
            "low_frequency_ratio": round(low_ratio, 4),
            "mid_frequency_ratio": round(mid_ratio, 4),
            "high_frequency_ratio": round(high_ratio, 4),
            "smooth_frequency_hint": round(smooth_hint, 4),
            "noisy_frequency_hint": round(noisy_hint, 4),
        },
    }


def _tile_anomaly_layer(gray_array: np.ndarray, edges: np.ndarray) -> dict[str, Any]:
    tile_rows = _tile_stats(gray_array, edges)
    if not tile_rows:
        return {
            "ai_signal": 0.5,
            "manipulation_signal": 0.25,
            "evidence": ["Tile analysis was not available."],
            "metrics": {"tiles": []},
        }
    brightness = np.array([tile["brightness"] for tile in tile_rows], dtype=np.float32)
    noise = np.array([tile["noise"] for tile in tile_rows], dtype=np.float32)
    edge = np.array([tile["edge"] for tile in tile_rows], dtype=np.float32)
    anomaly_scores = _z_scores(brightness) + _z_scores(noise) + _z_scores(edge)
    for tile, score in zip(tile_rows, anomaly_scores, strict=False):
        tile["anomaly_score"] = round(float(score), 4)
    max_score = float(np.max(anomaly_scores)) if len(anomaly_scores) else 0.0
    mean_score = float(np.mean(anomaly_scores)) if len(anomaly_scores) else 0.0
    for tile in tile_rows:
        severity = float(tile["anomaly_score"]) / (max_score + 1e-6) if max_score else 0.0
        tile["severity"] = round(_clamp(severity), 4)
        tile["severity_band"] = _severity_band(severity)
    top_tiles = sorted(tile_rows, key=lambda item: item["anomaly_score"], reverse=True)[:4]
    high_tiles = [tile for tile in tile_rows if tile["severity_band"] == "high"]
    anomaly_hint = _clamp((max_score - 3.0) / 5.0)
    evidence = [
        f"Strongest tile anomaly score: {max_score:.3f}.",
        f"Mean tile anomaly score: {mean_score:.3f}.",
        f"Region map: {len(tile_rows)} tiles analyzed; {len(high_tiles)} high-severity regional differences.",
        "Top anomalous tiles: "
        + ", ".join(f"row {tile['row']} col {tile['col']} score {tile['anomaly_score']}" for tile in top_tiles)
        + ".",
    ]
    return {
        "ai_signal": _clamp(0.35 + 0.25 * anomaly_hint),
        "manipulation_signal": _clamp(0.25 + 0.55 * anomaly_hint),
        "evidence": evidence,
        "metrics": {
            "max_tile_anomaly_score": round(max_score, 4),
            "mean_tile_anomaly_score": round(mean_score, 4),
            "high_severity_tile_count": len(high_tiles),
            "tile_grid": sorted(tile_rows, key=lambda item: (item["row"], item["col"])),
            "top_tiles": top_tiles,
        },
    }


def _model_consensus_layer(detectors: list[DetectorSignal]) -> dict[str, Any]:
    model_signals = [
        detector for detector in detectors if detector.name.startswith("hf:") and detector.status == "ok" and detector.ai_probability is not None
    ]
    ensemble = next((detector for detector in detectors if detector.name == "open_source_model_ensemble" and detector.status == "ok"), None)
    values = [float(detector.ai_probability) for detector in model_signals if detector.ai_probability is not None]
    if not values:
        return _evidence_layer(
            layer_id="visual_model_consensus",
            name="Visual Model Consensus Layer",
            layer_type="pretrained_model_inference",
            question="Do pretrained visual detectors classify the image as AI-generated?",
            method="Run configured Hugging Face image-classification detectors and aggregate votes.",
            ai_signal=0.5,
            manipulation_signal=0.25,
            confidence="none",
            evidence=["No visual model scores were available."],
            metrics={"enabled_models": 0},
            limitations=[
                "Model inference must be enabled with AIDA_ENABLE_HF_MODEL=true.",
                "No model score means the final verdict relies on non-model evidence only.",
            ],
        )

    ai_votes = sum(detector.label == "model_likely_ai_generated" for detector in model_signals)
    real_votes = sum(detector.label == "model_likely_human_or_real" for detector in model_signals)
    disagreement = float(max(values) - min(values)) if len(values) >= 2 else 0.0
    confidence = ensemble.confidence if ensemble else ("medium" if disagreement < 0.35 else "low")
    average = float(ensemble.ai_probability) if ensemble and ensemble.ai_probability is not None else _weighted_average(
        values,
        [float(detector.weight or DEFAULT_MODEL_PROFILE["weight"]) for detector in model_signals],
    )
    return _evidence_layer(
        layer_id="visual_model_consensus",
        name="Visual Model Consensus Layer",
        layer_type="pretrained_model_inference",
        question="Do pretrained visual detectors classify the image as AI-generated?",
        method="Run configured Hugging Face image-classification detectors and aggregate votes.",
        ai_signal=average,
        manipulation_signal=0.25,
        confidence=confidence,
        evidence=[
            f"{ai_votes}/{len(values)} models voted AI-generated.",
            f"{real_votes}/{len(values)} models voted real/human-origin.",
            f"Model disagreement range: {disagreement:.3f}.",
            f"Reliability-weighted model average: {average:.3f}.",
            *[detector.evidence[0] for detector in model_signals if detector.evidence],
        ],
        metrics={
            "enabled_models": len(values),
            "ai_votes": ai_votes,
            "real_votes": real_votes,
            "inconclusive_votes": len(values) - ai_votes - real_votes,
            "average_ai_probability": round(average, 4),
            "raw_average_ai_probability": round(float(np.mean(values)), 4),
            "disagreement_range": round(disagreement, 4),
            "model_scores": [
                {
                    "name": detector.name,
                    "ai_probability": detector.ai_probability,
                    "label": detector.label,
                    "reliability_weight": detector.weight,
                }
                for detector in model_signals
            ],
        },
        limitations=[
            "Pretrained detectors can fail on new generators, screenshots, crops, or heavy compression.",
            "This layer is stronger when multiple models agree and weaker when they disagree.",
        ],
    )


def _array_entropy(values: np.ndarray) -> float:
    histogram, _ = np.histogram(values.astype(np.uint8), bins=256, range=(0, 255), density=False)
    probabilities = histogram.astype(np.float64)
    probabilities = probabilities / (probabilities.sum() + 1e-9)
    probabilities = probabilities[probabilities > 0]
    return float(-np.sum(probabilities * np.log2(probabilities)))


def _tile_feature_values(values: np.ndarray, reducer) -> list[float]:
    rows = []
    height, width = values.shape[:2]
    y_edges = np.linspace(0, height, 5, dtype=int)
    x_edges = np.linspace(0, width, 5, dtype=int)
    for row_index in range(4):
        for col_index in range(4):
            top, bottom = int(y_edges[row_index]), int(y_edges[row_index + 1])
            left, right = int(x_edges[col_index]), int(x_edges[col_index + 1])
            tile = values[top:bottom, left:right]
            if tile.size:
                rows.append(float(reducer(tile)))
    return rows


def _tile_stats(gray_array: np.ndarray, edges: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    height, width = gray_array.shape[:2]
    y_edges = np.linspace(0, height, 5, dtype=int)
    x_edges = np.linspace(0, width, 5, dtype=int)
    for row_index in range(4):
        for col_index in range(4):
            top, bottom = int(y_edges[row_index]), int(y_edges[row_index + 1])
            left, right = int(x_edges[col_index]), int(x_edges[col_index + 1])
            gray_tile = gray_array[top:bottom, left:right]
            edge_tile = edges[top:bottom, left:right]
            if gray_tile.size and edge_tile.size:
                rows.append(
                    {
                        "row": row_index + 1,
                        "col": col_index + 1,
                        "brightness": round(float(np.mean(gray_tile) / 255.0), 4),
                        "noise": round(float(np.var(edge_tile)), 4),
                        "edge": round(float(np.mean(edge_tile) / 255.0), 4),
                    }
                )
    return rows


def _severity_band(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    return "low"


def _z_scores(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return values
    return np.abs((values - float(np.mean(values))) / (float(np.std(values)) + 1e-6))


def metadata_detector(metadata: dict[str, Any], c2pa: dict[str, Any]) -> DetectorSignal:
    evidence: list[str] = []
    ai_probability = 0.5
    manipulation_probability = 0.25
    label = "inconclusive"
    confidence = "low"

    if metadata["generative_markers"]:
        ai_probability = 0.9
        label = "likely_ai_generated"
        confidence = "medium"
        evidence.append(f"Generative software markers found: {', '.join(metadata['generative_markers'])}.")
    elif c2pa.get("claim") == "ai_generated_or_synthetic":
        ai_probability = 0.92
        label = "likely_ai_generated"
        confidence = "high"
        evidence.append("C2PA/content credentials appear to declare synthetic or AI-generated content.")
    elif metadata["editing_markers"]:
        manipulation_probability = 0.62
        label = "possibly_edited"
        confidence = "low"
        evidence.append(f"Editing software markers found: {', '.join(metadata['editing_markers'])}.")
    elif metadata["has_exif"]:
        ai_probability = 0.35
        label = "camera_metadata_present"
        confidence = "low"
        evidence.append("Some EXIF metadata is present; this is compatible with camera-origin media but not proof.")
    else:
        evidence.append("No strong metadata signal was found.")

    return DetectorSignal(
        name="metadata_provenance",
        status="ok",
        label=label,
        ai_probability=ai_probability,
        manipulation_probability=manipulation_probability,
        confidence=confidence,
        evidence=evidence,
        weight=0.22,
    )


def forensic_detector(forensics: dict[str, Any]) -> DetectorSignal:
    manipulation = forensics["manipulation_score"]
    artificiality = forensics["artificiality_score"]
    evidence = [
        f"ELA normalized mean: {forensics['ela']['normalized_mean']}.",
        f"Noise tile inconsistency: {forensics['noise']['tile_inconsistency']}.",
    ]
    if manipulation >= 0.68:
        label = "likely_manipulated_or_recompressed"
        confidence = "medium"
    elif artificiality >= 0.7:
        label = "synthetic_artifact_signal"
        confidence = "low"
    else:
        label = "no_strong_forensic_signal"
        confidence = "low"

    return DetectorSignal(
        name="compression_noise_forensics",
        status="ok",
        label=label,
        ai_probability=round(0.35 + artificiality * 0.45, 4),
        manipulation_probability=round(manipulation, 4),
        confidence=confidence,
        evidence=evidence,
        weight=0.28,
    )


def huggingface_detectors(image: Image.Image, settings: Settings) -> list[DetectorSignal]:
    if not settings.enable_hf_model:
        return [
            DetectorSignal(
                name="open_source_model_ensemble",
                status="unavailable",
                label="not_configured",
                ai_probability=None,
                manipulation_probability=None,
                confidence="none",
                evidence=["Set AIDA_ENABLE_HF_MODEL=true and AIDA_HF_MODEL_IDS to use pretrained open-source visual detectors."],
                weight=0.65,
            )
        ]

    model_ids = _configured_model_ids(settings)
    portrait_metrics = _portrait_likelihood_metrics(image)
    signals = [_huggingface_detector_for_model(image, model_id, portrait_metrics) for model_id in model_ids]
    ok_signals = [signal for signal in signals if signal.status == "ok" and signal.ai_probability is not None]
    if len(ok_signals) >= 2:
        signals.append(model_ensemble_signal(ok_signals))
    return signals


def optional_huggingface_detector(image: Image.Image, settings: Settings) -> DetectorSignal:
    """Backward-compatible single-signal adapter used by older tests/callers."""
    return huggingface_detectors(image, settings)[0]


def _huggingface_detector_for_model(image: Image.Image, model_id: str, portrait_metrics: dict[str, Any] | None = None) -> DetectorSignal:
    name = f"hf:{model_id}"
    profile = _model_profile(model_id)
    portrait_metrics = portrait_metrics or {"portrait_score": 0.0, "evidence": ["Portrait gate was not evaluated."]}
    if profile.get("portrait_only") and float(portrait_metrics.get("portrait_score") or 0.0) < float(profile.get("min_portrait_score") or 0.0):
        return DetectorSignal(
            name=name,
            status="unavailable",
            label="portrait_gate_not_met",
            ai_probability=None,
            manipulation_probability=None,
            confidence="none",
            evidence=[
                f"Skipped portrait-only model {model_id}; portrait likelihood was {float(portrait_metrics.get('portrait_score') or 0.0):.2f}.",
                *portrait_metrics.get("evidence", [])[:2],
            ],
            weight=0.0,
        )

    try:
        classifier = _get_huggingface_classifier(model_id)
        outputs = classifier(image.convert("RGB"), top_k=None)
        outputs = _normalize_classifier_outputs(outputs)
    except Exception as exc:
        return DetectorSignal(
            name=name,
            status="unavailable",
            label="runtime_error",
            ai_probability=None,
            manipulation_probability=None,
            confidence="none",
            evidence=[f"Open-source model {model_id} failed: {exc.__class__.__name__}."],
            weight=0.0,
        )

    ai_score = _map_classifier_outputs_to_ai_probability(outputs)
    if ai_score >= profile["ai_threshold"]:
        label = "model_likely_ai_generated"
    elif ai_score <= profile["real_threshold"]:
        label = "model_likely_human_or_real"
    else:
        label = "model_inconclusive"

    return DetectorSignal(
        name=name,
        status="ok",
        label=label,
        ai_probability=round(ai_score, 4),
        manipulation_probability=None,
        confidence="medium",
        evidence=[
            f"Model {model_id} returned labels: {_summarize_labels(outputs)}.",
            (
                f"Calibration: AI threshold {profile['ai_threshold']:.2f}, real threshold "
                f"{profile['real_threshold']:.2f}, reliability weight {profile['weight']:.2f}."
            ),
            *(
                [f"Portrait gate active: likelihood {float(portrait_metrics.get('portrait_score') or 0.0):.2f}."]
                if profile.get("portrait_only")
                else []
            ),
        ],
        weight=float(profile["weight"]),
    )


def model_ensemble_signal(signals: list[DetectorSignal]) -> DetectorSignal:
    valid_signals = [signal for signal in signals if signal.ai_probability is not None]
    values = [float(signal.ai_probability) for signal in valid_signals]
    if not values:
        return DetectorSignal(
            name="open_source_model_ensemble",
            status="unavailable",
            label="no_model_scores",
            ai_probability=None,
            manipulation_probability=None,
            confidence="none",
            evidence=["No model scores were available for ensemble aggregation."],
            weight=0.0,
        )

    weights = [float(signal.weight or DEFAULT_MODEL_PROFILE["weight"]) for signal in valid_signals]
    average = _weighted_average(values, weights)
    raw_average = float(np.mean(values))
    disagreement = float(max(values) - min(values)) if len(values) >= 2 else 0.0
    ai_votes = sum(signal.label == "model_likely_ai_generated" for signal in valid_signals)
    lean_ai_votes = sum(value >= 0.6 for value in values)
    real_votes = sum(signal.label == "model_likely_human_or_real" for signal in valid_signals)
    if len(values) >= 2 and disagreement > 0.45:
        label = "ensemble_inconclusive"
    elif ai_votes == len(values) and average >= 0.72:
        label = "ensemble_likely_ai_generated"
    elif len(values) >= 3 and lean_ai_votes >= max(2, len(values) - 1) and real_votes == 0 and average >= 0.74:
        label = "ensemble_likely_ai_generated"
    elif ai_votes > real_votes and real_votes == 0 and average >= 0.76:
        label = "ensemble_likely_ai_generated"
    elif real_votes == len(values) and average <= 0.28:
        label = "ensemble_likely_real"
    elif real_votes > ai_votes and ai_votes == 0 and average <= 0.35:
        label = "ensemble_likely_real"
    else:
        label = "ensemble_inconclusive"

    if disagreement <= 0.2 and len(values) >= 2:
        confidence = "high"
    elif disagreement <= 0.4 and real_votes == 0:
        confidence = "medium"
    else:
        confidence = "low"

    evidence = [
        f"{ai_votes}/{len(values)} visual models voted AI-generated.",
        f"{lean_ai_votes}/{len(values)} visual models leaned AI-generated at or above 60%.",
        f"{real_votes}/{len(values)} visual models voted real/human.",
        f"Visual-model disagreement range: {disagreement:.3f}.",
        f"Reliability-weighted visual average: {average:.3f}; raw model average: {raw_average:.3f}.",
    ]
    return DetectorSignal(
        name="open_source_model_ensemble",
        status="ok",
        label=label,
        ai_probability=round(average, 4),
        manipulation_probability=None,
        confidence=confidence,
        evidence=evidence,
        weight=0.9,
    )


@lru_cache(maxsize=6)
def _get_huggingface_classifier(model_id: str):
    from transformers import pipeline  # type: ignore

    return pipeline("image-classification", model=model_id, device=-1)


def _configured_model_ids(settings: Settings) -> list[str]:
    configured = settings.hf_model_ids or settings.hf_model_id
    model_ids = [item.strip() for item in configured.split(",") if item.strip()]
    return model_ids or [settings.hf_model_id]


def _model_profile(model_id: str) -> dict[str, float | str]:
    return MODEL_PROFILES.get(model_id, DEFAULT_MODEL_PROFILE)


def _is_portrait_specialist(signal: DetectorSignal) -> bool:
    if not signal.name.startswith("hf:"):
        return False
    model_id = signal.name.removeprefix("hf:")
    return _model_profile(model_id).get("expert_group") == "portrait_specialist"


def _weighted_average(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.5
    total_weight = sum(max(0.0, weight) for weight in weights)
    if total_weight <= 0:
        return float(np.mean(values))
    return float(sum(value * max(0.0, weight) for value, weight in zip(values, weights, strict=False)) / total_weight)


def aggregate_verdict(
    detectors: list[DetectorSignal],
    metadata: dict[str, Any],
    c2pa: dict[str, Any],
    forensics: dict[str, Any],
) -> dict[str, Any]:
    if metadata["generative_markers"]:
        return {
            "label": "likely_ai_generated",
            "confidence": "medium",
            "ai_probability": 0.9,
            "manipulation_probability": max(0.35, forensics["manipulation_score"]),
            "disagreement": 0.0,
            "rationale": [f"Generative software markers found: {', '.join(metadata['generative_markers'])}."],
        }

    if c2pa.get("claim") == "ai_generated_or_synthetic":
        return {
            "label": "likely_ai_generated",
            "confidence": "high",
            "ai_probability": 0.94,
            "manipulation_probability": max(0.45, forensics["manipulation_score"]),
            "disagreement": 0.0,
            "rationale": ["Readable content credentials appear to declare synthetic or AI-generated content."],
        }

    model_signal = next(
        (detector for detector in detectors if detector.name == "open_source_model_ensemble" and detector.status == "ok"),
        None,
    )
    model_detectors = [
        detector for detector in detectors if detector.name.startswith("hf:") and detector.status == "ok" and detector.ai_probability is not None
    ]
    model_values = [float(detector.ai_probability) for detector in model_detectors]
    model_disagreement = (max(model_values) - min(model_values)) if len(model_values) >= 2 else 0.0
    model_ai_votes = sum(detector.label == "model_likely_ai_generated" for detector in model_detectors)
    model_lean_ai_votes = sum(value >= 0.6 for value in model_values)
    model_real_votes = sum(detector.label == "model_likely_human_or_real" for detector in model_detectors)
    quality_risk = float((forensics.get("quality") or {}).get("risk_score") or 0.0)

    if model_signal and model_signal.ai_probability is not None:
        available = [
            detector
            for detector in detectors
            if detector.status == "ok" and detector.ai_probability is not None and not detector.name.startswith("hf:")
        ]
    else:
        available = [detector for detector in detectors if detector.status == "ok" and detector.ai_probability is not None]
    total_weight = sum(detector.weight for detector in available) or 1.0
    ai_probability = sum((detector.ai_probability or 0.5) * detector.weight for detector in available) / total_weight
    manipulation_values = [detector.manipulation_probability for detector in detectors if detector.manipulation_probability is not None]
    manipulation_probability = max(manipulation_values) if manipulation_values else forensics["manipulation_score"]
    ai_values = [detector.ai_probability for detector in detectors if detector.status == "ok" and detector.ai_probability is not None]
    disagreement = max((max(ai_values) - min(ai_values)) if len(ai_values) >= 2 else 0.0, model_disagreement)

    strong_signals = [
        detector
        for detector in available
        if detector.confidence in {"medium", "high"} and detector.label not in {"no_strong_forensic_signal", "camera_metadata_present"}
    ]
    has_model = any(detector.name.startswith("hf:") and detector.status == "ok" for detector in detectors)
    rationale = _collect_rationale(detectors)
    non_model_ai_support = any(
        detector.name in {"metadata_provenance", "compression_noise_forensics"}
        and detector.confidence in {"medium", "high"}
        and detector.ai_probability is not None
        and detector.ai_probability >= 0.72
        for detector in detectors
    )
    larger_model_consensus = (
        len(model_values) >= 3
        and model_lean_ai_votes >= max(2, len(model_values) - 1)
        and model_real_votes == 0
        and model_disagreement < 0.42
    )
    model_only_ai_claim = (
        model_signal is not None
        and model_signal.label == "ensemble_likely_ai_generated"
        and not non_model_ai_support
        and not larger_model_consensus
    )
    portrait_real_support = any(
        _is_portrait_specialist(detector)
        and detector.label == "model_likely_human_or_real"
        and detector.ai_probability is not None
        and detector.ai_probability <= 0.12
        for detector in model_detectors
    )
    portrait_real_override = (
        portrait_real_support
        and model_real_votes >= model_ai_votes
        and model_disagreement >= 0.5
        and not non_model_ai_support
        and quality_risk < 0.55
        and forensics["artificiality_score"] < 0.45
        and forensics["manipulation_score"] < 0.65
    )
    weak_non_model_artifacts = (
        not metadata["generative_markers"]
        and c2pa.get("claim") != "ai_generated_or_synthetic"
        and forensics["artificiality_score"] < 0.45
        and forensics["manipulation_score"] < 0.65
    )
    model_uncorroborated = has_model and weak_non_model_artifacts and not larger_model_consensus and (
        model_disagreement >= 0.45
        or (model_signal is not None and model_signal.confidence == "low")
        or (len(model_values) >= 2 and model_ai_votes < 2)
        or model_only_ai_claim
    )
    if model_uncorroborated and ai_probability > 0.64:
        ai_probability = 0.64
        rationale.append(
            "Final AI probability was capped because visual-model suspicion was not corroborated by independent metadata, provenance, or forensic evidence."
        )
    if quality_risk >= 0.55 and not non_model_ai_support and ai_probability > 0.68:
        ai_probability = 0.68
        rationale.append(
            "Final AI probability was capped because input-quality risk is high; low-resolution, cropped, or heavily exported media weakens detector reliability."
        )
    if portrait_real_override and ai_probability > 0.38:
        ai_probability = 0.38
        rationale.append(
            "Calibrated portrait-specialist evidence and at least one generic real/human vote reduced the final AI probability."
        )

    model_supports_ai = (
        model_signal is not None
        and model_signal.label == "ensemble_likely_ai_generated"
        and model_signal.confidence in {"medium", "high"}
        and (non_model_ai_support or larger_model_consensus)
    )
    if model_supports_ai and not model_uncorroborated and model_signal.ai_probability is not None:
        ai_probability = max(ai_probability, min(float(model_signal.ai_probability), 0.88))

    if model_supports_ai and ai_probability >= 0.72:
        label = "likely_ai_generated"
    elif ai_probability >= 0.78 and (strong_signals or non_model_ai_support) and not model_uncorroborated:
        label = "likely_ai_generated"
    elif manipulation_probability >= 0.68:
        label = "likely_manipulated_or_deepfake"
    elif (
        ai_probability <= 0.28
        and manipulation_probability < 0.35
        and (has_model or metadata["has_exif"] or c2pa.get("status") == "found")
    ):
        label = "likely_real"
    elif portrait_real_override and ai_probability <= 0.45:
        label = "likely_real"
    else:
        label = "inconclusive"

    if label == "inconclusive":
        confidence = "low"
    elif model_supports_ai:
        confidence = "medium"
    elif has_model and disagreement < 0.28:
        confidence = "medium"
    elif strong_signals and disagreement < 0.35:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "label": label,
        "confidence": confidence,
        "ai_probability": round(float(ai_probability), 4),
        "manipulation_probability": round(float(manipulation_probability), 4),
        "disagreement": round(float(disagreement), 4),
        "rationale": rationale,
    }


def build_layers(
    metadata: dict[str, Any],
    hashes: dict[str, Any],
    c2pa: dict[str, Any],
    forensics: dict[str, Any],
    detectors: list[DetectorSignal],
    source_context: dict | None,
) -> list[dict[str, Any]]:
    return [
        {
            "name": "Input and Source",
            "status": "complete",
            "findings": [
                f"Image dimensions: {metadata['width']} x {metadata['height']}.",
                f"Input source: {(source_context or {}).get('domain') or 'direct upload'}.",
            ],
        },
        {
            "name": "Metadata",
            "status": "complete",
            "findings": [
                "EXIF metadata present." if metadata["has_exif"] else "No EXIF metadata found.",
                "GPS metadata was present and redacted." if metadata["gps_present"] else "No GPS metadata was exposed.",
                f"Software markers: {', '.join(metadata['software_values'])}." if metadata["software_values"] else "No software marker found.",
            ],
        },
        {
            "name": "Provenance",
            "status": c2pa["status"],
            "findings": c2pa["evidence"],
        },
        {
            "name": "Hashes",
            "status": "complete",
            "findings": [
                f"SHA-256: {hashes['sha256']}.",
                f"Perceptual hash: {hashes['average_hash']}.",
            ],
        },
        {
            "name": "Compression and Noise",
            "status": "complete",
            "findings": [
                f"Manipulation heuristic score: {forensics['manipulation_score']}.",
                f"Artificiality heuristic score: {forensics['artificiality_score']}.",
            ],
        },
        {
            "name": "Detector Ensemble",
            "status": "complete",
            "findings": [
                f"{detector.name}: {detector.label} ({detector.status})." for detector in detectors
            ],
        },
    ]


def build_explainability(
    verdict: dict[str, Any],
    detectors: list[DetectorSignal],
    metadata: dict[str, Any],
    c2pa: dict[str, Any],
    forensics: dict[str, Any],
    analytical_layers: list[dict[str, Any]],
) -> dict[str, Any]:
    model_signals = [
        detector
        for detector in detectors
        if detector.name.startswith("hf:") and detector.status == "ok" and detector.ai_probability is not None
    ]
    ensemble = next((detector for detector in detectors if detector.name == "open_source_model_ensemble"), None)
    model_scores = [
        {
            "name": signal.name,
            "ai_probability": signal.ai_probability,
            "label": signal.label,
            "reliability_weight": signal.weight,
            "evidence": signal.evidence,
        }
        for signal in model_signals
    ]
    strongest = sorted(
        [
            {
                "source": detector.name,
                "label": detector.label,
                "ai_probability": detector.ai_probability,
                "manipulation_probability": detector.manipulation_probability,
                "evidence": detector.evidence,
            }
            for detector in detectors
            if detector.status == "ok"
        ],
        key=lambda item: max(
            abs((item["ai_probability"] or 0.5) - 0.5),
            abs((item["manipulation_probability"] or 0.25) - 0.25),
        ),
        reverse=True,
    )
    model_values = [float(signal.ai_probability) for signal in model_signals if signal.ai_probability is not None]
    weighted_model_average = (
        float(ensemble.ai_probability)
        if ensemble and ensemble.ai_probability is not None
        else _weighted_average(model_values, [float(signal.weight or DEFAULT_MODEL_PROFILE["weight"]) for signal in model_signals])
        if model_values
        else None
    )
    layer_votes = {
        "supports_ai_generated": sum(layer["conclusion"] == "supports_ai_generated" for layer in analytical_layers),
        "supports_real_or_camera_origin": sum(layer["conclusion"] == "supports_real_or_camera_origin" for layer in analytical_layers),
        "supports_manipulation_or_editing": sum(layer["conclusion"] == "supports_manipulation_or_editing" for layer in analytical_layers),
        "weak_anomaly": sum(layer["conclusion"] == "weak_anomaly" for layer in analytical_layers),
        "neutral_or_inconclusive": sum(layer["conclusion"] == "neutral_or_inconclusive" for layer in analytical_layers),
    }
    decision_support = _decision_support(verdict, analytical_layers, layer_votes, c2pa, model_scores)
    expert_opinions = _mixture_expert_opinions(verdict, detectors, metadata, c2pa, forensics)
    regional_map = _regional_evidence_map(analytical_layers)
    return {
        "decision_trace": [
            f"Final label is {verdict['label']} with {verdict['confidence']} confidence.",
            f"Combined AI probability is {verdict['ai_probability']:.0%}.",
            f"Combined manipulation probability is {verdict['manipulation_probability']:.0%}.",
            (
                "Layer ledger: "
                f"{layer_votes['supports_ai_generated']} support AI, "
                f"{layer_votes['supports_real_or_camera_origin']} support real/camera-origin, "
                f"{layer_votes['supports_manipulation_or_editing']} support manipulation, "
                f"{layer_votes['weak_anomaly']} weak anomalies, "
                f"{layer_votes['neutral_or_inconclusive']} neutral/inconclusive."
            ),
        ],
        "decision_support": decision_support,
        "expert_opinions": expert_opinions,
        "model_consensus": {
            "enabled_models": len(model_signals),
            "ai_votes": sum(signal.label == "model_likely_ai_generated" for signal in model_signals),
            "real_votes": sum(signal.label == "model_likely_human_or_real" for signal in model_signals),
            "inconclusive_votes": sum(signal.label == "model_inconclusive" for signal in model_signals),
            "average_ai_probability": round(weighted_model_average, 4) if weighted_model_average is not None else None,
            "raw_average_ai_probability": round(float(np.mean(model_values)), 4) if model_values else None,
            "disagreement_range": round(float(max(model_values) - min(model_values)), 4) if len(model_values) >= 2 else 0.0,
            "ensemble_label": ensemble.label if ensemble else None,
            "ensemble_confidence": ensemble.confidence if ensemble else None,
            "models": model_scores,
        },
        "decision_standard": {
            "policy": "victim_safe_calibrated_triage",
            "likely_ai_requires": [
                "Readable generative metadata or C2PA declaration,",
                "or independent non-model forensic/provenance support,",
                "or calibrated multi-model consensus with no model voting real/human-origin.",
            ],
            "false_positive_controls": [
                "Raw model scores are reliability-weighted before aggregation.",
                "Detector disagreement and real/human votes force abstention.",
                "Portrait-specialist models only run after a portrait-likelihood gate.",
                "Low-quality crops, screenshots, and compressed exports cap confidence.",
            ],
            "input_quality": forensics.get("quality", {}),
        },
        "non_model_evidence": {
            "metadata": "Generative markers found." if metadata["generative_markers"] else "No generative metadata marker found.",
            "c2pa": c2pa["status"],
            "forensic_artificiality_score": forensics["artificiality_score"],
            "forensic_manipulation_score": forensics["manipulation_score"],
        },
        "strongest_evidence": strongest[:5],
        "regional_evidence_map": regional_map,
        "layer_ledger": {
            "counts": layer_votes,
            "layers": analytical_layers,
        },
        "calibration_note": (
            "Scores are calibrated for cautious triage, not certainty. "
            "Agreement across multiple visual detectors is stronger than any single model score."
        ),
    }


def _decision_support(
    verdict: dict[str, Any],
    analytical_layers: list[dict[str, Any]],
    layer_votes: dict[str, int],
    c2pa: dict[str, Any],
    model_scores: list[dict[str, Any]],
) -> dict[str, Any]:
    label = verdict["label"]
    if label == "likely_ai_generated":
        supporting = [layer for layer in analytical_layers if layer["conclusion"] == "supports_ai_generated"]
        counter = [layer for layer in analytical_layers if layer["conclusion"] == "supports_real_or_camera_origin"]
        plain_summary = "The AI-generated verdict is mainly driven by visual detector evidence, then checked against metadata and forensic layers."
    elif label == "likely_manipulated_or_deepfake":
        supporting = [layer for layer in analytical_layers if layer["conclusion"] == "supports_manipulation_or_editing"]
        counter = [layer for layer in analytical_layers if layer["conclusion"] == "supports_real_or_camera_origin"]
        plain_summary = "The manipulation verdict is driven by editing or regional forensic signals, not by identity inference."
    elif label == "likely_real":
        supporting = [layer for layer in analytical_layers if layer["conclusion"] == "supports_real_or_camera_origin"]
        counter = [
            layer
            for layer in analytical_layers
            if layer["conclusion"] in {"supports_ai_generated", "supports_manipulation_or_editing"}
        ]
        plain_summary = "The real-origin verdict is supported by camera/provenance-style evidence and a low AI probability."
    else:
        supporting = [
            layer
            for layer in analytical_layers
            if layer["conclusion"] in {"supports_ai_generated", "supports_real_or_camera_origin", "supports_manipulation_or_editing"}
        ]
        counter = [layer for layer in analytical_layers if layer["conclusion"] == "weak_anomaly"]
        plain_summary = "The evidence does not cross a safe threshold; the report is preserving uncertainty instead of forcing a binary answer."

    supporting = sorted(supporting, key=_layer_strength, reverse=True)
    counter = sorted(counter, key=_layer_strength, reverse=True)
    weak_anomalies = [layer for layer in analytical_layers if layer["conclusion"] == "weak_anomaly"]

    uncertainty = []
    if verdict["confidence"] == "low":
        uncertainty.append("Confidence is low, so this should be treated as triage evidence rather than a final forensic certificate.")
    if verdict["disagreement"] >= 0.35:
        uncertainty.append(f"Detector disagreement is elevated at {verdict['disagreement']:.0%}.")
    if c2pa.get("status") != "found":
        uncertainty.append("No signed C2PA/content credential was available to independently confirm provenance.")
    if len(model_scores) < 2:
        uncertainty.append("Fewer than two visual model scores were available.")
    if weak_anomalies:
        uncertainty.append(f"{len(weak_anomalies)} layer(s) produced weak anomaly signals that need context.")
    if layer_votes["neutral_or_inconclusive"] >= 4:
        uncertainty.append(f"{layer_votes['neutral_or_inconclusive']} layer(s) were neutral or inconclusive.")

    return {
        "plain_summary": plain_summary,
        "primary_drivers": _layer_summaries(supporting[:4])
        or ["No single layer was strong enough on its own; the final label comes from combined probabilities."],
        "counter_evidence": _layer_summaries(counter[:4]) or ["No strong counter-evidence was found in the analytical layers."],
        "uncertainty_factors": uncertainty[:5] or ["No major uncertainty factor was detected, but image authenticity still cannot be proven from pixels alone."],
        "what_would_help": [
            "Original, uncompressed media from the device or platform export.",
            "Public source URL, timestamps, captions, and account/page context.",
            "Signed C2PA/content credentials where available.",
            "Manual review when the result affects safety, reputation, or legal action.",
        ],
    }


def _mixture_expert_opinions(
    verdict: dict[str, Any],
    detectors: list[DetectorSignal],
    metadata: dict[str, Any],
    c2pa: dict[str, Any],
    forensics: dict[str, Any],
) -> list[dict[str, Any]]:
    opinions: list[dict[str, Any]] = []
    ensemble = next((detector for detector in detectors if detector.name == "open_source_model_ensemble"), None)
    if ensemble:
        opinions.append(
            {
                "expert": "Visual Detector Ensemble",
                "opinion": ensemble.label,
                "stance": _stance_from_label(ensemble.label),
                "confidence": ensemble.confidence,
                "score": ensemble.ai_probability,
                "evidence": ensemble.evidence[:3],
            }
        )

    portrait_signal = next((detector for detector in detectors if _is_portrait_specialist(detector)), None)
    if portrait_signal:
        opinions.append(
            {
                "expert": "Portrait Specialist",
                "opinion": portrait_signal.label,
                "stance": _stance_from_label(portrait_signal.label),
                "confidence": portrait_signal.confidence,
                "score": portrait_signal.ai_probability,
                "evidence": portrait_signal.evidence[:3],
            }
        )

    metadata_stance = "supports_ai" if metadata["generative_markers"] or c2pa.get("claim") == "ai_generated_or_synthetic" else "neutral"
    opinions.append(
        {
            "expert": "Metadata And Provenance",
            "opinion": "generative_marker_found" if metadata_stance == "supports_ai" else "no_generative_marker",
            "stance": metadata_stance,
            "confidence": "high" if c2pa.get("claim") else "low",
            "score": 0.9 if metadata_stance == "supports_ai" else 0.5,
            "evidence": [
                f"Generative markers: {', '.join(metadata['generative_markers']) or 'none'}.",
                f"C2PA status: {c2pa.get('status')}.",
            ],
        }
    )

    forensic_stance = "supports_manipulation" if forensics["manipulation_score"] >= 0.68 else "neutral"
    if forensics["artificiality_score"] >= 0.7:
        forensic_stance = "supports_ai"
    opinions.append(
        {
            "expert": "Forensic Residuals",
            "opinion": forensic_stance,
            "stance": forensic_stance,
            "confidence": "medium" if forensic_stance != "neutral" else "low",
            "score": max(forensics["artificiality_score"], forensics["manipulation_score"]),
            "evidence": [
                f"Artificiality score: {forensics['artificiality_score']}.",
                f"Manipulation score: {forensics['manipulation_score']}.",
            ],
        }
    )

    quality = forensics.get("quality") or {}
    opinions.append(
        {
            "expert": "Input Quality Guard",
            "opinion": f"{quality.get('risk_band', 'unknown')}_quality_risk",
            "stance": "limits_confidence" if float(quality.get("risk_score") or 0.0) >= 0.25 else "neutral",
            "confidence": "medium",
            "score": quality.get("risk_score"),
            "evidence": (quality.get("evidence") or [])[:3],
        }
    )

    opinions.append(
        {
            "expert": "Safety Arbiter",
            "opinion": verdict["label"],
            "stance": _stance_from_label(verdict["label"]),
            "confidence": verdict["confidence"],
            "score": verdict["ai_probability"],
            "evidence": verdict["rationale"][-3:],
        }
    )
    return opinions


def _stance_from_label(label: str) -> str:
    normalized = label.lower().replace("-", "_")
    tokens = set(normalized.split("_"))
    if normalized in {"portrait_gate_not_met", "ensemble_inconclusive", "model_inconclusive", "inconclusive"}:
        return "neutral"
    if (
        "likely_ai_generated" in normalized
        or "ai_generated" in normalized
        or "synthetic" in tokens
        or "fake" in tokens
        or "deepfake" in tokens
    ):
        return "supports_ai"
    if "real" in tokens or "human" in tokens or "camera" in tokens:
        return "supports_real"
    if "manipulated" in tokens or "editing" in tokens:
        return "supports_manipulation"
    return "neutral"


def _layer_strength(layer: dict[str, Any]) -> float:
    return max(abs(float(layer.get("ai_signal") or 0.5) - 0.5), abs(float(layer.get("manipulation_signal") or 0.25) - 0.25))


def _layer_summaries(layers: list[dict[str, Any]]) -> list[str]:
    return [
        (
            f"{layer['name']}: {layer['conclusion']} "
            f"(AI {float(layer['ai_signal']):.0%}, manipulation {float(layer['manipulation_signal']):.0%})."
        )
        for layer in layers
    ]


def _regional_evidence_map(analytical_layers: list[dict[str, Any]]) -> dict[str, Any] | None:
    tile_layer = next((layer for layer in analytical_layers if layer.get("id") == "tile_regions"), None)
    if not tile_layer:
        return None
    metrics = tile_layer.get("metrics") or {}
    tile_grid = metrics.get("tile_grid") or []
    if not tile_grid:
        return None
    return {
        "grid": {"rows": 4, "cols": 4},
        "tiles": tile_grid,
        "max_score": metrics.get("max_tile_anomaly_score"),
        "mean_score": metrics.get("mean_tile_anomaly_score"),
        "high_severity_tile_count": metrics.get("high_severity_tile_count", 0),
        "interpretation": (
            "This abstract map compares regions against the rest of the same image. "
            "It does not display the uploaded image and does not identify what caused a regional difference."
        ),
    }


def _safe_metadata_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value[:128].hex()
    if isinstance(value, tuple):
        return ", ".join(_safe_metadata_value(item) for item in value[:12])
    return str(value)[:500]


def _metadata_marker_text(exif: dict[str, str], png_text: dict[str, str], xmp: str | None) -> str:
    values = [str(value) for value in exif.values()]
    values.extend(str(value) for value in png_text.values())
    if xmp:
        values.append(xmp)
    return " ".join(values).lower()


def _compact_metadata_summary(value: str, *, limit: int = 120) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}..."


def _xmp_report_summary(xmp: str | None, generative_markers: list[str], editing_markers: list[str]) -> str | None:
    if not xmp:
        return None
    markers = sorted(set(generative_markers + editing_markers))
    marker_text = f"; markers: {', '.join(markers)}" if markers else ""
    return f"XMP metadata present ({len(xmp)} characters{marker_text}); raw XMP omitted from stored report."


def _collect_software_values(
    exif: dict[str, str],
    png_text: dict[str, str],
    xmp: str | None,
    generative_markers: list[str],
    editing_markers: list[str],
) -> list[str]:
    values: list[str] = []
    for key in ("Software", "ProcessingSoftware", "Make", "Model"):
        if exif.get(key):
            values.append(_compact_metadata_summary(str(exif[key])))
    for key, value in png_text.items():
        if key.lower() in {"software", "parameters", "prompt", "workflow", "generation_data"}:
            values.append(f"{key}: {_compact_metadata_summary(str(value))}")
    if xmp:
        markers = sorted(set(generative_markers + editing_markers))
        if markers:
            values.append(f"XMP metadata mentions: {', '.join(markers)}")
        else:
            values.append("XMP metadata present")
    return values


def _average_hash(image: Image.Image) -> str:
    small = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def _difference_hash(image: Image.Image) -> str:
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = []
    for row in range(8):
        offset = row * 9
        for col in range(8):
            bits.append("1" if pixels[offset + col] > pixels[offset + col + 1] else "0")
    return f"{int(''.join(bits), 2):016x}"


def _ela_metrics(image: Image.Image) -> dict[str, Any]:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert("RGB")
    diff = ImageChops.difference(image, recompressed)
    stat = ImageStat.Stat(diff)
    mean = float(sum(stat.mean) / len(stat.mean))
    extrema = diff.getextrema()
    max_delta = max(channel[1] for channel in extrema)
    return {
        "mean_delta": round(mean, 4),
        "max_delta": int(max_delta),
        "normalized_mean": round(_clamp((mean - 2.5) / 18.0), 4),
    }


def _noise_metrics(image: Image.Image) -> dict[str, Any]:
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    tile_scores = []
    tile_w = max(8, gray.width // 4)
    tile_h = max(8, gray.height // 4)
    for top in range(0, gray.height, tile_h):
        for left in range(0, gray.width, tile_w):
            tile = edges.crop((left, top, min(left + tile_w, gray.width), min(top + tile_h, gray.height)))
            arr = np.asarray(tile, dtype=np.float32)
            tile_scores.append(float(arr.var()))
    mean = float(np.mean(tile_scores)) if tile_scores else 0.0
    std = float(np.std(tile_scores)) if tile_scores else 0.0
    coefficient = std / (mean + 1e-6)
    low_noise_hint = _clamp((90.0 - mean) / 90.0)
    return {
        "tile_variance_mean": round(mean, 4),
        "tile_variance_std": round(std, 4),
        "tile_inconsistency": round(_clamp(coefficient / 1.8), 4),
        "low_noise_hint": round(low_noise_hint, 4),
    }


def _jpeg_marker_summary(image_bytes: bytes) -> dict[str, Any]:
    # Multiple quantization tables can be normal; this only contributes a weak hint.
    dqt_count = image_bytes.count(b"\xff\xdb")
    return {
        "dqt_marker_count": dqt_count,
        "double_quantization_hint": 0.3 if dqt_count >= 3 else 0.0,
    }


def _input_quality_metrics(image: Image.Image, image_bytes: bytes, entropy: float) -> dict[str, Any]:
    width, height = image.size
    pixels = width * height
    shortest_edge = min(width, height)
    aspect_ratio = max(width, height) / max(1, shortest_edge)
    bytes_per_pixel = len(image_bytes) / max(1, pixels)
    flags: list[str] = []
    risk = 0.0

    if pixels < 120_000 or shortest_edge < 256:
        flags.append("low_resolution_or_crop")
        risk += 0.35
    elif pixels < 300_000:
        flags.append("moderate_resolution")
        risk += 0.18
    if aspect_ratio >= 2.75:
        flags.append("extreme_aspect_ratio")
        risk += 0.15
    if bytes_per_pixel < 0.08 and pixels > 250_000:
        flags.append("heavy_compression_or_platform_export")
        risk += 0.18
    if entropy <= 4.2:
        flags.append("very_low_texture_entropy")
        risk += 0.12
    if image.format in {"PNG", "WEBP"} and pixels < 500_000:
        flags.append("possible_screenshot_or_export")
        risk += 0.10

    risk_score = round(_clamp(risk), 4)
    if flags:
        evidence = [
            f"Robustness risk flags: {', '.join(flags)}.",
            f"Resolution: {width} x {height}; shortest edge {shortest_edge}px.",
            f"Bytes per pixel: {bytes_per_pixel:.3f}; entropy: {entropy:.3f}.",
        ]
    else:
        evidence = [
            "No major input-quality risk flags were detected.",
            f"Resolution: {width} x {height}; shortest edge {shortest_edge}px.",
            f"Bytes per pixel: {bytes_per_pixel:.3f}; entropy: {entropy:.3f}.",
        ]

    return {
        "risk_score": risk_score,
        "risk_band": "high" if risk_score >= 0.55 else "medium" if risk_score >= 0.25 else "low",
        "flags": flags,
        "width": width,
        "height": height,
        "pixels": pixels,
        "shortest_edge": shortest_edge,
        "aspect_ratio": round(aspect_ratio, 4),
        "bytes_per_pixel": round(bytes_per_pixel, 4),
        "entropy": entropy,
        "evidence": evidence,
    }


def _portrait_likelihood_metrics(image: Image.Image) -> dict[str, Any]:
    rgb = image.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR)
    arr = np.asarray(rgb, dtype=np.float32)
    ycbcr = np.asarray(rgb.convert("YCbCr"), dtype=np.float32)
    cb = ycbcr[:, :, 1]
    cr = ycbcr[:, :, 2]
    skin_mask = (cb >= 77) & (cb <= 135) & (cr >= 130) & (cr <= 180)
    height, width = skin_mask.shape
    center = skin_mask[int(height * 0.12) : int(height * 0.82), int(width * 0.25) : int(width * 0.75)]
    side_left = skin_mask[:, : int(width * 0.18)]
    side_right = skin_mask[:, int(width * 0.82) :]
    center_skin_ratio = float(np.mean(center)) if center.size else 0.0
    side_skin_ratio = float((np.mean(side_left) + np.mean(side_right)) / 2.0) if side_left.size and side_right.size else 0.0
    centrality = _clamp((center_skin_ratio - side_skin_ratio + 0.12) / 0.42)
    aspect_ratio = image.width / max(1, image.height)
    aspect_hint = _clamp(1.0 - abs(aspect_ratio - 0.78) / 0.55)
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)
    center_luma = float(np.mean(gray[int(height * 0.18) : int(height * 0.80), int(width * 0.28) : int(width * 0.72)]))
    edge_luma = float(
        np.mean(
            np.concatenate(
                [
                    gray[:, : int(width * 0.12)].reshape(-1),
                    gray[:, int(width * 0.88) :].reshape(-1),
                ]
            )
        )
    )
    subject_contrast = _clamp((center_luma - edge_luma + 35.0) / 90.0)
    portrait_score = _clamp(0.45 * center_skin_ratio + 0.25 * centrality + 0.18 * aspect_hint + 0.12 * subject_contrast)
    evidence = [
        f"Portrait likelihood score: {portrait_score:.3f}.",
        f"Central skin-tone ratio: {center_skin_ratio:.3f}; side skin-tone ratio: {side_skin_ratio:.3f}.",
        f"Aspect hint: {aspect_hint:.3f}; subject contrast hint: {subject_contrast:.3f}.",
    ]
    return {
        "portrait_score": round(portrait_score, 4),
        "center_skin_ratio": round(center_skin_ratio, 4),
        "side_skin_ratio": round(side_skin_ratio, 4),
        "centrality": round(centrality, 4),
        "aspect_hint": round(aspect_hint, 4),
        "subject_contrast": round(subject_contrast, 4),
        "evidence": evidence,
    }


def _map_classifier_outputs_to_ai_probability(outputs: list[dict[str, Any]]) -> float:
    ai_score_total = 0.0
    real_score_total = 0.0
    for item in outputs:
        label = str(item.get("label", "")).lower()
        score = float(item.get("score", 0.0))
        if any(token in label for token in ("ai", "fake", "generated", "synthetic", "deepfake", "artificial")):
            ai_score_total += score
        if any(token in label for token in ("real", "human", "hum", "natural", "authentic")):
            real_score_total += score
    if ai_score_total or real_score_total:
        return _clamp(ai_score_total / (ai_score_total + real_score_total + 1e-9))
    return 0.5


def _normalize_classifier_outputs(outputs: Any) -> list[dict[str, Any]]:
    if isinstance(outputs, list) and outputs and isinstance(outputs[0], list):
        outputs = outputs[0]
    if not isinstance(outputs, list):
        return []
    return [item for item in outputs if isinstance(item, dict)]


def _summarize_labels(outputs: list[dict[str, Any]]) -> str:
    return ", ".join(f"{item.get('label')}={float(item.get('score', 0.0)):.3f}" for item in outputs[:5])


def _collect_rationale(detectors: list[DetectorSignal]) -> list[str]:
    rationale: list[str] = []
    for detector in detectors:
        rationale.extend(detector.evidence[:2])
    return rationale[:8]


def _headline(label: str) -> str:
    return {
        "likely_real": "The image currently looks more consistent with real camera-origin media.",
        "likely_ai_generated": "The image has signals consistent with AI-generated or synthetic media.",
        "likely_manipulated_or_deepfake": "The image has signals consistent with manipulation or deepfake-style editing.",
        "inconclusive": "The analysis is inconclusive.",
    }.get(label, "The analysis is inconclusive.")


def _plain_language(verdict: dict[str, Any]) -> str:
    return (
        f"Verdict: {verdict['label']} with {verdict['confidence']} confidence. "
        f"Estimated AI probability is {verdict['ai_probability']:.0%}; manipulation probability is "
        f"{verdict['manipulation_probability']:.0%}. Review the evidence layers before taking action."
    )


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    if math.isnan(value):
        return 0.0
    return max(lower, min(upper, float(value)))
