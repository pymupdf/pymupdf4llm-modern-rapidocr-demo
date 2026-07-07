from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
import platform
import sys
import traceback
from pathlib import Path

import pymupdf4llm.helpers.document_layout as document_layout

from pymupdf4llm_modern_rapidocr_demo import rapidocr_latest_compat
from pymupdf4llm_modern_rapidocr_demo.parse_samples import parse_input


SAMPLES = [
    Path("samples/chinese_bank_cashflow.png"),
    Path("samples/dongxing_mining_report.jpg"),
    Path("samples/galaxy_securities_disclaimer.png"),
]

EXPECTED_SHA256 = {
    "chinese_bank_cashflow.md": (
        "f8bf15442bafc1dbe0997ec73ac72c4ab20b0287a2bd174e71ed0241a0d6419a"
    ),
    "dongxing_mining_report.md": (
        "84e8a4b66603cac99c84b680cf6a7f5ca14c39e4f36acfff988c4af96a112869"
    ),
    "galaxy_securities_disclaimer.md": (
        "43336c289f3e79ba653ffa629d0b55f9109d7cbd4b2bc675ee8c17fb56c5c45b"
    ),
}


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not-installed"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_step_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as file:
        file.write(markdown)
        file.write("\n")


def build_markdown(report: dict) -> str:
    status = "PASS" if report["ok"] else "FAIL"
    lines = [
        f"# PyMuPDF4LLM RapidOCR compatibility: {status}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Matrix OS | `{report['matrix']['os']}` |",
        f"| Matrix Python | `{report['matrix']['python']}` |",
        f"| Platform | `{report['platform']['platform']}` |",
        f"| Python | `{report['python']['version']}` |",
        f"| RapidOCR class | `{report['rapidocr']['class_module']}` |",
        f"| Selected OCR function | `{report['rapidocr']['selected_function']}` |",
        f"| Legacy rapidocr_onnxruntime installed | `{report['rapidocr']['legacy_installed']}` |",
        "",
        "## Package Versions",
        "",
        "| Package | Version |",
        "|---|---|",
    ]
    for name, version in report["packages"].items():
        lines.append(f"| `{name}` | `{version}` |")

    lines.extend(
        [
            "",
            "## Markdown Outputs",
            "",
            "| File | Bytes | SHA-256 | Expected | Result |",
            "|---|---:|---|---|---|",
        ]
    )
    for item in report["outputs"]:
        result = "PASS" if item["matches_expected"] else "FAIL"
        lines.append(
            "| `{name}` | {bytes} | `{sha256}` | `{expected_sha256}` | {result} |".format(
                **item,
                result=result,
            )
        )

    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in report["errors"]:
            lines.append(f"- {error}")

    return "\n".join(lines) + "\n"


def run(output_dir: Path, ocr_dpi: int) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "ok": False,
        "matrix": {
            "os": os.environ.get("CI_MATRIX_OS", ""),
            "python": os.environ.get("CI_MATRIX_PYTHON", ""),
        },
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version.replace("\n", " "),
        },
        "packages": {
            "pymupdf": package_version("pymupdf"),
            "pymupdf4llm": package_version("pymupdf4llm"),
            "pymupdf-layout": package_version("pymupdf-layout"),
            "rapidocr": package_version("rapidocr"),
            "rapidocr_onnxruntime": package_version("rapidocr_onnxruntime"),
            "onnxruntime": package_version("onnxruntime"),
            "numpy": package_version("numpy"),
        },
        "rapidocr": {
            "selector_before_install": "",
            "selector_after_install": "",
            "selected_function": "",
            "selected_is_compat_exec_ocr": False,
            "class_module": "",
            "engine_type": "",
            "modern_installed": False,
            "legacy_installed": False,
        },
        "outputs": [],
        "errors": [],
    }

    try:
        before_module = document_layout.select_ocr_function.__module__
        rapidocr_latest_compat.install()
        selected = document_layout.select_ocr_function()
        engine = rapidocr_latest_compat._engine()
        report["rapidocr"] = {
            "selector_before_install": before_module,
            "selector_after_install": document_layout.select_ocr_function.__module__,
            "selected_function": f"{selected.__module__}.{selected.__name__}",
            "selected_is_compat_exec_ocr": selected is rapidocr_latest_compat.exec_ocr,
            "class_module": rapidocr_latest_compat.RapidOCR.__module__,
            "engine_type": f"{type(engine).__module__}.{type(engine).__qualname__}",
            "modern_installed": importlib.util.find_spec("rapidocr") is not None,
            "legacy_installed": importlib.util.find_spec("rapidocr_onnxruntime")
            is not None,
        }

        if selected is not rapidocr_latest_compat.exec_ocr:
            report["errors"].append("PyMuPDF4LLM did not select the compatibility OCR hook.")
        if rapidocr_latest_compat.RapidOCR.__module__.split(".")[0] != "rapidocr":
            report["errors"].append("Compatibility hook is not using the modern rapidocr package.")
        if report["rapidocr"]["legacy_installed"]:
            report["errors"].append("Legacy rapidocr_onnxruntime is installed in the CI environment.")

        for sample in SAMPLES:
            result = parse_input(sample, output_dir, ocr_dpi)
            output_path = Path(result["output"])
            output_hash = sha256(output_path)
            expected_hash = EXPECTED_SHA256[output_path.name]
            item = {
                "input": result["input"],
                "name": output_path.name,
                "path": str(output_path),
                "bytes": result["bytes"],
                "empty": result["empty"],
                "sha256": output_hash,
                "expected_sha256": expected_hash,
                "matches_expected": output_hash == expected_hash,
            }
            report["outputs"].append(item)
            if item["empty"]:
                report["errors"].append(f"{output_path.name} was empty.")
            if not item["matches_expected"]:
                report["errors"].append(
                    f"{output_path.name} hash mismatch: {output_hash} != {expected_hash}"
                )
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()

    report["ok"] = not report["errors"]
    report_path = output_dir / "compatibility-report.json"
    summary_path = output_dir / "compatibility-summary.md"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    summary = build_markdown(report)
    summary_path.write_text(summary, encoding="utf-8", newline="\n")
    append_step_summary(summary)
    return 0 if report["ok"] else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("ci-output"))
    parser.add_argument("--ocr-dpi", type=int, default=150)
    args = parser.parse_args()
    raise SystemExit(run(args.output_dir, args.ocr_dpi))


if __name__ == "__main__":
    main()
