# PyMuPDF4LLM 1.28 + Modern RapidOCR Demo

This repo shows the minimal compatibility layer needed to run public
`pymupdf4llm==1.28.0` with modern `rapidocr` instead of the legacy
`rapidocr_onnxruntime` package.

The compatibility code is in:

```text
src/pymupdf4llm_modern_rapidocr_demo/rapidocr_latest_compat.py
```

Run the sample parser:

```bash
uv run pymupdf4llm-modern-rapidocr-demo
```

Or pass explicit documents/images:

```bash
uv run pymupdf4llm-modern-rapidocr-demo path/to/file.png --output-dir output
```

The demo defaults to `--ocr-dpi 150`.
The compatibility function itself keeps PyMuPDF4LLM's default OCR callback
signature, where `dpi=300`; `to_markdown(..., ocr_dpi=150)` passes 150 into it.

## What The Shim Changes

Public PyMuPDF4LLM 1.28 expects the legacy package and API:

```python
from rapidocr_onnxruntime import RapidOCR
result, elapsed = RapidOCR()(img)
```

Modern RapidOCR uses:

```python
from rapidocr import RapidOCR
result = RapidOCR()(img)
```

where `result` is a `RapidOCROutput` object with `boxes`, `txts`, and `scores`.
The shim converts that object into the `(box, text, score)` shape used by the
existing PyMuPDF4LLM OCR insertion logic, then monkey-patches
`pymupdf4llm.helpers.document_layout.select_ocr_function`.

## Included Samples

The repo includes three sample inputs:

```text
samples/chinese_bank_cashflow.png
samples/dongxing_mining_report.jpg
samples/galaxy_securities_disclaimer.png
```

## Verified Locally

The included samples were parsed with:

```bash
uv run pymupdf4llm-modern-rapidocr-demo --output-dir output --ocr-dpi 150
```

Installed versions:

```text
pymupdf==1.28.0
pymupdf4llm==1.28.0
pymupdf-layout==1.28.0
rapidocr==3.9.1
```

Result:

```text
parsed=3 empty=0 output_dir=output
```

Python compatibility was checked on Linux x86_64 GNU with:

```text
Python 3.10.20
Python 3.11.15
Python 3.12.13
Python 3.13.14
Python 3.14.6
```

For the included samples, the generated Markdown files were byte-for-byte
identical across all Python versions listed above. The output SHA-256 hashes
were:

```text
chinese_bank_cashflow.md          f8bf15442bafc1dbe0997ec73ac72c4ab20b0287a2bd174e71ed0241a0d6419a
dongxing_mining_report.md         84e8a4b66603cac99c84b680cf6a7f5ca14c39e4f36acfff988c4af96a112869
galaxy_securities_disclaimer.md   43336c289f3e79ba653ffa629d0b55f9109d7cbd4b2bc675ee8c17fb56c5c45b
```

## GitHub Actions Matrix

The compatibility workflow verifies the sample parser across this matrix:

```text
Operating systems: ubuntu-latest, windows-latest, macos-latest
Python versions:   3.10, 3.11, 3.12, 3.13, 3.14
```

The workflow checks that the parser runs successfully, generates non-empty
Markdown for every included sample, selects this compatibility OCR hook, uses
modern `rapidocr`, and does not install `rapidocr_onnxruntime`.

Verified run:

```text
https://github.com/pymupdf/pymupdf4llm-modern-rapidocr-demo/actions/runs/28900293247
```
