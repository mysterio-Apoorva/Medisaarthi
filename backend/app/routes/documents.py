"""Protected document endpoints and document-to-history integration."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.app.ai.orchestrator import orchestrator
from backend.app.document_processing import DocumentResult, classify_and_extract, document_review, validate_and_store
from backend.app.security import AuthenticatedUser, assert_patient_access, current_user
from backend.app.store import now, store

router = APIRouter(prefix="/documents", tags=["Document Processing"])


def _normalised_value(value) -> tuple[str, ...]:
    values = value if isinstance(value, list) else [value]
    return tuple(sorted(" ".join(str(item).casefold().split()).strip(" .,:;") for item in values))


def _event_date(result: DocumentResult, fallback: str) -> str:
    return f"{result.document_date}T00:00:00+00:00" if result.document_date else fallback


def _append_timeline_event(db, *, patient_id: str, encounter_id: str, document_id: str, event_type: str, title: str, detail: str, page_number: int | None, confidence: float, occurred_at: str, verification_status: str = "NEEDS_VERIFICATION", evidence: str | None = None) -> None:
    """De-duplicate a repeated extracted statement while retaining all source links."""
    existing = db.execute(
        """SELECT * FROM timeline_events WHERE patient_id=? AND event_type=? AND title=?
           AND occurred_at=? ORDER BY created_at LIMIT 1""",
        (patient_id, event_type, title, occurred_at),
    ).fetchone()
    source_ref = {"document_id": document_id, "page_number": page_number, "evidence": evidence}
    if existing:
        metadata = json.loads(existing["metadata_json"] or "{}")
        sources = metadata.setdefault("sources", [])
        if source_ref not in sources:
            sources.append(source_ref)
            db.execute("UPDATE timeline_events SET metadata_json=? WHERE event_id=?", (json.dumps(metadata, ensure_ascii=False), existing["event_id"]))
        return
    db.execute(
        """INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,document_id,page_number,verification_status,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"EVT_{uuid4().hex}", patient_id, encounter_id, event_type, title, detail, "DOCUMENT_EXTRACTED", confidence, occurred_at, now(), document_id, page_number, verification_status, json.dumps({"sources": [source_ref]}, ensure_ascii=False)),
    )


def _persist_processed_document(db, *, document_id: str, patient_id: str, encounter_id: str, processed: DocumentResult, replace: bool = False) -> None:
    """Persist immutable source evidence before creating review candidates."""
    if replace:
        db.execute("DELETE FROM reconciliation_items WHERE document_id=? AND status='OPEN'", (document_id,))
        db.execute("DELETE FROM document_extractions WHERE document_id=?", (document_id,))
        db.execute("DELETE FROM document_pages WHERE document_id=?", (document_id,))
        db.execute("DELETE FROM document_entities WHERE document_id=?", (document_id,))
        db.execute(
            """UPDATE documents SET classification=?,processing_status=?,error_code=?,document_date=?,classification_confidence=?,processing_detail_json=?
               WHERE document_id=?""",
            (processed.classification, processed.processing_status, processed.error_code, processed.document_date, processed.classification_confidence, json.dumps(processed.processing_steps), document_id),
        )
    db.execute(
        """INSERT INTO document_extractions(extraction_id,document_id,raw_text,extracted_json,confidence,provenance,created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (f"DEX_{uuid4().hex}", document_id, processed.raw_text, json.dumps(processed.extracted, ensure_ascii=False), processed.confidence, "DOCUMENT_EXTRACTED", now()),
    )
    for page in processed.pages:
        db.execute(
            """INSERT INTO document_pages(document_page_id,document_id,page_number,raw_text,extraction_method,confidence,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (f"DPA_{uuid4().hex}", document_id, page.page_number, page.text, page.extraction_method, page.confidence, now()),
        )
    for entity in processed.entities:
        db.execute(
            """INSERT INTO document_entities(entity_id,document_id,page_number,entity_type,field_name,value_json,normalized_value,evidence,confidence,verification_status,entity_metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"DEN_{uuid4().hex}", document_id, entity["page_number"], entity["entity_type"], entity.get("field_name"), json.dumps(entity["value"], ensure_ascii=False), entity.get("normalized_value"), entity["evidence"], entity["confidence"], "NEEDS_VERIFICATION", json.dumps({key: value for key, value in entity.items() if key not in {"entity_type", "field_name", "value", "normalized_value", "evidence", "page_number", "confidence"}}, ensure_ascii=False), now(), now()),
        )
    for fact in processed.extracted:
        first_page = fact["page_numbers"][0] if fact.get("page_numbers") else None
        current = db.execute(
            """SELECT fact_id,value_json FROM clinical_facts WHERE encounter_id=? AND field_name=?
               AND superseded_at IS NULL ORDER BY created_at DESC LIMIT 1""",
            (encounter_id, fact["field_name"]),
        ).fetchone()
        current_value = json.loads(current["value_json"]) if current and "value_json" in current.keys() else None
        if current and _normalised_value(current_value) == _normalised_value(fact["value"]):
            store.audit(db, None, "DOCUMENT_FACT_MATCHED", "DOCUMENT", document_id, {"field": fact["field_name"]})
            continue
        db.execute(
            """INSERT INTO reconciliation_items(reconciliation_id,encounter_id,field_name,current_fact_id,incoming_value_json,incoming_source,confidence,status,created_at,document_id,page_number,evidence)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"REC_{uuid4().hex}", encounter_id, fact["field_name"], current["fact_id"] if current else None, json.dumps(fact["value"], ensure_ascii=False), "DOCUMENT_EXTRACTED", processed.confidence, "OPEN", now(), document_id, first_page, fact["evidence"]),
        )
    occurred_at = _event_date(processed, now())
    _append_timeline_event(
        db,
        patient_id=patient_id,
        encounter_id=encounter_id,
        document_id=document_id,
        event_type="DOCUMENT_UPLOADED",
        title="Medical document added",
        detail=f"{processed.classification or 'Unknown document'}: source retained for clinician review.",
        page_number=None,
        confidence=processed.classification_confidence,
        occurred_at=occurred_at,
        evidence=None,
    )
    event_labels = {
        "DIAGNOSIS": "Document mentions diagnosis",
        "MEDICATION": "Document lists medication",
        "ALLERGY": "Document lists allergy information",
        "INVESTIGATION": "Document investigation result",
        "VITAL": "Document vital sign",
        "PROCEDURE": "Document mentions procedure",
    }
    for entity in processed.entities:
        label = event_labels.get(entity["entity_type"])
        if not label:
            continue
        suffix = " (abnormal result)" if entity.get("abnormal_status") in {"LOW", "HIGH"} else ""
        _append_timeline_event(
            db,
            patient_id=patient_id,
            encounter_id=encounter_id,
            document_id=document_id,
            event_type=f"DOCUMENT_{entity['entity_type']}",
            title=f"{label}: {entity['value']}{suffix}",
            detail="Extracted from uploaded document; clinician verification is required.",
            page_number=entity["page_number"],
            confidence=entity["confidence"],
            occurred_at=occurred_at,
            evidence=entity["evidence"],
        )


def _document_with_counts(db, document_id: str) -> dict:
    row = db.execute(
        """SELECT d.*, COUNT(e.entity_id) AS entity_count FROM documents d
           LEFT JOIN document_entities e ON e.document_id=d.document_id
           WHERE d.document_id=? GROUP BY d.document_id""",
        (document_id,),
    ).fetchone()
    return dict(row)


@router.post("/encounters/{encounter_id}", status_code=status.HTTP_201_CREATED)
async def upload(encounter_id: str, file: UploadFile = File(...), user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        encounter = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not encounter:
            raise HTTPException(status_code=404, detail="Encounter not found")
        encounter = dict(encounter)
        assert_patient_access(db, user, encounter["patient_id"])
        if user.role != "PATIENT":
            raise HTTPException(status_code=403, detail="Only the patient may upload a source document")
        if encounter["status"] == "FINALIZED":
            raise HTTPException(status_code=409, detail="Finalized encounters cannot receive documents")
        consent = db.execute("SELECT 1 FROM consents WHERE patient_id=? AND consent_type='DOCUMENT_PROCESSING' AND status='GRANTED'", (encounter["patient_id"],)).fetchone()
        if not consent:
            raise HTTPException(status_code=409, detail="Document processing consent is required")
    upload_root = Path(os.getenv("DOCUMENT_UPLOAD_DIR", "backend/data/uploads"))
    path, original_name, size_bytes = await validate_and_store(file, upload_root)
    try:
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        with store.connection() as db:
            if db.execute('SELECT 1 FROM documents WHERE encounter_id=? AND content_hash=?', (encounter_id, content_hash)).fetchone():
                raise HTTPException(409, 'This document has already been uploaded to this encounter')
        processed = await run_in_threadpool(orchestrator.document.run, path)
        document_id = f"DOC_{uuid4().hex}"
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute('SELECT status FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
            if not current or current['status'] == 'FINALIZED':
                raise HTTPException(409, 'The encounter was finalized while the document was processing')
            if db.execute('SELECT 1 FROM documents WHERE encounter_id=? AND content_hash=?', (encounter_id, content_hash)).fetchone():
                raise HTTPException(409, 'This document has already been uploaded to this encounter')
            db.execute(
                """INSERT INTO documents(document_id,patient_id,encounter_id,original_name,stored_name,mime_type,size_bytes,classification,processing_status,error_code,uploaded_by,uploaded_at,document_date,classification_confidence,processing_detail_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (document_id, encounter["patient_id"], encounter_id, original_name, path.name, file.content_type or "application/octet-stream", size_bytes, processed.classification, processed.processing_status, processed.error_code, user.user_id, now(), processed.document_date, processed.classification_confidence, json.dumps(processed.processing_steps)),
            )
            _persist_processed_document(db, document_id=document_id, patient_id=encounter["patient_id"], encounter_id=encounter_id, processed=processed)
            db.execute('UPDATE documents SET content_hash=? WHERE document_id=?', (content_hash, document_id))
            db.execute('UPDATE encounters SET revision=revision+1 WHERE encounter_id=?', (encounter_id,))
            store.audit(db, user.user_id, "DOCUMENT_PROCESSED", "DOCUMENT", document_id, {"status": processed.processing_status, "classification": processed.classification, "entity_count": len(processed.entities)})
            result = _document_with_counts(db, document_id)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {
        "document_id": document_id,
        "processing_status": processed.processing_status,
        "classification": processed.classification,
        "classification_confidence": processed.classification_confidence,
        "document_date": processed.document_date,
        "extracted_count": len(processed.extracted),
        "entity_count": result["entity_count"],
        "confidence": processed.confidence,
        "processing_steps": processed.processing_steps,
        "error_code": processed.error_code,
    }


@router.get("/{document_id}/file")
def download(document_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        assert_patient_access(db, user, row["patient_id"])
        root = Path(os.getenv("DOCUMENT_UPLOAD_DIR", "backend/data/uploads")).resolve()
        path = (root / row["stored_name"]).resolve()
        if path.parent != root or not path.is_file():
            raise HTTPException(status_code=404, detail="Document file is unavailable")
        store.audit(db, user.user_id, "DOCUMENT_VIEWED", "DOCUMENT", document_id)
        return FileResponse(path, media_type=row["mime_type"], filename=row["original_name"], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{document_id}/extraction")
def extraction(document_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        document = db.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        assert_patient_access(db, user, document["patient_id"])
        row = db.execute("SELECT * FROM document_extractions WHERE document_id=? ORDER BY created_at DESC LIMIT 1", (document_id,)).fetchone()
        pages = [dict(page) for page in db.execute("SELECT page_number,raw_text,extraction_method,confidence FROM document_pages WHERE document_id=? ORDER BY page_number", (document_id,))]
        entities = [dict(entity) | json.loads(entity["entity_metadata_json"] or "{}") | {"value": json.loads(entity["value_json"])} for entity in db.execute("SELECT * FROM document_entities WHERE document_id=? ORDER BY page_number,created_at", (document_id,))]
        matches = []
        for fact in json.loads(row["extracted_json"]) if row else []:
            current = db.execute("SELECT value_json FROM clinical_facts WHERE encounter_id=? AND field_name=? AND superseded_at IS NULL ORDER BY created_at DESC LIMIT 1", (document["encounter_id"], fact["field_name"])).fetchone()
            if not current:
                match_status = "NEW_CANDIDATE"
            elif _normalised_value(json.loads(current["value_json"])) == _normalised_value(fact["value"]):
                match_status = "CONSISTENT"
            else:
                match_status = "CONFLICT_REQUIRES_REVIEW"
            matches.append({"field_name": fact["field_name"], "status": match_status, "page_numbers": fact.get("page_numbers", [])})
        store.audit(db, user.user_id, "DOCUMENT_EXTRACTION_VIEWED", "DOCUMENT", document_id)
        return {
            "document_id": document_id,
            "status": document["processing_status"],
            "error_code": document["error_code"],
            "classification": document["classification"],
            "classification_confidence": document["classification_confidence"],
            "document_date": document["document_date"],
            "processing_steps": json.loads(document["processing_detail_json"] or "[]"),
            "text": row["raw_text"] if row else None,
            "facts": json.loads(row["extracted_json"]) if row else [],
            "match_results": matches,
            "pages": pages,
            "entities": entities,
            "review": document_review(entities, document["classification"], document["document_date"]),
            "source": "DOCUMENT_EXTRACTED",
            "requires_clinician_review": True,
        }


@router.get("/encounters/{encounter_id}")
def list_for_encounter(encounter_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        encounter = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not encounter:
            raise HTTPException(status_code=404, detail="Encounter not found")
        assert_patient_access(db, user, encounter["patient_id"])
        documents = [
            dict(row)
            for row in db.execute(
                """SELECT d.*, COUNT(e.entity_id) AS entity_count FROM documents d
                   LEFT JOIN document_entities e ON e.document_id=d.document_id
                   WHERE d.encounter_id=? GROUP BY d.document_id ORDER BY d.uploaded_at DESC""",
                (encounter_id,),
            )
        ]
        reviewed = {row['document_id'] for row in db.execute("SELECT DISTINCT document_id FROM reconciliation_items WHERE encounter_id=? AND status!='OPEN'", (encounter_id,))}
        for document in documents:
            document['can_retry'] = encounter['status'] != 'FINALIZED' and document['document_id'] not in reviewed
            document['can_remove'] = document['can_retry'] and user.role == 'PATIENT'
        store.audit(db, user.user_id, "DOCUMENT_LIST_VIEWED", "ENCOUNTER", encounter_id)
        return documents


@router.post("/{document_id}/retry")
async def retry(document_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT d.*, e.status AS encounter_status FROM documents d JOIN encounters e ON e.encounter_id=d.encounter_id WHERE d.document_id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        document = dict(row)
        assert_patient_access(db, user, document["patient_id"])
        if document["encounter_status"] == "FINALIZED":
            raise HTTPException(status_code=409, detail="Finalized records cannot be reprocessed")
        if db.execute("SELECT 1 FROM reconciliation_items WHERE document_id=? AND status!='OPEN'", (document_id,)).fetchone():
            raise HTTPException(409, 'A clinician has reviewed this document; its extraction cannot be replaced')
        root = Path(os.getenv("DOCUMENT_UPLOAD_DIR", "backend/data/uploads")).resolve()
        path = (root / document["stored_name"]).resolve()
        if path.parent != root or not path.is_file():
            raise HTTPException(status_code=404, detail="Document file is unavailable")
    processed = await run_in_threadpool(classify_and_extract, path)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute('SELECT e.status FROM documents d JOIN encounters e ON e.encounter_id=d.encounter_id WHERE d.document_id=?', (document_id,)).fetchone()
        if not current:
            raise HTTPException(404, 'The document was removed during processing')
        if current['status'] == 'FINALIZED':
            raise HTTPException(409, 'The encounter was finalized during processing')
        if db.execute("SELECT 1 FROM reconciliation_items WHERE document_id=? AND status!='OPEN'", (document_id,)).fetchone():
            raise HTTPException(409, 'A clinician has reviewed this document; its extraction cannot be replaced')
        _persist_processed_document(db, document_id=document_id, patient_id=document["patient_id"], encounter_id=document["encounter_id"], processed=processed, replace=True)
        db.execute('UPDATE encounters SET revision=revision+1 WHERE encounter_id=?', (document['encounter_id'],))
        store.audit(db, user.user_id, "DOCUMENT_REPROCESSED", "DOCUMENT", document_id, {"status": processed.processing_status, "entity_count": len(processed.entities)})
    return {"document_id": document_id, "processing_status": processed.processing_status, "entity_count": len(processed.entities), "error_code": processed.error_code, "processing_steps": processed.processing_steps}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(document_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT d.*, e.status AS encounter_status FROM documents d JOIN encounters e ON e.encounter_id=d.encounter_id WHERE d.document_id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        document = dict(row)
        assert_patient_access(db, user, document["patient_id"])
        if user.role != "PATIENT" or document["encounter_status"] == "FINALIZED":
            raise HTTPException(status_code=409, detail="This document can no longer be removed")
        if db.execute("SELECT 1 FROM reconciliation_items WHERE document_id=? AND status!='OPEN'", (document_id,)).fetchone():
            raise HTTPException(409, 'Clinician-reviewed source documents must be retained')
        root = Path(os.getenv("DOCUMENT_UPLOAD_DIR", "backend/data/uploads")).resolve()
        path = (root / document["stored_name"]).resolve()
        if path.parent != root:
            raise HTTPException(status_code=404, detail="Document file is unavailable")
        db.execute("DELETE FROM reconciliation_items WHERE document_id=? AND status='OPEN'", (document_id,))
        db.execute('DELETE FROM timeline_events WHERE document_id=?', (document_id,))
        db.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
        db.execute('UPDATE encounters SET revision=revision+1 WHERE encounter_id=?', (document['encounter_id'],))
        store.audit(db, user.user_id, "DOCUMENT_REMOVED", "DOCUMENT", document_id)
    path.unlink(missing_ok=True)
