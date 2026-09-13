from fastapi import APIRouter, HTTPException
from app.database import supabase
from app.schemas import PatientHistoryResponse

router = APIRouter(
    prefix="/patients",
    tags=["Patient History"]
)


@router.get("/{patient_id}/history", response_model=PatientHistoryResponse)
def get_patient_history(patient_id: str):
    clean_id = patient_id.strip()

    pat_info = None
    try:
        patient = (
            supabase
            .table("patients")
            .select("patient_id, name, age, gender, language")
            .eq("patient_id", clean_id)
            .execute()
        )
        if patient.data:
            pat_info = patient.data[0]
    except Exception:
        pass

    from app.routes.doctor import SYNTHETIC_PATIENT_DATA
    synth = SYNTHETIC_PATIENT_DATA.get(clean_id)

    if not pat_info:
        if synth:
            pat_info = {
                "patient_id": clean_id,
                "name": synth["name"],
                "age": synth["age"],
                "gender": synth["gender"].lower(),
                "language": synth.get("language", "hi")
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Patient not found"
            )

    # Get medical history
    medical_history = []
    try:
        med_hist = (
            supabase
            .table("medical_history")
            .select("condition, diagnosed_year, notes")
            .eq("patient_id", clean_id)
            .order("diagnosed_year")
            .execute()
        )
        medical_history = med_hist.data or []
    except Exception:
        pass

    if not medical_history and synth and synth.get("conditions"):
        medical_history = [
            {"condition": c["condition"], "diagnosed_year": int(c.get("date", "2021")), "notes": "Electronic health record"}
            for c in synth["conditions"]
        ]

    # Get medications
    medications = []
    try:
        meds = (
            supabase
            .table("medications")
            .select("name, dosage, frequency, notes")
            .eq("patient_id", clean_id)
            .execute()
        )
        medications = meds.data or []
    except Exception:
        pass

    if not medications and synth and synth.get("medications"):
        medications = [
            {"name": m["name"], "dosage": m.get("dosage", ""), "frequency": m.get("frequency", ""), "notes": None}
            for m in synth["medications"]
        ]

    # Get allergies
    allergies = []
    try:
        all_res = (
            supabase
            .table("allergies")
            .select("allergen, reaction")
            .eq("patient_id", clean_id)
            .execute()
        )
        allergies = all_res.data or []
    except Exception:
        pass

    if not allergies and synth and synth.get("allergies"):
        allergies = [
            {"allergen": a["allergen"], "reaction": a.get("reaction")}
            for a in synth["allergies"]
        ]

    return {
        "patient": pat_info,
        "medical_history": medical_history,
        "medications": medications,
        "allergies": allergies
    }