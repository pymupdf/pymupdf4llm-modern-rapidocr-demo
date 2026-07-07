"""Compatibility hook for PyMuPDF4LLM 1.28 with the modern rapidocr package."""

from __future__ import annotations

import numpy as np
import pymupdf
from rapidocr import RapidOCR

from pymupdf4llm.ocr.get_culled_pixmap import get_pixmap


FONT = pymupdf.Font("cjk")
FONTNAME = "myfont"
REPLACEMENT_UNICODE = chr(0xFFFD)
STROKED_TEXT = pymupdf.mupdf.FZ_STEXT_STROKED
FILLED_TEXT = pymupdf.mupdf.FZ_STEXT_FILLED
_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = RapidOCR()
    return _ENGINE


def _ocr_text(span) -> bool:
    if (span["char_flags"] & STROKED_TEXT) or (span["char_flags"] & FILLED_TEXT):
        return False
    return True


def _normalize_results(engine_output):
    if isinstance(engine_output, tuple):
        result, _ = engine_output
        return result or []

    boxes = getattr(engine_output, "boxes", None)
    txts = getattr(engine_output, "txts", None)
    scores = getattr(engine_output, "scores", None)
    if boxes is None or txts is None or scores is None:
        return []
    return list(zip(boxes, txts, scores))


def exec_ocr(page, dpi=300, pixmap=None, language="eng", keep_ocr_text=False):
    """PyMuPDF4LLM OCR callback backed by modern rapidocr."""

    def adjust_width(text, fontsize, rect):
        text_len = FONT.text_length(text, fontsize)
        if text_len > 0:
            return pymupdf.Matrix(rect.width / text_len, 1)
        return pymupdf.Matrix(1, 1)

    displaylist = page.get_displaylist()
    stextpage = displaylist.get_textpage(flags=pymupdf.TEXT_ACCURATE_BBOXES)
    textpage = pymupdf.TextPage(stextpage)
    text_blocks = textpage.extractDICT()["blocks"]

    spans = []
    fffd_spans = []
    ocr_spans = []
    for block in text_blocks:
        for line in block["lines"]:
            for span in line["spans"]:
                if _ocr_text(span):
                    ocr_spans.append(span["bbox"])
                elif REPLACEMENT_UNICODE in span["text"]:
                    fffd_spans.append(span["bbox"])
                else:
                    spans.append(span["bbox"])
    if ocr_spans and keep_ocr_text:
        return

    pix = get_pixmap(displaylist, dpi=dpi, rects=spans)
    matrix = pymupdf.Rect(pix.irect).torect(page.rect)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

    result = _normalize_results(_engine()(img))
    if not result:
        return

    redaction_rects = fffd_spans + ocr_spans
    if redaction_rects:
        for bbox in redaction_rects:
            page.add_redact_annot(bbox)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )

    page.insert_font(fontname=FONTNAME, fontbuffer=FONT.buffer)
    for box, text, _conf in result:
        rect = (
            pymupdf.Rect(
                min(point[0] for point in box),
                min(point[1] for point in box),
                max(point[0] for point in box),
                max(point[1] for point in box),
            )
            * matrix
        )
        if not text.strip():
            continue

        fontsize = rect.height
        page.insert_text(
            rect.bl + (0, -0.2 * fontsize),
            text,
            fontsize=fontsize,
            fontname=FONTNAME,
            morph=(rect.bl, adjust_width(text, fontsize, rect)),
        )


def _select_ocr_function():
    from pymupdf4llm.helpers.document_layout import INFO_MESSAGES

    print("Using RapidOCR for OCR processing.", file=INFO_MESSAGES)
    return exec_ocr


def install():
    import pymupdf4llm.helpers.document_layout as document_layout

    document_layout.select_ocr_function = _select_ocr_function
