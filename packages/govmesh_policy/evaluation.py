"""Policy scanner evaluation helpers."""

from __future__ import annotations

import json
from pathlib import Path

from packages.govmesh_policy.scanner import scan_text


def load_corpus(path: str | Path) -> list[dict]:
    entries: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def evaluate_policy_corpus(path: str | Path) -> dict:
    entries = load_corpus(path)
    true_positive = false_positive = true_negative = false_negative = 0
    by_kind: dict[str, dict[str, int]] = {}

    for entry in entries:
        text = entry["text"]
        expected_block = bool(entry.get("should_block", False))
        expected_kinds = set(entry.get("expected_kinds", []))
        decision = scan_text(text)
        predicted_block = not decision.allow
        predicted_kinds = {finding["kind"] for finding in decision.findings}

        if expected_block and predicted_block:
            true_positive += 1
        elif not expected_block and predicted_block:
            false_positive += 1
        elif not expected_block and not predicted_block:
            true_negative += 1
        else:
            false_negative += 1

        for kind in expected_kinds | predicted_kinds:
            stats = by_kind.setdefault(kind, {"expected": 0, "predicted": 0, "matched": 0})
            if kind in expected_kinds:
                stats["expected"] += 1
            if kind in predicted_kinds:
                stats["predicted"] += 1
            if kind in expected_kinds and kind in predicted_kinds:
                stats["matched"] += 1

    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    return {
        "case_count": len(entries),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "by_kind": by_kind,
    }
