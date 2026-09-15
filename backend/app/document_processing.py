"""Local medical-document processing with page-level, reviewable evidence.

The recognisers in this module only return text that was present in an uploaded
file. They classify and extract conservatively: an uncertain scan stays
reviewable instead of becoming a guessed clinical fact.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class PageResult:
    page_number: int
    text: str
    extraction_method: str
    confidence: float


@dataclass(frozen=True)
class DocumentResult:
    stored_name: str
    size_bytes: int
    classification: str | None
    processing_status: str
    raw_text: str | None
    extracted: list[dict]
    confidence: float
    pages: list[PageResult]
    entities: list[dict]
    document_date: str | None = None
    classification_confidence: float = 0.0
    processing_steps: tuple[str, ...] = ()
    error_code: str | None = None


async def validate_and_store(upload: UploadFile, upload_root: Path) -> tuple[Path, str, int]:
    safe_name = Path(upload.filename or "upload").name
    suffix = Path(safe_name).suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES or upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF, JPEG, PNG, and WebP medical reports are accepted")
    payload = await upload.read(MAX_DOCUMENT_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The uploaded document is empty")
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Document exceeds the 10 MB limit")
    signatures = {
        ".pdf": payload.startswith(b"%PDF-"),
        ".png": payload.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": payload.startswith(b"\xff\xd8\xff"),
        ".jpeg": payload.startswith(b"\xff\xd8\xff"),
        ".webp": payload.startswith(b"RIFF") and payload[8:12] == b"WEBP",
    }
    types = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    if not signatures[suffix] or upload.content_type != types[suffix]:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The document header, extension, and content type must match")
    upload_root.mkdir(parents=True, exist_ok=True)
    path = upload_root / f"{uuid4().hex}{suffix}"
    path.write_bytes(payload)
    return path, safe_name, len(payload)


def _prepared_image(image):
    """A deterministic preprocessing pass that improves photographed text."""
    from PIL import ImageOps

    return ImageOps.autocontrast(ImageOps.grayscale(image.convert("RGB")))


@lru_cache(maxsize=1)
def _rapid_ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)


def _ocr(image) -> tuple[str, float]:
    image = _prepared_image(image)
    if shutil.which("tesseract"):
        import pytesseract

        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6", timeout=20)
        words = [word.strip() for word in data["text"] if word.strip()]
        confidences = [float(value) for value in data["conf"] if str(value).strip() not in {"", "-1"} and float(value) >= 0]
        return " ".join(words).strip(), round((sum(confidences) / len(confidences) / 100) if confidences else 0.0, 3)
    import numpy as np

    result, _ = _rapid_ocr()(np.array(image.convert("RGB")))
    lines = result or []
    text = "\n".join(str(line[1]).strip() for line in lines if len(line) > 1 and str(line[1]).strip())
    confidences = [float(line[2]) for line in lines if len(line) > 2 and isinstance(line[2], (float, int))]
    return text.strip(), round(sum(confidences) / len(confidences), 3) if confidences else 0.0


def _extract_pdf_pages(path: Path) -> list[PageResult]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF_TEXT_ENGINE_UNAVAILABLE") from exc
    document = pymupdf.open(path)
    try:
        if len(document) > 20 or document.needs_pass:
            raise RuntimeError("DOCUMENT_REQUIRES_MANUAL_REVIEW")
        pages: list[PageResult] = []
        for index in range(1, len(document) + 1):
            page = document.load_page(index - 1)
            text = page.get_text("text").strip()
            if text:
                pages.append(PageResult(index, text, "PDF_TEXT", 0.98))
                continue
            from PIL import Image

            pix = page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), colorspace=pymupdf.csRGB)
            text, confidence = _ocr(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
            pages.append(PageResult(index, text, "OCR", confidence))
        return pages
    finally:
        document.close()


def _extract_image_pages(path: Path) -> list[PageResult]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("OCR_ENGINE_UNAVAILABLE") from exc
    with Image.open(path) as image:
        if image.width * image.height > 20_000_000:
            raise RuntimeError("IMAGE_TOO_LARGE_FOR_OCR")
        text, confidence = _ocr(image)
        return [PageResult(1, text, "OCR", confidence)]


CLASSIFIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Prescription", ("prescription", "rx", "tablet", "capsule", "dose", "od", "bd", "twice daily")),
    ("Laboratory Report", ("reference range", "hemoglobin", "haemoglobin", "blood glucose", "cbc", "biochemistry", "specimen")),
    ("Discharge Summary", ("discharge summary", "date of admission", "date of discharge", "hospital course")),
    ("Radiology Report", ("radiology", "x-ray", "ct scan", "mri", "ultrasound", "impression")),
    ("Pathology Report", ("pathology", "histopathology", "biopsy", "cytology")),
    ("Surgery Report", ("operative note", "operation performed", "surgery", "procedure performed")),
    ("Referral Letter", ("referral", "referred to", "dear doctor")),
    ("Medical Certificate", ("medical certificate", "certified that", "fit to resume")),
    ("AYUSH Consultation Note", ("ayurveda", "ayurvedic", "prakriti", "ahara", "vihara", "panchakarma")),
)


def _classify(text: str) -> tuple[str, float]:
    lowered = text.casefold()
    ranked = [(label, sum(1 for marker in markers if marker in lowered), len(markers)) for label, markers in CLASSIFIERS]
    label, matches, total = max(ranked, key=lambda item: item[1])
    if not matches:
        medical = any(marker in lowered for marker in ("patient", "hospital", "diagnosis", "medicine", "report"))
        return ("Other Medical Document", 0.45) if medical else ("Unknown", 0.1)
    return label, round(min(0.96, 0.55 + matches / max(total, 1) * 0.35), 3)


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split()).strip(" .,:;")


def _safe_date(value: str) -> str | None:
    cleaned = " ".join(value.replace(",", " ").split())
    formats = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y")
    for date_format in formats:
        try:
            return datetime.strptime(cleaned, date_format).date().isoformat()
        except ValueError:
            continue
    return None


DATE_PATTERN = re.compile(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4})\b", re.I)


def _entity(entity_type: str, page: PageResult, value: str, evidence: str, field_name: str | None = None, confidence: float | None = None, **extra) -> dict:
    return {
        "entity_type": entity_type,
        "field_name": field_name,
        "value": value,
        "normalized_value": _normalise(value),
        "evidence": evidence.strip()[:1200],
        "page_number": page.page_number,
        "confidence": round(min(0.99, confidence if confidence is not None else max(0.35, page.confidence * 0.9)), 3),
        **extra,
    }


MEDICATION_PATTERN = re.compile(r"(?im)^\s*(?:rx\s*[:\-]?\s*)?(?:tab(?:let)?\.?|cap(?:sule)?\.?|syp(?:rup)?\.?|inj(?:ection)?\.?)\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 .+()/\-]{1,100})$")
ALLERGY_PATTERN = re.compile(r"(?im)^\s*(?:drug\s+)?allerg(?:y|ies)\s*[:\-]\s*(.{2,180})$")
DIAGNOSIS_PATTERN = re.compile(r"(?im)^\s*(?:diagnosis|diagnoses|assessment|provisional diagnosis|final diagnosis|impression)\s*[:\-]\s*(.{2,300})$")
PROCEDURE_PATTERN = re.compile(r"(?im)^\s*(?:procedure|operation|surgery|operative procedure|procedure performed)\s*[:\-]\s*(.{2,300})$")
PATIENT_PATTERN = re.compile(r"(?im)^\s*(?:patient(?:\s+name)?|name)\s*[:\-]\s*([A-Za-z][A-Za-z .'-]{1,120})$")
PROVIDER_PATTERN = re.compile(r"(?im)^\s*(?:hospital|clinic|provider|hospital name)\s*[:\-]\s*([A-Za-z][A-Za-z0-9 .&()'-]{1,160})$")
VITAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Blood pressure", re.compile(r"\b(?:bp|blood pressure)\s*[:\-]?\s*(\d{2,3}\s*/\s*\d{2,3})[ \t]*(?P<unit>mmhg)?\b", re.I)),
    ("Pulse", re.compile(r"\b(?:pulse|heart rate|hr)\s*[:\-]?\s*(\d{2,3})[ \t]*(?P<unit>bpm|/min)?\b", re.I)),
    ("Temperature", re.compile(r"\b(?:temp(?:erature)?)\s*[:\-]?\s*(\d{2,3}(?:\.\d+)?)[ \t]*(?P<unit>°?[ \t]*[CF])?\b", re.I)),
    ("SpO2", re.compile(r"\b(?:spo2|o2\s*sat(?:uration)?)\s*[:\-]?\s*(\d{2,3})\b[ \t]*(?P<unit>%)?", re.I)),
    ("Weight", re.compile(r"\bweight\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)\s*(?P<unit>kg)\b", re.I)),
    ("Height", re.compile(r"\bheight\s*[:\-]?\s*(\d{1,3}(?:\.\d+)?)\s*(?P<unit>cm|m)\b", re.I)),
)
LAB_PATTERN = re.compile(r"(?im)^[ \t]*((?:ha?emoglobin|hb|wbc|rbc|platelet(?:s)?|blood[ \t]*glucose|glucose|hba1c|creatinine|urea|sodium|potassium|cholesterol|triglyceride|tsh|bilirubin|alt|ast))[ \t]*[:\-]?[ \t]*(\d+(?:\.\d+)?)[ \t]*([A-Za-z%/^0-9.]+)?(?:[ \t]*(?:\(|\[)?[ \t]*(?:(?:reference[ \t]*range|normal)[ \t]*[:\-]?[ \t]*)?([0-9.]+)[ \t]*(?:-|–|to)[ \t]*([0-9.]+)[ \t]*[\)\]]?)?[ \t]*$")


def _abnormal(value: str, lower: str | None, upper: str | None) -> str | None:
    if lower is None or upper is None:
        return None
    try:
        number = float(value)
        if number < float(lower):
            return "LOW"
        if number > float(upper):
            return "HIGH"
    except ValueError:
        return None
    return "NORMAL"


def _entities_from_page(page: PageResult) -> list[dict]:
    entities: list[dict] = []
    text = page.text
    for match in DATE_PATTERN.finditer(text):
        parsed = _safe_date(match.group(0))
        if parsed:
            entities.append(_entity("DATE", page, parsed, match.group(0), confidence=max(0.75, page.confidence)))
    for pattern, entity_type, field in ((MEDICATION_PATTERN, "MEDICATION", "medications"), (ALLERGY_PATTERN, "ALLERGY", "allergies"), (DIAGNOSIS_PATTERN, "DIAGNOSIS", "past_medical_history"), (PROCEDURE_PATTERN, "PROCEDURE", "past_surgical_history")):
        for match in pattern.finditer(text):
            value = match.group(1).strip(" .;:-")
            if value and value.casefold() not in {"none", "nil", "none known", "no known allergies"}:
                entities.append(_entity(entity_type, page, value, match.group(0), field))
            elif entity_type == "ALLERGY":
                entities.append(_entity(entity_type, page, "No known allergies", match.group(0), field))
    for pattern, entity_type in ((PATIENT_PATTERN, "PATIENT_IDENTIFIER"), (PROVIDER_PATTERN, "PROVIDER")):
        for match in pattern.finditer(text):
            entities.append(_entity(entity_type, page, match.group(1).strip(), match.group(0), confidence=max(0.6, page.confidence * 0.8)))
    for label, pattern in VITAL_PATTERNS:
        for match in pattern.finditer(text):
            unit = (match.groupdict().get('unit') or '').strip()
            entities.append(_entity("VITAL", page, f"{label}: {match.group(1).replace(' ', '')}" + (f' {unit}' if unit else ''), match.group(0), "document_vitals"))
    for match in LAB_PATTERN.finditer(text):
        test, value, unit, low, high = match.groups()
        abnormal = _abnormal(value, low, high)
        result = f"{test.strip()}: {value}{(' ' + unit) if unit else ''}"
        if low is not None and high is not None:
            result += f" (reference {low}-{high}; {abnormal or 'UNASSESSED'})"
        entities.append(_entity("INVESTIGATION", page, result, match.group(0), "document_investigations", abnormal_status=abnormal))
    unique: dict[tuple[str, str | None, str, int], dict] = {}
    for item in entities:
        unique[(item["entity_type"], item["field_name"], item["normalized_value"], item["page_number"])] = item
    return list(unique.values())


def _facts_from_entities(entities: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for entity in entities:
        field = entity.get("field_name")
        if not field:
            continue
        group = grouped.setdefault(field, {"field_name": field, "value": [], "evidence": [], "page_numbers": []})
        if entity["value"] not in group["value"]:
            group["value"].append(entity["value"])
        group["evidence"].append(entity["evidence"])
        group["page_numbers"].append(entity["page_number"])
    return [{**fact, "evidence": "\n".join(dict.fromkeys(fact["evidence"])), "page_numbers": sorted(set(fact["page_numbers"]))} for fact in grouped.values()]


def document_review(entities: list[dict], classification: str | None, document_date: str | None) -> dict:
    """A bounded document-review agent output backed only by extracted evidence."""
    categories: dict[str, int] = {}
    for entity in entities:
        categories[entity["entity_type"]] = categories.get(entity["entity_type"], 0) + 1
    abnormal = [entity["value"] for entity in entities if entity.get("abnormal_status") in {"LOW", "HIGH"}]
    clinical = [entity["entity_type"] for entity in entities if entity["entity_type"] in {"DIAGNOSIS", "MEDICATION", "ALLERGY", "INVESTIGATION", "VITAL", "PROCEDURE"}]
    return {
        "document_type": classification or "Unknown",
        "document_date": document_date,
        "entity_counts": categories,
        "abnormal_results": abnormal,
        "requires_physician_verification": sorted(set(clinical)),
        "summary": f"{classification or 'Unknown document'}: {len(entities)} source-backed item(s) extracted; clinician verification is required.",
    }


def classify_and_extract(path: Path) -> DocumentResult:
    steps = ["VALIDATED"]
    try:
        pages = _extract_pdf_pages(path) if path.suffix.casefold() == ".pdf" else _extract_image_pages(path)
        steps.append("TEXT_EXTRACTED")
    except RuntimeError as exc:
        return DocumentResult(path.name, path.stat().st_size, None, "NEEDS_REVIEW", None, [], 0.0, [], [], processing_steps=tuple(steps), error_code=str(exc))
    except Exception:
        return DocumentResult(path.name, path.stat().st_size, None, "NEEDS_REVIEW", None, [], 0.0, [], [], processing_steps=tuple(steps), error_code="TEXT_EXTRACTION_UNAVAILABLE")
    raw_text = "\n\n".join(f"--- Page {page.page_number} ---\n{page.text}" for page in pages if page.text).strip()
    if not raw_text:
        return DocumentResult(path.name, path.stat().st_size, None, "NEEDS_REVIEW", "", [], 0.0, pages, [], processing_steps=tuple(steps), error_code="NO_MACHINE_READABLE_TEXT")
    classification, classification_confidence = _classify(raw_text)
    steps.append("CLASSIFIED")
    entities = [entity for page in pages for entity in _entities_from_page(page)]
    steps.extend(("CLINICAL_ENTITIES_EXTRACTED", "READY_FOR_RECONCILIATION"))
    dates = [entity["value"] for entity in entities if entity["entity_type"] == "DATE"]
    confidences = [entity["confidence"] for entity in entities] or [page.confidence for page in pages]
    return DocumentResult(path.name, path.stat().st_size, classification, "PROCESSED", raw_text[:80_000], _facts_from_entities(entities), round(sum(confidences) / len(confidences), 3) if confidences else 0.0, pages, entities, document_date=min(dates) if dates else None, classification_confidence=classification_confidence, processing_steps=tuple(steps))
