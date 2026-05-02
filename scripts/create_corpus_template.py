"""Create a reviewed policy corpus template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TEMPLATE_CASES = [
    {
        "id": "clean-template-001",
        "text": "합성 샘플 안내문입니다.",
        "should_block": False,
        "expected_kinds": [],
        "source_class": "synthetic",
        "reviewer": "security-reviewer",
    },
    {
        "id": "blocked-template-001",
        "text": "합성 민감정보 후보가 포함된 샘플입니다.",
        "should_block": True,
        "expected_kinds": ["internal_document_marker"],
        "source_class": "synthetic",
        "reviewer": "security-reviewer",
    },
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in TEMPLATE_CASES) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
