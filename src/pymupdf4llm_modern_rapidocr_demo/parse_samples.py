from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf4llm

from . import rapidocr_latest_compat


def parse_pdf(pdf_path: Path, output_dir: Path, ocr_dpi: int) -> dict:
    output_path = output_dir / f"{pdf_path.stem}.md"
    markdown = pymupdf4llm.to_markdown(str(pdf_path), ocr_dpi=ocr_dpi)
    output_path.write_text(markdown or "", encoding="utf-8")
    return {
        "input": str(pdf_path),
        "output": str(output_path),
        "bytes": output_path.stat().st_size,
        "empty": not bool(markdown),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        default=[Path("samples")],
        help="PDF file(s) or directories containing PDFs. Defaults to samples/.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--ocr-dpi", type=int, default=150)
    args = parser.parse_args()

    rapidocr_latest_compat.install()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = []
    for input_path in args.inputs:
        if input_path.is_dir():
            pdfs.extend(sorted(input_path.glob("*.pdf")))
        elif input_path.suffix.lower() == ".pdf":
            pdfs.append(input_path)

    if not pdfs:
        raise SystemExit("No PDF inputs found.")

    results = [parse_pdf(pdf_path, args.output_dir, args.ocr_dpi) for pdf_path in pdfs]
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    errors = [result for result in results if result["empty"]]
    print(f"parsed={len(results)} empty={len(errors)} output_dir={args.output_dir}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
