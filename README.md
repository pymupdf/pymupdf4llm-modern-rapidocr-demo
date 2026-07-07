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

Or pass explicit PDFs:

```bash
uv run pymupdf4llm-modern-rapidocr-demo path/to/file.pdf --output-dir output
```

The demo defaults to `--ocr-dpi 150`, matching the benchmark configuration.
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

## Verified Locally

The included sample PDFs were parsed with:

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
