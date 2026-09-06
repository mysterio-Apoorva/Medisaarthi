"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  approveDoctorSummary,
  getAuthStatus,
  getDoctorPatients,
  getDoctorSummary,
  getFullInterview,
  getTimeline,
  loginDoctor,
  saveDoctorSummary,
  setupDoctor,
} from "../../lib/api";
import {
  ClinicalSummary,
  DoctorPatient,
  EditableClinicalSummary,
  TimelineEvent,
} from "../../lib/contracts";

const TOKEN_KEY = "medisaarthi_doctor_token";

function Lines({ values, empty = "None recorded" }: { values: string[]; empty?: string }) {
  return values.length ? (
    <ul>{values.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}</ul>
  ) : <p className="empty-copy">{empty}</p>;
}

function editable(summary: ClinicalSummary): EditableClinicalSummary {
  const { interview_id, patient_id, status, version, updated_at, approved_at, ...value } = summary;
  return value;
}

export default function DoctorDashboard() {
  const [needsSetup, setNeedsSetup] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [doctorName, setDoctorName] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [patients, setPatients] = useState<DoctorPatient[]>([]);
  const [selected, setSelected] = useState<DoctorPatient | null>(null);
  const [summary, setSummary] = useState<ClinicalSummary | null>(null);
  const [draft, setDraft] = useState<EditableClinicalSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [fullInterview, setFullInterview] = useState<unknown>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPatients = useCallback(async (sessionToken: string) => {
    try {
      const rows = await getDoctorPatients(sessionToken);
      setPatients(rows);
      setError(null);
    } catch (reason) {
      sessionStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setError(reason instanceof Error ? reason.message : "Could not load patients");
    }
  }, []);

  useEffect(() => {
    const existing = sessionStorage.getItem(TOKEN_KEY);
    getAuthStatus().then((status) => setNeedsSetup(status.needs_setup)).catch(() => {
      setError("The API is unavailable. Start the FastAPI server and try again.");
    });
    if (existing) {
      setToken(existing);
      loadPatients(existing);
    }
  }, [loadPatients]);

  async function authenticate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = needsSetup
        ? await setupDoctor(username, displayName, password)
        : await loginDoctor(username, password);
      sessionStorage.setItem(TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      setDoctorName(String(result.doctor.display_name));
      setNeedsSetup(false);
      setPassword("");
      await loadPatients(result.access_token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  async function selectPatient(patient: DoctorPatient) {
    if (!token || !patient.interview_id || !patient.completed) return;
    setSelected(patient);
    setSummary(null);
    setDraft(null);
    setTimeline([]);
    setFullInterview(null);
    setEditing(false);
    setBusy(true);
    setError(null);
    try {
      const [nextSummary, nextTimeline] = await Promise.all([
        getDoctorSummary(patient.patient.patient_id, patient.interview_id, token),
        getTimeline(patient.patient.patient_id, token),
      ]);
      setSummary(nextSummary);
      setDraft(editable(nextSummary));
      setTimeline(nextTimeline);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the clinical record");
    } finally {
      setBusy(false);
    }
  }

  function setList(field: keyof EditableClinicalSummary, value: string) {
    if (!draft) return;
    setDraft({ ...draft, [field]: value.split("\n").map((item) => item.trim()).filter(Boolean) });
  }

  async function save() {
    if (!token || !summary || !draft) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await saveDoctorSummary(summary.interview_id, draft, summary.version, token);
      setSummary(saved);
      setDraft(editable(saved));
      setEditing(false);
      await loadPatients(token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the summary");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!token || !summary) return;
    setBusy(true);
    setError(null);
    try {
      const approved = await approveDoctorSummary(
        summary.interview_id,
        summary.version,
        token,
      );
      setSummary(approved);
      setDraft(editable(approved));
      await loadPatients(token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not approve the summary");
    } finally {
      setBusy(false);
    }
  }

  async function showInterview() {
    if (!token || !summary) return;
    try {
      setFullInterview(await getFullInterview(summary.interview_id, token));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the interview");
    }
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setPatients([]);
    setSelected(null);
    setSummary(null);
  }

  if (!token) {
    return <main className="doctor-auth-shell">
      <section className="doctor-auth-card">
        <a className="doctor-brand" href="/"><span>+</span> MEDISAARTHI</a>
        <p className="eyebrow">PHYSICIAN ACCESS</p>
        <h1>{needsSetup ? "Create the first doctor account" : "Welcome back, doctor"}</h1>
        <p className="screen-help">{needsSetup
          ? "This one-time setup is stored securely in the clinical database."
          : "Sign in to review completed pre-consultation interviews."}</p>
        <form onSubmit={authenticate} className="doctor-auth-form">
          {needsSetup && <label className="field"><span>Display name</span><input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>}
          <label className="field"><span>Username</span><input required minLength={3} autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label className="field"><span>Password</span><input required minLength={8} type="password" autoComplete={needsSetup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <p className="error-banner">{error}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "Please wait…" : needsSetup ? "Create account" : "Sign in"}</button>
        </form>
      </section>
    </main>;
  }

  return <main className="doctor-shell">
    <header className="doctor-topbar">
      <a className="doctor-brand" href="/"><span>+</span> MEDISAARTHI <small>Clinical workspace</small></a>
      <div><strong>{doctorName || username}</strong><button onClick={logout}>Sign out</button></div>
    </header>
    <div className="doctor-grid">
      <aside className="patient-panel">
        <div className="panel-title"><div><p className="eyebrow">QUEUE</p><h2>Patients</h2></div><button onClick={() => token && loadPatients(token)}>↻</button></div>
        {!patients.length && <p className="empty-copy">No patient interviews yet.</p>}
        <div className="patient-list">{patients.map((row) =>
          <button key={row.patient.patient_id} className={selected?.patient.patient_id === row.patient.patient_id ? "patient-row active" : "patient-row"} onClick={() => selectPatient(row)} disabled={!row.completed}>
            <span className="avatar">{row.patient.name.slice(0, 1).toUpperCase()}</span>
            <span><strong>{row.patient.name}</strong><small>#{row.patient.patient_id} · {row.patient.age} {row.patient.gender.slice(0, 1).toUpperCase()}</small><em>{row.chief_complaint || (row.completed ? "No complaint captured" : "Interview in progress")}</em></span>
            <i className={`review-state ${row.summary_status || "pending"}`}>{row.summary_status || (row.completed ? "ready" : "active")}</i>
          </button>
        )}</div>
      </aside>
      <section className="clinical-workspace">
        {error && <p className="error-banner">{error}</p>}
        {!selected && <div className="doctor-empty"><span>+</span><h1>Select a patient</h1><p>Completed interviews will appear in the queue for physician verification.</p></div>}
        {selected && busy && !summary && <div className="doctor-empty"><div className="loader"/><p>Preparing the patient record…</p></div>}
        {summary && draft && <>
          <div className="clinical-header">
            <div><p className="eyebrow">PATIENT #{summary.patient_id}</p><h1>{summary.patient_snapshot.name}</h1><p>{summary.patient_snapshot.age} years · {summary.patient_snapshot.gender} · Interview {summary.interview_id}</p></div>
            <span className={`approval-badge ${summary.status}`}>{summary.status === "approved" ? "✓ Physician approved" : "Awaiting verification"}</span>
          </div>
          <div className="complaint-strip"><div><small>Current complaint</small><strong>{summary.current_complaint.name || "Not reported"}</strong></div><div><small>Duration</small><strong>{summary.current_complaint.duration || "Unknown"}</strong></div><div><small>Severity</small><strong>{summary.current_complaint.severity === null ? "Unknown" : `${summary.current_complaint.severity}/10`}</strong></div></div>
          {summary.priority_flags.length > 0 && <section className="priority-card"><strong>Priority review</strong><Lines values={summary.priority_flags}/></section>}
          {editing ? <section className="edit-sheet">
            <h2>Edit physician briefing</h2>
            <label><span>Interview summary</span><textarea rows={5} value={draft.interview_summary} onChange={(event) => setDraft({ ...draft, interview_summary: event.target.value })}/></label>
            <div className="edit-grid">
              {(["past_history", "medications", "allergies", "important_findings", "missing_information", "priority_flags"] as const).map((field) => <label key={field}><span>{field.replaceAll("_", " ")}</span><textarea rows={4} value={(draft[field] as string[]).join("\n")} onChange={(event) => setList(field, event.target.value)}/></label>)}
            </div>
            <div className="doctor-actions"><button className="secondary-button" onClick={() => { setDraft(editable(summary)); setEditing(false); }}>Cancel</button><button className="primary-button" onClick={save} disabled={busy}>Save changes</button></div>
          </section> : <>
            <section className="clinical-card wide"><p className="eyebrow">INTERVIEW SUMMARY</p><h2>Patient story, structured</h2><p className="summary-prose">{summary.interview_summary}</p></section>
            <div className="clinical-columns">
              <section className="clinical-card"><h3>Past medical history</h3><Lines values={summary.past_history}/></section>
              <section className="clinical-card"><h3>Current medications</h3><Lines values={summary.medications}/></section>
              <section className="clinical-card"><h3>Allergies</h3><Lines values={summary.allergies} empty="No allergies recorded"/></section>
              <section className="clinical-card"><h3>Important findings</h3><Lines values={summary.important_findings}/></section>
              <section className="clinical-card"><h3>Missing information</h3><Lines values={summary.missing_information} empty="No required fields missing"/></section>
            </div>
            <section className="clinical-card timeline-card"><h3>Clinical timeline</h3>{timeline.length ? <ol>{timeline.map((event, index) => <li key={`${event.date}-${index}`}><time>{event.date ? new Date(event.date).toLocaleDateString() : "Date unknown"}</time><div><strong>{event.title}</strong><p>{event.detail}</p><small>{event.source.replaceAll("_", " ")} · confidence {Math.round(event.confidence * 100)}%</small></div></li>)}</ol> : <p className="empty-copy">No prior timeline events.</p>}</section>
            <div className="doctor-actions"><button className="secondary-button" onClick={showInterview}>View full interview</button><button className="secondary-button" onClick={() => setEditing(true)}>Edit</button><button className="primary-button" onClick={approve} disabled={busy || summary.status === "approved"}>{summary.status === "approved" ? "Approved" : "Approve summary"}</button></div>
          </>}
          {fullInterview !== null && <div className="record-modal" role="dialog" aria-modal="true"><div><button className="modal-close" onClick={() => setFullInterview(null)}>×</button><p className="eyebrow">SOURCE RECORD</p><h2>Full interview</h2><pre>{JSON.stringify(fullInterview, null, 2)}</pre></div></div>}
        </>}
      </section>
    </div>
  </main>;
}
