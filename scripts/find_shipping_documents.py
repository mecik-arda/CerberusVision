from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_project_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


_load_project_env(PROJECT_ROOT / ".env")

from app.config import settings
from app.search.document_discovery import (
    DEFAULT_SEARCH_QUERIES,
    DiscoveryEngine,
    build_manual_google_urls,
    resolve_search_provider,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find English Shipping Instruction and Bill of Lading PDF/PNG/JPG "
            "samples, run local screening, and use DeepSeek only to remove "
            "topically irrelevant or non-English documents."
        )
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "brave", "google"],
        default=settings.document_search.provider,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(settings.document_search.output_dir),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=settings.document_search.max_results,
    )
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--print-queries", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--min-local-score",
        type=float,
        default=settings.document_search.min_local_score,
    )
    parser.add_argument(
        "--max-file-mb",
        type=int,
        default=settings.document_search.max_file_mb,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    queries = tuple(args.queries or DEFAULT_SEARCH_QUERIES)
    if args.print_queries:
        for query, url in zip(queries, build_manual_google_urls(queries)):
            print(query)
            print(url)
        return 0
    if not 1 <= args.max_results <= 100:
        raise ValueError("--max-results must be between 1 and 100.")
    if not 1 <= args.max_file_mb <= 100:
        raise ValueError("--max-file-mb must be between 1 and 100.")
    if not 0 <= args.min_local_score <= 100:
        raise ValueError("--min-local-score must be between 0 and 100.")
    provider = resolve_search_provider(args.provider)
    engine = DiscoveryEngine(
        provider=provider,
        output_dir=args.output_dir.resolve(),
        min_local_score=args.min_local_score,
        max_file_bytes=args.max_file_mb * 1024 * 1024,
    )
    result = engine.run(
        queries=queries,
        max_results=args.max_results,
        local_only=args.local_only,
        use_ocr=not args.no_ocr,
    )
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Provider: {result['provider']}")
        print(f"Search results inspected: {result['searched']}")
        print(f"Documents downloaded: {result['downloaded']}")
        print(f"Accepted: {result['accepted']}")
        print(f"Pending DeepSeek relevance review: {result['pending_review']}")
        print(f"Rejected: {result['rejected']}")
        print(f"Duplicates: {result['duplicates']}")
        print(f"Errors: {result['errors']}")
        print(f"Manifest: {(args.output_dir / 'manifest.jsonl').resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, httpx.HTTPError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
