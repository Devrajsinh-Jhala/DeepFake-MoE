from __future__ import annotations

from collections import Counter
from threading import Lock

_lock = Lock()
_counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()


def increment(name: str, **labels: str | int | None) -> None:
    clean_labels = tuple(sorted((key, str(value)) for key, value in labels.items() if value is not None))
    with _lock:
        _counters[(name, clean_labels)] += 1


def render_prometheus() -> str:
    lines = [
        "# HELP aida_events_total Application event counters.",
        "# TYPE aida_events_total counter",
    ]
    with _lock:
        items = list(_counters.items())
    for (name, labels), value in sorted(items):
        label_text = ""
        if labels:
            label_text = "{" + ",".join(f'{key}="{_escape_label(label)}"' for key, label in labels) + "}"
        lines.append(f"{name}{label_text} {value}")
    return "\n".join(lines) + "\n"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
