"use client";

import { CSSProperties, FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, completeInterview, getInterview, getRuntimeStatus, startInterview, submitResponse } from "../lib/api";
import { Gender, InterviewResponse, Language, RuntimeStatus } from "../lib/contracts";

type FlowStep = "welcome" | "language" | "consent" | "identify" | "interview" | "complete";
type PatientInput = { patient_id: string; name: string; age: string; gender: Gender; language: Language };
type Turn = { speaker: "ai" | "patient"; text: string; field?: string };
type RecognitionResult = { 0: { transcript: string }; length: number };
type RecognitionEvent = { results: ArrayLike<RecognitionResult> };
type VoiceRecognition = {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
  onstart: (() => void) | null; onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: { error?: string }) => void) | null; onend: (() => void) | null;
  start: () => void; stop: () => void; abort: () => void;
};
type SpeechWindow = Window & { SpeechRecognition?: new () => VoiceRecognition; webkitSpeechRecognition?: new () => VoiceRecognition };

const steps: { id: FlowStep; en: string; hi: string }[] = [
  { id: "language", en: "Language", hi: "भाषा" }, { id: "consent", en: "Consent", hi: "सहमति" },
  { id: "identify", en: "Patient details", hi: "रोगी विवरण" }, { id: "interview", en: "Health interview", hi: "स्वास्थ्य बातचीत" },
  { id: "complete", en: "Review", hi: "समीक्षा" },
];
const defaultPatient: PatientInput = { patient_id: "", name: "", age: "", gender: "male", language: "en" };

const uiCopy: Record<Language, Record<string, string>> = {
  en: {
    eyebrow: "PRE-CONSULTATION INTAKE", title: "Tell your story. We’ll structure it for your doctor.",
    welcome: "A calm, guided health conversation before you meet the doctor. Speak naturally or type in your own words.",
    start: "Begin my interview", privacy: "Your answers prepare a briefing. They do not replace medical advice or your doctor.",
    languageTitle: "Which language feels easiest?", languageHelp: "Questions and voice recognition will use your selection.", continue: "Continue",
    consentTitle: "Your information, with your permission", consentBody: "We will collect your symptoms and health history and share the resulting summary with the treating doctor. The doctor will verify it before use.",
    consentLabel: "I understand and consent to this pre-consultation interview.", consentError: "Please provide consent before continuing.",
    detailsTitle: "Let’s find your patient record", detailsHelp: "Use the details provided at hospital registration.", patientId: "Patient ID", patientIdHint: "Example: P1001",
    name: "Full name", age: "Age", gender: "Gender", male: "Male", female: "Female", other: "Other", begin: "Start health interview",
    required: "Complete all patient details before continuing.", invalidAge: "Enter an age between 1 and 130.", interviewLabel: "AI HEALTH INTERVIEW",
    listenTitle: "Listen to the question", play: "Play question", stopAudio: "Stop audio", answerTitle: "Answer in your own words",
    answerHelp: "Speak naturally. You can edit the transcript before sending it.", placeholder: "For example: I have had chest pain for three days and it gets worse while walking...",
    micStart: "Start speaking", micStop: "Stop listening", listening: "Listening now", listeningHelp: "Speak clearly. Your words will appear below.",
    voiceReady: "Voice input ready", voiceUnavailable: "Voice input is unavailable in this browser. You can still type your answer.", autoRead: "Read each question aloud",
    send: "Send answer", sending: "Understanding your answer...", finish: "Finish interview", transcript: "Conversation so far", patient: "You", assistant: "Medisaarthi",
    responseRequired: "Speak or type an answer before sending.", tooLong: "Keep the response under 4,000 characters.", serviceError: "The interview service is unavailable. Confirm the backend is running.",
    voiceDenied: "Microphone access was blocked. Allow microphone permission in your browser, then try again.", voiceNoSpeech: "No speech was detected. Move closer to the microphone and try again.",
    voiceFailed: "Voice capture stopped unexpectedly. You can retry or type instead.", conflict: "The interview changed in another request. Your answer was not sent; review it and send again.",
    completeTitle: "Your briefing is ready for review", completeHelp: "This is the information captured from your answers. Your doctor will verify it.",
    captured: "Captured information", important: "Important for staff", missing: "Still missing", unknown: "Skipped or unknown", none: "None", newPatient: "Start another patient",
    demoTitle: "Guided demo engine", demoHelp: "This mode understands a limited set of example phrases. Enable Gemini for natural answers.", liveTitle: "Gemini AI", liveHelp: "Gemini natural-language extraction is active.", offlineTitle: "Backend offline",
  },
  hi: {
    eyebrow: "प्री-कंसल्टेशन जानकारी", title: "अपनी बात सहजता से बताइए। हम डॉक्टर के लिए इसे व्यवस्थित करेंगे।",
    welcome: "डॉक्टर से मिलने से पहले एक आसान स्वास्थ्य बातचीत। अपनी भाषा में बोलें या लिखें।", start: "बातचीत शुरू करें",
    privacy: "आपके उत्तर डॉक्टर के लिए जानकारी तैयार करते हैं। यह चिकित्सकीय सलाह नहीं है।", languageTitle: "आप किस भाषा में सहज हैं?",
    languageHelp: "सवाल और आवाज़ की पहचान चुनी गई भाषा में होगी।", continue: "आगे बढ़ें", consentTitle: "आपकी अनुमति से आपकी जानकारी",
    consentBody: "हम आपके लक्षण और स्वास्थ्य इतिहास एकत्र करेंगे और डॉक्टर के साथ सारांश साझा करेंगे। डॉक्टर उपयोग से पहले इसकी पुष्टि करेंगे।",
    consentLabel: "मैं इस प्री-कंसल्टेशन बातचीत को समझता/समझती हूँ और सहमति देता/देती हूँ।", consentError: "आगे बढ़ने से पहले सहमति दें।",
    detailsTitle: "अपना रोगी रिकॉर्ड खोजें", detailsHelp: "अस्पताल पंजीकरण में दिए गए विवरण भरें।", patientId: "रोगी ID", patientIdHint: "उदाहरण: P1001",
    name: "पूरा नाम", age: "उम्र", gender: "लिंग", male: "पुरुष", female: "महिला", other: "अन्य", begin: "स्वास्थ्य बातचीत शुरू करें",
    required: "आगे बढ़ने से पहले सभी रोगी विवरण भरें।", invalidAge: "1 से 130 के बीच सही उम्र भरें।", interviewLabel: "AI स्वास्थ्य बातचीत",
    listenTitle: "सवाल सुनें", play: "सवाल चलाएँ", stopAudio: "आवाज़ रोकें", answerTitle: "अपने शब्दों में जवाब दें",
    answerHelp: "स्वाभाविक रूप से बोलें। भेजने से पहले लिखे हुए शब्द सुधार सकते हैं।", placeholder: "उदाहरण: मेरे सीने में तीन दिन से दर्द है और चलते समय बढ़ जाता है...",
    micStart: "बोलना शुरू करें", micStop: "सुनना रोकें", listening: "अभी सुन रहा है", listeningHelp: "साफ़ बोलें। आपके शब्द नीचे दिखाई देंगे।",
    voiceReady: "आवाज़ से जवाब तैयार", voiceUnavailable: "इस ब्राउज़र में आवाज़ से लिखना उपलब्ध नहीं है। आप जवाब टाइप कर सकते हैं।", autoRead: "हर सवाल बोलकर सुनाएँ",
    send: "जवाब भेजें", sending: "आपका जवाब समझ रहा है...", finish: "बातचीत पूरी करें", transcript: "अब तक की बातचीत", patient: "आप", assistant: "मेडिसारथी",
    responseRequired: "भेजने से पहले बोलें या जवाब लिखें।", tooLong: "जवाब 4,000 अक्षरों से छोटा रखें।", serviceError: "इंटरव्यू सर्विस उपलब्ध नहीं है। जाँचें कि बैकएंड चालू है।",
    voiceDenied: "माइक्रोफ़ोन की अनुमति नहीं मिली। ब्राउज़र में अनुमति दें और फिर कोशिश करें।", voiceNoSpeech: "कोई आवाज़ नहीं मिली। माइक्रोफ़ोन के पास बोलकर फिर कोशिश करें।",
    voiceFailed: "आवाज़ रिकॉर्ड करना रुक गया। दोबारा कोशिश करें या टाइप करें।", conflict: "इंटरव्यू किसी दूसरी रिक्वेस्ट में बदल गया। आपका जवाब नहीं भेजा गया; जाँचकर दोबारा भेजें।",
    completeTitle: "आपकी जानकारी समीक्षा के लिए तैयार है", completeHelp: "यह आपके जवाबों से मिली जानकारी है। डॉक्टर इसकी पुष्टि करेंगे।",
    captured: "मिली हुई जानकारी", important: "स्टाफ के लिए महत्वपूर्ण", missing: "अभी बाकी", unknown: "छोड़ी गई या अज्ञात", none: "कोई नहीं", newPatient: "दूसरा रोगी शुरू करें",
    demoTitle: "सीमित डेमो इंजन", demoHelp: "यह मोड कुछ उदाहरण वाक्य ही समझता है। सामान्य बातचीत के लिए Gemini चालू करें।", liveTitle: "Gemini AI", liveHelp: "Gemini सामान्य भाषा समझ रहा है।", offlineTitle: "बैकएंड बंद है",
  },
};

function Icon({ children, size = 24 }: { children: ReactNode; size?: number }) { return <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{children}</svg>; }
const MicIcon = () => <Icon size={30}><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></Icon>;
const SoundIcon = () => <Icon><path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12"/></Icon>;
const ArrowIcon = () => <Icon><path d="m9 18 6-6-6-6"/></Icon>;
const ShieldIcon = () => <Icon><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></Icon>;
const humanize = (field: string) => field.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
function displayValue(value: unknown, language: Language) { if (Array.isArray(value)) return value.length ? value.join(", ") : language === "hi" ? "कोई नहीं" : "None reported"; if (typeof value === "boolean") return value ? language === "hi" ? "हाँ" : "Yes" : language === "hi" ? "नहीं" : "No"; return String(value); }

export default function PatientInterview() {
  const [step, setStep] = useState<FlowStep>("welcome"); const [language, setLanguage] = useState<Language>("en");
  const [consent, setConsent] = useState(false); const [patient, setPatient] = useState<PatientInput>(defaultPatient);
  const [interview, setInterview] = useState<InterviewResponse | null>(null); const [turns, setTurns] = useState<Turn[]>([]);
  const [responseText, setResponseText] = useState(""); const [error, setError] = useState<string | null>(null); const [isBusy, setIsBusy] = useState(false);
  const [isRecording, setIsRecording] = useState(false); const [voiceSupported, setVoiceSupported] = useState(false); const [audioSupported, setAudioSupported] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false); const [autoRead, setAutoRead] = useState(true); const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [backendReachable, setBackendReachable] = useState<boolean | null>(null); const recognitionRef = useRef<VoiceRecognition | null>(null); const voicePrefixRef = useRef("");
  const copy = uiCopy[language]; const question = interview?.next_question; const activeIndex = step === "welcome" ? -1 : steps.findIndex((item) => item.id === step);
  const progress = useMemo(() => { if (!interview) return 0; if (interview.completed) return 100; const answered = new Set(turns.filter((turn) => turn.speaker === "ai" && turn.field).map((turn) => turn.field)).size; const total = answered + interview.missing_information.length; return total ? Math.max(8, Math.round(answered / total * 100)) : 8; }, [interview, turns]);

  useEffect(() => {
    getRuntimeStatus().then((status) => { setRuntime(status); setBackendReachable(true); }).catch(() => setBackendReachable(false));
    if (typeof window === "undefined") return; const speechWindow = window as SpeechWindow;
    setVoiceSupported(Boolean(speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition)); setAudioSupported("speechSynthesis" in window);
    return () => { recognitionRef.current?.abort(); window.speechSynthesis?.cancel(); };
  }, []);

  const readQuestion = (text = question?.text) => { if (!text || !audioSupported || typeof window === "undefined") return; window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = language === "hi" ? "hi-IN" : "en-IN"; utterance.rate = .92; utterance.onstart = () => setIsSpeaking(true); utterance.onend = () => setIsSpeaking(false); utterance.onerror = () => setIsSpeaking(false); window.speechSynthesis.speak(utterance); };
  useEffect(() => { if (autoRead && question?.text && audioSupported) readQuestion(question.text); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [question?.text]);
  const stopAudio = () => { window.speechSynthesis?.cancel(); setIsSpeaking(false); };
  const startListening = () => {
    if (!voiceSupported || typeof window === "undefined") return; const speechWindow = window as SpeechWindow; const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition; if (!Recognition) return;
    stopAudio(); setError(null); voicePrefixRef.current = responseText.trim(); const recognition = new Recognition(); recognition.lang = language === "hi" ? "hi-IN" : "en-IN"; recognition.continuous = true; recognition.interimResults = true; recognition.maxAlternatives = 1;
    recognition.onstart = () => setIsRecording(true); recognition.onresult = (event) => { const spoken: string[] = []; for (let i = 0; i < event.results.length; i += 1) { const result = event.results[i]; if (result?.length) spoken.push(result[0].transcript); } setResponseText([voicePrefixRef.current, spoken.join(" ")].filter(Boolean).join(" ").trim()); };
    recognition.onerror = (event) => { setError(event.error === "not-allowed" || event.error === "service-not-allowed" ? copy.voiceDenied : event.error === "no-speech" ? copy.voiceNoSpeech : copy.voiceFailed); setIsRecording(false); };
    recognition.onend = () => { setIsRecording(false); recognitionRef.current = null; }; recognitionRef.current = recognition;
    try { recognition.start(); } catch { setError(copy.voiceFailed); setIsRecording(false); }
  };
  const stopListening = () => recognitionRef.current?.stop();
  const changeLanguage = (value: Language) => { setLanguage(value); setPatient((current) => ({ ...current, language: value })); setError(null); };
  const startSession = async (event: FormEvent) => {
    event.preventDefault(); if (!patient.patient_id.trim() || !patient.name.trim() || !patient.age || !patient.gender) { setError(copy.required); return; }
    const age = Number(patient.age); if (!Number.isInteger(age) || age < 1 || age > 130) { setError(copy.invalidAge); return; }
    setIsBusy(true); setError(null); try { const started = await startInterview({ ...patient, patient_id: patient.patient_id.trim(), name: patient.name.trim(), age }, true); setInterview(started); setBackendReachable(true); setTurns(started.next_question ? [{ speaker: "ai", text: started.next_question.text, field: started.next_question.id }] : []); setStep(started.completed ? "complete" : "interview"); } catch (caught) { setBackendReachable(false); setError((caught as Error).message || copy.serviceError); } finally { setIsBusy(false); }
  };
  const sendResponse = async (event: FormEvent) => {
    event.preventDefault(); if (!interview || !question) return; const answer = responseText.trim(); if (!answer) { setError(copy.responseRequired); return; } if (answer.length > 4000) { setError(copy.tooLong); return; }
    stopListening(); setIsBusy(true); setError(null); setTurns((current) => [...current, { speaker: "patient", text: answer }]);
    try { const next = await submitResponse({ interview_id: interview.interview_id, response: answer, expected_revision: interview.revision }); setInterview(next); setResponseText(""); const nextQuestion = next.next_question; if (nextQuestion) setTurns((current) => [...current, { speaker: "ai", text: nextQuestion.text, field: nextQuestion.id }]); if (next.completed) setStep("complete"); }
    catch (caught) { setTurns((current) => current.slice(0, -1)); if (caught instanceof ApiError && caught.status === 409) { try { setInterview(await getInterview(interview.interview_id)); setError(copy.conflict); } catch (refreshError) { setError((refreshError as Error).message || copy.serviceError); } } else setError((caught as Error).message || copy.serviceError); } finally { setIsBusy(false); }
  };
  const finish = async () => { if (!interview || interview.completed) { setStep("complete"); return; } stopListening(); stopAudio(); setIsBusy(true); setError(null); try { const done = await completeInterview({ interview_id: interview.interview_id, expected_revision: interview.revision }); setInterview(done); setStep("complete"); } catch (caught) { setError((caught as Error).message || copy.serviceError); } finally { setIsBusy(false); } };
  const reset = () => { stopListening(); stopAudio(); setStep("welcome"); setConsent(false); setPatient({ ...defaultPatient, language }); setInterview(null); setTurns([]); setResponseText(""); setError(null); };
  const rows = Object.entries(interview?.clinical_state || {}).filter(([, value]) => value !== null && value !== "");
  const runtimeLabel = backendReachable === false ? copy.offlineTitle : runtime?.extraction_mode === "gemini" ? copy.liveTitle : copy.demoTitle;

  return <main className="app-shell">
    <header className="topbar"><button className="brand" onClick={reset} aria-label="Medisaarthi home"><span className="brand-mark">M</span><span>MEDISAARTHI<small>Patient intake</small></span></button><div className="portal-links"><a href="/doctor">Doctor portal</a><div className={`runtime-pill ${backendReachable === false ? "offline" : runtime?.extraction_mode === "gemini" ? "live" : "demo"}`}><span className="status-dot" />{runtimeLabel}</div></div></header>
    <div className="workspace">
      <aside className="step-rail" aria-label="Interview progress"><p className="rail-kicker">YOUR VISIT</p><ol>{steps.map((item, index) => <li key={item.id} className={index < activeIndex || step === "complete" ? "done" : index === activeIndex ? "active" : ""}><span>{index < activeIndex || step === "complete" ? "✓" : index + 1}</span>{language === "hi" ? item.hi : item.en}</li>)}</ol><div className="privacy-note"><ShieldIcon /><p>{copy.privacy}</p></div></aside>
      <section className="stage" aria-live="polite">
        {step === "welcome" && <div className="welcome-screen reveal"><p className="eyebrow">{copy.eyebrow}</p><h1>{copy.title}</h1><p className="lead">{copy.welcome}</p><div className="welcome-actions"><button className="primary-button" onClick={() => setStep("language")}>{copy.start}<ArrowIcon /></button><div className="mode-card"><span className="status-dot" /><div><strong>{runtimeLabel}</strong><p>{runtime?.extraction_mode === "gemini" ? copy.liveHelp : copy.demoHelp}</p></div></div></div><div className="voice-preview"><span><MicIcon /></span><p><strong>Speak</strong><small>Use your natural words</small></p><i/><span className="structure-icon">01<br/>02<br/>03</span><p><strong>Structure</strong><small>Key details are organized</small></p><i/><span className="doctor-icon">+</span><p><strong>Review</strong><small>Your doctor verifies</small></p></div></div>}
        {step === "language" && <div className="form-screen reveal"><p className="eyebrow">01 · LANGUAGE</p><h2>{copy.languageTitle}</h2><p className="screen-help">{copy.languageHelp}</p><div className="language-grid"><button className={language === "hi" ? "language-choice selected" : "language-choice"} onClick={() => changeLanguage("hi")}><span>अ</span><strong>हिन्दी</strong><small>Hindi</small></button><button className={language === "en" ? "language-choice selected" : "language-choice"} onClick={() => changeLanguage("en")}><span>A</span><strong>English</strong><small>English</small></button></div><button className="primary-button align-right" onClick={() => setStep("consent")}>{copy.continue}<ArrowIcon /></button></div>}
        {step === "consent" && <div className="form-screen reveal"><p className="eyebrow">02 · CONSENT</p><h2>{copy.consentTitle}</h2><div className="consent-panel"><ShieldIcon/><p>{copy.consentBody}</p></div><label className="consent-check"><input type="checkbox" checked={consent} onChange={(event) => { setConsent(event.target.checked); setError(null); }}/><span className="fake-check">✓</span><span>{copy.consentLabel}</span></label>{error && <p className="error-banner" role="alert">{error}</p>}<button className="primary-button align-right" onClick={() => { if (!consent) setError(copy.consentError); else { setError(null); setStep("identify"); } }}>{copy.continue}<ArrowIcon/></button></div>}
        {step === "identify" && <form className="form-screen reveal" onSubmit={startSession}><p className="eyebrow">03 · PATIENT</p><h2>{copy.detailsTitle}</h2><p className="screen-help">{copy.detailsHelp}</p><div className="field-grid"><label className="field full"><span>{copy.patientId}</span><input autoFocus value={patient.patient_id} placeholder={copy.patientIdHint} onChange={(event) => setPatient((current) => ({ ...current, patient_id: event.target.value }))}/></label><label className="field full"><span>{copy.name}</span><input value={patient.name} autoComplete="name" onChange={(event) => setPatient((current) => ({ ...current, name: event.target.value }))}/></label><label className="field"><span>{copy.age}</span><input value={patient.age} inputMode="numeric" onChange={(event) => setPatient((current) => ({ ...current, age: event.target.value.replace(/\D/g, "") }))}/></label><label className="field"><span>{copy.gender}</span><select value={patient.gender} onChange={(event) => setPatient((current) => ({ ...current, gender: event.target.value as Gender }))}><option value="male">{copy.male}</option><option value="female">{copy.female}</option><option value="other">{copy.other}</option></select></label></div>{error && <p className="error-banner" role="alert">{error}</p>}<button className="primary-button align-right" disabled={isBusy}>{isBusy ? copy.sending : copy.begin}<ArrowIcon/></button></form>}
        {step === "interview" && interview && <div className="interview-screen reveal"><div className="interview-head"><div><p className="eyebrow">{copy.interviewLabel}</p><p className="patient-line">{patient.name}<span>#{patient.patient_id}</span></p></div><div className="progress-ring" style={{ "--progress": `${progress * 3.6}deg` } as CSSProperties}><span>{progress}%</span></div></div>{runtime?.extraction_mode !== "gemini" && <div className="demo-warning"><span className="status-dot"/><p><strong>{copy.demoTitle}</strong>{copy.demoHelp}</p></div>}{question && <article className="question-card"><p>{copy.listenTitle}</p><h2>{question.text}</h2><div className="audio-row"><button className="audio-button" type="button" onClick={() => isSpeaking ? stopAudio() : readQuestion()} disabled={!audioSupported}><SoundIcon/>{isSpeaking ? copy.stopAudio : copy.play}</button><label className="toggle"><input type="checkbox" checked={autoRead} onChange={(event) => setAutoRead(event.target.checked)}/><span/>{copy.autoRead}</label></div></article>}<form className="answer-card" onSubmit={sendResponse}><div className="answer-heading"><div><h3>{copy.answerTitle}</h3><p>{copy.answerHelp}</p></div><span className={voiceSupported ? "capability ready" : "capability"}>{voiceSupported ? copy.voiceReady : copy.voiceUnavailable}</span></div><div className={isRecording ? "voice-control recording" : "voice-control"}><button type="button" className="mic-button" onClick={isRecording ? stopListening : startListening} disabled={!voiceSupported || isBusy} aria-label={isRecording ? copy.micStop : copy.micStart}><MicIcon/></button><div><strong>{isRecording ? copy.listening : copy.micStart}</strong><small>{isRecording ? copy.listeningHelp : voiceSupported ? copy.voiceReady : copy.voiceUnavailable}</small></div><div className="wave" aria-hidden="true">{[1,2,3,4,5,6,7].map((bar) => <i key={bar}/>)}</div></div><label className="transcript-box"><span>{copy.patient}</span><textarea value={responseText} onChange={(event) => setResponseText(event.target.value)} placeholder={copy.placeholder} rows={4} maxLength={4000}/><small>{responseText.length}/4000</small></label>{error && <p className="error-banner" role="alert">{error}</p>}<div className="answer-actions"><button type="button" className="text-button" onClick={finish} disabled={isBusy}>{copy.finish}</button><button className="primary-button compact" disabled={isBusy || !question}>{isBusy ? copy.sending : copy.send}<ArrowIcon/></button></div></form><details className="conversation"><summary>{copy.transcript}<span>{turns.length}</span></summary>{turns.map((turn, index) => <div key={`${turn.speaker}-${index}`} className={`turn ${turn.speaker}`}><strong>{turn.speaker === "ai" ? copy.assistant : copy.patient}</strong><p>{turn.text}</p></div>)}</details></div>}
        {step === "complete" && interview && <div className="complete-screen reveal"><div className="complete-mark">✓</div><p className="eyebrow">INTERVIEW COMPLETE</p><h2>{copy.completeTitle}</h2><p className="screen-help">{copy.completeHelp}</p><section className="summary-card"><h3>{copy.captured}</h3>{rows.length ? <dl>{rows.map(([field, value]) => <div key={field}><dt>{humanize(field)}</dt><dd>{displayValue(value, language)}</dd></div>)}</dl> : <p>{copy.none}</p>}</section><div className="summary-grid"><section className={interview.priority_flags.length ? "mini-summary alert" : "mini-summary"}><h3>{copy.important}</h3>{interview.priority_flags.length ? interview.priority_flags.map((flag) => <p key={flag.code}>{flag.message}</p>) : <p>{copy.none}</p>}</section><section className="mini-summary"><h3>{copy.missing}</h3><p>{interview.missing_information.length ? interview.missing_information.map(humanize).join(", ") : copy.none}</p></section><section className="mini-summary"><h3>{copy.unknown}</h3><p>{interview.unknown_information.length ? interview.unknown_information.map(humanize).join(", ") : copy.none}</p></section></div><button className="secondary-button align-right" onClick={reset}>{copy.newPatient}</button></div>}
      </section>
    </div>
  </main>;
}
