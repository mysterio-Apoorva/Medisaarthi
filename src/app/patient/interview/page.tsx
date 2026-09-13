'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Patient,
  Language,
  InterviewMessage,
  ExtractedFactItem,
  ExtractedSymptomData,
} from '@/types';
import {
  startInterviewSession,
  respondToInterviewSession,
  transcribeInterviewAudio,
  getIntakeSnapshot,
  getPatient,
  type CareMode,
} from '@/services/api';
import { PatientHeader } from '@/components/patient/PatientHeader';
import { InterviewProgress } from '@/components/patient/InterviewProgress';
import { ExtractedInfo } from '@/components/patient/ExtractedInfo';
import { TalkingAvatar } from '@/components/patient/TalkingAvatar';
import { useAssistantSpeech } from '@/components/patient/useAssistantSpeech';
import { Button } from '@/components/ui/Button';
import {
  Send,
  Bot,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  HelpCircle,
  Mic,
  MicOff,
  Square,
  Volume2,
  VolumeX,
} from 'lucide-react';

export default function PatientInterviewPage() {
  const router = useRouter();

  // Core State
  const [patient, setPatient] = useState<Patient | null>(null);
  const [language, setLanguage] = useState<Language>('hi');
  const [careMode, setCareMode] = useState<CareMode>('MODERN');
  const [interviewId, setInterviewId] = useState<string>('');
  const [currentQuestion, setCurrentQuestion] = useState<string>('');
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isInitializing, setIsInitializing] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [interviewCompleted, setInterviewCompleted] = useState<boolean>(false);
  const [questionCount, setQuestionCount] = useState<number>(1);
  const [revision, setRevision] = useState<number>(0);

  // Voice Interaction State (Step 4C) - Speaking and listening by default
  const [voiceMode, setVoiceMode] = useState<boolean>(true);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isProcessingVoice, setIsProcessingVoice] = useState<boolean>(false);
  const speech = useAssistantSpeech();
  const isSpeaking = speech.speaking;
  const [completionPercentage, setCompletionPercentage] = useState(0);
  const [safetyFlags, setSafetyFlags] = useState<{ code: string; message: string }[]>([]);
  const [aiWarning, setAiWarning] = useState<string | null>(null);
  const [isRequestingMic, setIsRequestingMic] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [lastTranscript, setLastTranscript] = useState<string | null>(null);

  // Extracted structured facts from backend
  const [extractedData, setExtractedData] = useState<ExtractedSymptomData>({
    chief_complaint: '',
    duration: '',
    severity: '',
    associated_symptoms: [],
  });

  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isRecordingRef = useRef<boolean>(false);
  const streamRef = useRef<MediaStream | null>(null);
  const mountedRef = useRef(true);
  const requestingMicRef = useRef(false);
  const initializingRef = useRef(false);
  const uploadRef = useRef<AbortController | null>(null);
  const submitRef = useRef(false);

  const isHindi = language === 'hi';

  const speakQuestion = (text: string, locale = language) => {
    if (!isRecordingRef.current && !requestingMicRef.current) void speech.speak(text, locale);
  };
  const stopSpeaking = speech.stop;

  // 2. Initialize Interview with Backend
  const initializeInterview = async () => {
    if (initializingRef.current || isRecordingRef.current || requestingMicRef.current) return;
    initializingRef.current = true;
    setIsInitializing(true);
    setErrorMessage(null);

    let currentId = '';
    let currentLang: Language = 'hi';
    let currentCareMode: CareMode = 'MODERN';

    try {
      const storedId = localStorage.getItem('medisaarthi_current_patient_id');
      const storedLang = localStorage.getItem('medisaarthi_selected_lang');
      if (storedId) currentId = storedId;
      if (storedLang === 'en' || storedLang === 'hi') currentLang = storedLang;
      const storedMode = localStorage.getItem('medisaarthi_care_mode');
      if (storedMode === 'MODERN' || storedMode === 'AYUSH') currentCareMode = storedMode;
    } catch {}

    setLanguage(currentLang);
    setCareMode(currentCareMode);

    try {
      if (!currentId) { router.replace('/patient/identify'); return; }
      const p = await getPatient(currentId);
      if (!p) throw new Error('Your patient record could not be found. Please sign in again.');
      setPatient(p);

      const consentId = localStorage.getItem('medisaarthi_current_consent_id');
      if (!consentId) {
        router.replace('/patient/consent');
        return;
      }
      const startRes = await startInterviewSession(p.patient_id, currentLang, consentId, currentCareMode);
      setInterviewId(startRes.interview_id);
      setRevision(startRes.revision);

      try {
        localStorage.setItem('medisaarthi_current_interview_id', startRes.interview_id);
      } catch {}

      const snapshot = await getIntakeSnapshot(startRes.interview_id);
      const initialQ = snapshot.next_question?.text || '';
      setLanguage(snapshot.language);
      setRevision(snapshot.revision);
      setCompletionPercentage(snapshot.completion.completion_percentage);
      setSafetyFlags(snapshot.priority_flags);
      setQuestionCount(snapshot.answers.length + 1);
      setInterviewCompleted(snapshot.status !== 'ACTIVE');
      setExtractedData({ chief_complaint: String(snapshot.clinical_state.chief_complaint || ''), duration: String(snapshot.clinical_state.duration || ''), severity: String(snapshot.clinical_state.severity ?? ''), location: String(snapshot.clinical_state.location || ''), associated_symptoms: Object.entries(snapshot.clinical_state).filter(([,value]) => value === true).map(([field]) => field.replaceAll('_',' ')) });

      setCurrentQuestion(initialQ);

      const initialMsg: InterviewMessage = {
        id: `msg-${Date.now()}`,
        sender: 'ai',
        text: initialQ,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages([...snapshot.answers.flatMap(answer => ([
        { id: `${answer.answer_id}-question`, sender: 'ai' as const, text: answer.question_text, timestamp: answer.created_at },
        { id: answer.answer_id, sender: 'patient' as const, text: answer.answer_text, timestamp: answer.created_at },
      ])), ...(initialQ ? [initialMsg] : [])]);
      setIsInitializing(false);

      // Auto-speak initial question: speaking and listening is the default!
      // Audio starts only after an explicit Listen gesture; browser autoplay is not assumed.
    } catch (err: any) {
      setIsInitializing(false);
      setErrorMessage(
        isHindi
          ? 'सर्वर से कनेक्ट करने में असमर्थ। कृपया जांचें कि बैकएंड चालू है और पुनः प्रयास करें।'
          : 'Unable to connect to the Medisaarthi server. Please ensure the backend is running and try again.'
      );
    } finally { initializingRef.current = false; setIsInitializing(false); }
  };

  useEffect(() => {
    initializeInterview();
  }, []);

  // Cleanup timers, microphone streams, and speech synthesis on unmount.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      uploadRef.current?.abort();
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current.ondataavailable = null;
        if (mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop();
      }
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (streamRef.current) {
        try {
          streamRef.current.getTracks().forEach((t) => t.stop());
        } catch {}
      }
      stopSpeaking();
    };
  }, []);

  // Focus input whenever question changes
  useEffect(() => {
    if (!isInitializing && !isSubmitting && !isProcessingVoice && !interviewCompleted) {
      inputRef.current?.focus();
    }
  }, [currentQuestion, isInitializing, isSubmitting, isProcessingVoice, interviewCompleted]);

  // Helper to sync extracted facts from backend into ExtractedSymptomData UI state
  const updateExtractedFromFacts = (facts: ExtractedFactItem[]) => {
    setExtractedData((prev) => {
      const next = { ...prev };
      for (const f of facts) {
        if (f.field_name === 'chief_complaint') next.chief_complaint = f.value;
        else if (f.field_name === 'duration') next.duration = f.value;
        else if (f.field_name === 'severity') next.severity = f.value;
        else if (f.field_name === 'location') next.location = f.value;
        else if (f.field_name === 'associated_symptoms') {
          if (!next.associated_symptoms.includes(f.value)) {
            next.associated_symptoms = [...next.associated_symptoms, f.value];
          }
        }
      }
      return next;
    });
  };

  // 3. Submit Patient Text Answer to Backend
  const handleSendResponse = async (textToSend?: string) => {
    const message = (textToSend !== undefined ? textToSend : inputText).trim();
    if (!message || submitRef.current || isSubmitting || isProcessingVoice || isRecordingRef.current || requestingMicRef.current || !interviewId || interviewCompleted) return;
    submitRef.current = true;

    stopSpeaking();
    setIsSubmitting(true);
    setErrorMessage(null);

    // Append patient message to transcript
    const patientMsg: InterviewMessage = {
      id: `pat-${Date.now()}`,
      sender: 'patient',
      text: message,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    const updatedMessages = [...messages, patientMsg];

    try {
      // Call Backend POST /interview/respond
      const respondRes = await respondToInterviewSession(interviewId, message, revision);
      setRevision(respondRes.revision);
      setInputText('');
      setLastTranscript(null);
      setCompletionPercentage(respondRes.completion?.completion_percentage || 0);
      setAiWarning(respondRes.ai_warning || null);
      const snapshot = await getIntakeSnapshot(interviewId);
      setSafetyFlags(snapshot.priority_flags);

      if (respondRes.extracted_facts && respondRes.extracted_facts.length > 0) {
        updateExtractedFromFacts(respondRes.extracted_facts);
      }

      const nextQText = respondRes.next_question?.text || '';
      setCurrentQuestion(nextQText);
      setQuestionCount((c) => c + 1);

      const aiReplyMsg: InterviewMessage = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: nextQText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages([...updatedMessages, aiReplyMsg]);

      if (voiceMode && nextQText) {
        speakQuestion(nextQText);
      }

      // If backend reports completion
      if (respondRes.interview_completed || respondRes.status === 'PATIENT_REVIEW') {
        setInterviewCompleted(true);
      }
      setIsSubmitting(false);
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMessage(
        isHindi
          ? 'उत्तर भेजने में समस्या आई। कृपया पुनः प्रयास करें।'
          : 'Could not send response. Please try again.'
      );
    } finally { submitRef.current = false; setIsSubmitting(false); }
  };

  // Voice is recorded in the browser and transcribed by the authenticated local-STT API.
  const handleStartRecording = async () => {
    if (requestingMicRef.current || isRecordingRef.current || isRecording || isProcessingVoice || isSubmitting || interviewCompleted || inputText.trim()) return;
    requestingMicRef.current = true;
    setIsRequestingMic(true);

    stopSpeaking();
    setErrorMessage(null);
    audioChunksRef.current = [];

    // Capture microphone audio. The server is the sole source of the saved transcript.
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
        setErrorMessage(
          isHindi
            ? 'माइक्रोफ़ोन एक्सेस की अनुमति नहीं दी गई। आप लिखकर उत्तर दे सकते हैं।'
            : 'Microphone access was not allowed. You can type your answer instead.'
        );
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current) { stream.getTracks().forEach(track => track.stop()); return; }
      streamRef.current = stream;
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
        .find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        isRecordingRef.current = false;
        if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
        // Stop stream tracks
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        if (!mountedRef.current) return;
        setIsRecording(false);

        const actualMimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: actualMimeType });
        if (audioBlob.size > 0) {
          await handleSendVoiceAudio(audioBlob, actualMimeType);
        } else {
          setErrorMessage(isHindi ? 'रिकॉर्डिंग खाली है। कृपया फिर से बोलें।' : 'The recording was empty. Please record your answer again.');
          setIsProcessingVoice(false);
        }
      };
      mediaRecorder.onerror = () => {
        mediaRecorder.onstop = null;
        stream.getTracks().forEach(track => track.stop());
        isRecordingRef.current = false;
        if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
        setIsRecording(false); setIsProcessingVoice(false);
        setErrorMessage(isHindi ? 'रिकॉर्डिंग विफल हुई। फिर प्रयास करें या लिखें।' : 'Recording failed. Please retry or type your answer.');
      };

      isRecordingRef.current = true;
      mediaRecorder.start(250); // Slice data every 250ms
      setIsRecording(true);
      setRecordingSeconds(0);

      // Start duration counter
      const recordingStarted = Date.now();
      timerIntervalRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - recordingStarted) / 1000);
        setRecordingSeconds(elapsed);
        if (elapsed >= 110) handleStopRecording();
      }, 1000);
    } catch (err: any) {
      streamRef.current?.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      isRecordingRef.current = false;
      setIsRecording(false);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      setErrorMessage(
        isHindi
          ? 'माइक्रोफ़ोन एक्सेस की अनुमति नहीं दी गई। आप लिखकर उत्तर दे सकते हैं।'
          : err?.name === 'NotFoundError' ? 'No microphone was found. Connect one or type your answer.' : err?.name === 'NotReadableError' ? 'The microphone is busy or unavailable. Close other recording apps and retry.' : 'Microphone access was not allowed. Allow it in your browser settings or type your answer.'
      );
    } finally { requestingMicRef.current = false; if (mountedRef.current) setIsRequestingMic(false); }
  };

  const handleStopRecording = () => {
    if (!isRecordingRef.current && !isRecording) return;

    isRecordingRef.current = false;
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    setIsRecording(false);
    setIsProcessingVoice(true);

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    } else {
      setErrorMessage(isHindi ? 'रिकॉर्डिंग उपलब्ध नहीं है। कृपया फिर से प्रयास करें।' : 'The microphone recording is unavailable. Please record your answer again.');
      setIsProcessingVoice(false);
    }
  };

  // Upload microphone audio to the local transcription endpoint.
  const handleSendVoiceAudio = async (
    audioBlob: Blob,
    mimeType: string,
  ) => {
    if (!interviewId || interviewCompleted) return;

    setIsProcessingVoice(true);
    setErrorMessage(null);

    try {
      const controller = new AbortController();
      uploadRef.current = controller;
      const voiceRes = await transcribeInterviewAudio(
        interviewId,
        audioBlob,
        `patient_voice.${mimeType.includes('webm') ? 'webm' : mimeType.includes('ogg') ? 'ogg' : mimeType.includes('mp4') ? 'm4a' : 'wav'}`,
        revision, controller.signal
      );
      if (!mountedRef.current) return;
      const transcript = voiceRes.transcript;
      setLastTranscript(transcript);
      setInputText(transcript);
      inputRef.current?.focus();
      setIsProcessingVoice(false);
    } catch (err: any) {
      if (!mountedRef.current) return;
      setIsProcessingVoice(false);
      setErrorMessage(
        err?.message ||
          (isHindi
            ? 'आवाज़ पहचानने में समस्या आई। कृपया पुनः बोलें या लिखकर उत्तर दें।'
            : 'Could not process voice recording. Please speak clearly or type your answer.')
      );
    }
  };

  // 6. Complete Interview & Navigate to Screen 6
  const handleFinishInterview = async () => {
    stopSpeaking();
    router.push('/patient/review');
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-between text-slate-900">
      <PatientHeader currentStep={4} totalSteps={4} stepName="Interview" />

      <main className="flex-1 max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8 w-full flex flex-col gap-6 justify-center">
        {careMode === 'AYUSH' && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-center text-sm font-semibold text-emerald-900">AYUSH history mode is active. Your responses are patient-reported information for practitioner review.</p>}
        {/* Progress Header */}
        <InterviewProgress
          collectedCount={questionCount}
          completionPercentage={completionPercentage}
          language={language}
        />
        {safetyFlags.length > 0 && <div role="alert" className="rounded-2xl border-2 border-rose-400 bg-rose-50 p-4 text-rose-950" id="clinical-safety-alert">
          <p className="font-bold">{isHindi ? 'तत्काल चिकित्सकीय सहायता लें। इंटरव्यू पूरा होने का इंतज़ार न करें।' : 'Seek urgent medical assessment. Do not wait to finish this interview.'}</p>
          {safetyFlags.map(flag => <p key={flag.code} className="mt-1 text-sm">{flag.message}</p>)}
          <p className="mt-2 text-xs">{isHindi ? 'यह सुरक्षा संकेत है, निदान नहीं।' : 'This is a safety alert, not a diagnosis.'}</p>
        </div>}
        {aiWarning && <p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{aiWarning}</p>}

        {/* Error Banner */}
        {errorMessage && (
          <div className="p-4 rounded-2xl bg-rose-50 border-2 border-rose-300 text-rose-900 flex items-center justify-between gap-3 animate-in fade-in shadow-sm" id="interview-error-banner">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
              <span className="text-sm font-semibold">{errorMessage}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={initializeInterview}
              leftIcon={<RefreshCw className="w-4 h-4" />}
              className="bg-white border-rose-300 text-rose-800 hover:bg-rose-100 shrink-0"
              id="retry-interview-button"
            >
              {isHindi ? 'पुनः प्रयास करें (Retry)' : 'Retry'}
            </Button>
          </div>
        )}

        {/* Initializing Loading State */}
        {isInitializing ? (
          <div className="bg-white rounded-3xl border border-slate-200 shadow-md p-10 sm:p-14 text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-sky-600 text-white mx-auto flex items-center justify-center animate-pulse shadow-md">
              <Bot className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900">
              {isHindi ? 'इंटरव्यू शुरू हो रहा है...' : 'Starting your interview...'}
            </h2>
            <p className="text-slate-500 text-sm">
              {isHindi
                ? 'कृपया प्रतीक्षा करें, हम आपके डॉक्टर के लिए सत्र तैयार कर रहे हैं।'
                : 'Connecting with the clinical engine. Please wait...'}
            </p>
          </div>
        ) : interviewCompleted ? (
          /* Interview Completed Banner & CTA */
          <div className="bg-white rounded-3xl border-2 border-emerald-500 shadow-xl p-8 sm:p-12 text-center space-y-6 animate-in fade-in">
            <div className="w-20 h-20 rounded-3xl bg-emerald-600 text-white mx-auto flex items-center justify-center shadow-lg shadow-emerald-600/20 ring-8 ring-emerald-50">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div className="space-y-2">
              <div className="text-xs font-black tracking-wider uppercase text-emerald-700">
                {isHindi ? 'इंटरव्यू संपन्न' : 'INTERVIEW COMPLETE'}
              </div>
              <h2 className="text-3xl font-black text-slate-900">
                {isHindi ? 'धन्यवाद! आपकी जानकारी दर्ज कर ली गई है।' : 'Thank you! Your information is recorded.'}
              </h2>
              <p className="text-base text-slate-600 max-w-lg mx-auto">
                {isHindi
                  ? 'आपकी सभी जानकारियां सुरक्षित रूप से संकलित कर डॉक्टर की समीक्षा के लिए तैयार कर दी गई हैं।'
                  : 'Your pre-consultation information has been recorded and will be available to the doctor for review.'}
              </p>
            </div>

            <div className="pt-4 max-w-md mx-auto">
              <Button
                variant="success"
                size="xl"
                onClick={handleFinishInterview}
                rightIcon={<ArrowRight className="w-5 h-5" />}
                className="w-full text-lg font-bold shadow-lg rounded-2xl py-4 min-h-[60px]"
                id="view-completed-button"
              >
                {isHindi ? 'जानकारी जाँचें और आगे बढ़ें' : 'Review & Continue'}
              </Button>
            </div>
          </div>
        ) : (
          /* Main Prominent Single Question Card */
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
            {/* Left 2 Cols: The Active Question & Voice / Text Controls */}
            <div className="md:col-span-2 bg-white rounded-3xl border-2 border-sky-300 shadow-lg p-6 sm:p-8 space-y-6">
              <TalkingAvatar mouth={speech.mouth} state={isRecording ? 'listening' : isSubmitting || isProcessingVoice || speech.loading ? 'thinking' : isSpeaking ? 'speaking' : 'waiting'} language={language} />
              {speech.notice && <p role="status" className="text-xs text-amber-800">{speech.notice}</p>}
              {isRequestingMic && <p role="status" className="text-sm text-sky-800">{isHindi ? 'माइक्रोफ़ोन की अनुमति दें…' : 'Waiting for microphone permission…'}</p>}
              {/* Question Header & Voice Mode Switcher */}
              <div className="flex flex-wrap items-center justify-between border-b border-slate-100 pb-3 gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-sky-600 text-white flex items-center justify-center font-bold shadow-xs">
                    <Bot className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-sky-900 block">
                      MediKiosk AI Assistant
                    </span>
                    <span className="text-xs text-slate-500 block">
                      {isHindi ? `मरीज: ${patient?.name || ''}` : `Patient: ${patient?.name || ''}`}
                    </span>
                  </div>
                </div>

                <div className="flex items-center flex-wrap gap-2">
                  {/* Switch to Writing / Typing Option */}
                  {voiceMode ? (
                    <button
                      type="button"
                      onClick={() => {
                        setVoiceMode(false);
                        stopSpeaking();
                        setTimeout(() => inputRef.current?.focus(), 150);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition-colors cursor-pointer shadow-2xs"
                      id="switch-to-typing-btn"
                    >
                      ✍️ {isHindi ? 'लिखकर उत्तर दें' : 'Switch to Typing'}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setVoiceMode(true);
                        speakQuestion(currentQuestion);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-sky-100 hover:bg-sky-200 text-sky-900 border border-sky-300 transition-colors cursor-pointer shadow-2xs"
                      id="switch-to-voice-btn"
                    >
                      🎙️ {isHindi ? 'बोलकर उत्तर दें (डिफ़ॉल्ट)' : 'Switch to Voice (Default)'}
                    </button>
                  )}

                  {/* Voice Mode Toggle Button (Preserved for tests & explicit toggle) */}
                  <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 px-3 py-1 rounded-xl">
                    <Mic className={`w-3.5 h-3.5 ${voiceMode ? 'text-rose-600 animate-pulse' : 'text-slate-400'}`} />
                    <span className="text-xs font-bold text-slate-700">
                      {isHindi ? 'वॉइस मोड:' : 'Voice Mode:'}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const newMode = !voiceMode;
                        setVoiceMode(newMode);
                        if (!newMode) stopSpeaking();
                        else speakQuestion(currentQuestion);
                      }}
                      className={`px-2.5 py-0.5 rounded-lg text-xs font-extrabold transition-colors cursor-pointer ${
                        voiceMode
                          ? 'bg-rose-600 text-white shadow-xs'
                          : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                      }`}
                      id="voice-mode-toggle-btn"
                    >
                      {voiceMode ? 'ON' : 'OFF'}
                    </button>
                  </div>

                  <span className="px-3 py-1 rounded-xl bg-sky-100 text-sky-800 text-xs font-bold">
                    {isHindi ? `प्रश्न #${questionCount}` : `Question #${questionCount}`}
                  </span>
                </div>
              </div>

              {/* Active Speaking Banner when AI is reading out */}
              {isSpeaking && (
                <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-sky-300 text-sky-950 flex items-center justify-between gap-3 animate-in fade-in shadow-xs">
                  <div className="flex items-center gap-2.5">
                    <div className="flex items-end gap-1 h-5">
                      <span className="w-1 bg-sky-600 rounded-full animate-bounce h-3" />
                      <span className="w-1 bg-sky-600 rounded-full animate-bounce h-5" />
                      <span className="w-1 bg-sky-600 rounded-full animate-bounce h-4" />
                      <span className="w-1 bg-sky-600 rounded-full animate-bounce h-2" />
                    </div>
                    <span className="text-xs sm:text-sm font-bold">
                      {isHindi ? '🔊 AI सवाल बोलकर सुना रहा है (सुनें)...' : '🔊 AI is reading the question aloud (listening)...'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={stopSpeaking}
                    className="px-2.5 py-1 rounded-lg text-xs font-bold bg-white text-slate-700 border border-slate-300 hover:bg-slate-100 cursor-pointer shadow-2xs"
                  >
                    {isHindi ? 'रोकें (Mute)' : 'Mute'}
                  </button>
                </div>
              )}

              {/* The Prominent Active Question */}
              <div className="space-y-2.5 py-1">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {isHindi ? 'वर्तमान प्रश्न:' : 'Current Question:'}
                  </div>

                  {/* Listen Question Button */}
                  <button
                    type="button"
                    onClick={() => speakQuestion(currentQuestion)}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-sky-50 text-sky-700 border border-sky-200 hover:bg-sky-100 transition-colors cursor-pointer shadow-2xs"
                    id="listen-question-btn"
                  >
                    <Volume2 className={`w-4 h-4 ${isSpeaking ? 'text-sky-600 animate-pulse' : 'text-sky-700'}`} />
                    <span>{isSpeaking ? (isHindi ? 'बोल रहे हैं...' : 'Speaking...') : (isHindi ? '🔊 सुनें (Listen)' : '🔊 Listen')}</span>
                  </button>
                </div>

                <h1
                  className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-snug tracking-tight"
                  id="active-question-text"
                >
                  {currentQuestion}
                </h1>
                <p className="text-xs text-slate-500 font-medium">
                  {voiceMode
                    ? isHindi
                      ? 'डिफ़ॉल्ट वॉइस मोड: माइक बटन दबाकर बोलें। आप कभी भी नीचे लिखकर भी उत्तर दे सकते हैं।'
                      : 'Default Voice Mode: Tap Speak to answer. You can also switch to typing anytime below.'
                    : isHindi
                    ? 'नीचे दिए गए बॉक्स में अपना उत्तर लिखें और आगे बढ़ें दबाएं।'
                    : 'Type your answer below and press Continue to proceed.'}
                </p>
              </div>

              {/* Voice Mode Primary Controller (Step 4C) - Prominent Default */}
              {voiceMode && (
                <div className="p-5 rounded-2xl bg-gradient-to-tr from-sky-50 to-indigo-50/60 border-2 border-sky-200 space-y-4 shadow-sm" id="voice-interaction-panel">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-sky-900 flex items-center gap-2">
                      <Mic className="w-4 h-4 text-sky-600" />
                      <span>{isHindi ? 'ध्वनि उत्तर (Voice Input - डिफ़ॉल्ट)' : 'Voice Input (Default)'}</span>
                    </span>
                    {isRecording && (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-100 border border-rose-300 text-rose-900 text-xs font-bold animate-pulse" id="recording-indicator">
                        <span className="w-2.5 h-2.5 rounded-full bg-rose-600" />
                        <span>{isHindi ? `रिकॉर्डिंग... (${recordingSeconds}s)` : `Recording... (${recordingSeconds}s)`}</span>
                      </span>
                    )}
                  </div>

                  {/* Audio Wave Visualizer during Active Recording */}
                  {isRecording && (
                    <div className="flex items-center justify-center gap-1.5 py-1">
                      <span className="w-1.5 h-6 bg-rose-500 rounded-full animate-pulse" />
                      <span className="w-1.5 h-10 bg-rose-600 rounded-full animate-bounce" />
                      <span className="w-1.5 h-14 bg-rose-500 rounded-full animate-pulse" />
                      <span className="w-1.5 h-8 bg-rose-600 rounded-full animate-bounce" />
                      <span className="w-1.5 h-5 bg-rose-500 rounded-full animate-pulse" />
                      <span className="text-xs font-bold text-rose-700 ml-2">
                        {isHindi ? '🎙️ आपकी आवाज़ सुनी जा रही है...' : '🎙️ Listening to your voice...'}
                      </span>
                    </div>
                  )}

                  {/* Main Record / Stop Action Bar */}
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 pt-1">
                    {!isRecording ? (
                      <Button
                        type="button"
                        variant="primary"
                        size="xl"
                        onClick={handleStartRecording}
                        disabled={isProcessingVoice || isSubmitting || isRequestingMic || !!inputText.trim()}
                        leftIcon={<Mic className="w-6 h-6 text-white" />}
                        className="w-full sm:w-auto px-8 py-4 rounded-2xl font-black text-lg bg-sky-600 hover:bg-sky-700 shadow-md min-h-[56px]"
                        id="voice-record-btn"
                      >
                        {isProcessingVoice
                          ? isHindi
                            ? '⏳ आवाज़ प्रोसेस हो रही है...'
                            : '⏳ Processing Audio...'
                          : isHindi
                          ? '🎤 बोलें (Speak)'
                          : '🎤 Speak'}
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="danger"
                        size="xl"
                        onClick={handleStopRecording}
                        leftIcon={<Square className="w-5 h-5 text-white fill-white" />}
                        className="w-full sm:w-auto px-8 py-4 rounded-2xl font-black text-lg bg-rose-600 hover:bg-rose-700 shadow-lg animate-pulse min-h-[56px]"
                        id="voice-stop-btn"
                      >
                        {isHindi ? '⏹ रोकें और जाँचें' : '⏹ Stop & Review'}
                      </Button>
                    )}
                  </div>

                  {/* Quick toggle to writing */}
                  <div className="text-center pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        setVoiceMode(false);
                        stopSpeaking();
                        setTimeout(() => inputRef.current?.focus(), 150);
                      }}
                      className="text-xs font-semibold text-slate-500 hover:text-sky-700 hover:underline cursor-pointer"
                    >
                      {isHindi ? '✍️ या लिखकर उत्तर देने के लिए यहाँ क्लिक करें' : '✍️ Or click here to switch to typing'}
                    </button>
                  </div>

                  {/* Live Transcript Display Card */}
                  {lastTranscript && (
                    <div className="p-3.5 rounded-xl bg-white border border-sky-200 text-xs text-slate-800 shadow-2xs space-y-1 animate-in fade-in" id="voice-transcript-card">
                      <span className="font-bold text-[10px] uppercase tracking-wider text-slate-400 block">
                        {isHindi ? 'मसौदा — नीचे सुधारें और आगे बढ़ें दबाएँ। अभी सेव नहीं हुआ।' : 'Draft — correct the text below, then Continue to save. Not submitted yet.'}
                      </span>
                      <p className="text-sm font-semibold text-sky-950 italic" id="voice-transcript-text">
                        "{lastTranscript}"
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Writing Mode Active Notice (When voice mode is toggled off) */}
              {!voiceMode && (
                <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center justify-between gap-3 shadow-2xs animate-in fade-in">
                  <div className="flex items-center gap-2">
                    <span>✍️</span>
                    <span className="font-medium">
                      {isHindi
                        ? 'टाइपिंग मोड सक्रिय है। आप कभी भी बोलकर उत्तर देने के लिए डिफ़ॉल्ट वॉइस मोड चालू कर सकते हैं।'
                        : 'Writing mode is active. You can switch back to default voice mode anytime.'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setVoiceMode(true);
                      speakQuestion(currentQuestion);
                    }}
                    className="font-bold text-sky-800 hover:underline shrink-0 cursor-pointer"
                  >
                    {isHindi ? '🎙️ वॉइस मोड चालू करें' : '🎙️ Turn Voice On'}
                  </button>
                </div>
              )}

              {/* Processing Spinner */}
              {(isSubmitting || isProcessingVoice) && (
                <div className="p-4 rounded-2xl bg-sky-50 border border-sky-200 flex items-center gap-3 animate-pulse" id="processing-indicator">
                  <div className="w-5 h-5 border-2 border-sky-600 border-t-transparent rounded-full animate-spin shrink-0" />
                  <span className="text-sm font-bold text-sky-900">
                    {isProcessingVoice
                      ? isHindi
                        ? 'आवाज़ का विश्लेषण हो रहा है (Processing audio)...'
                        : 'Transcribing speech & analyzing symptoms...'
                      : isHindi
                      ? 'कृपया प्रतीक्षा करें (Please wait)...'
                      : 'Analyzing response. Please wait...'}
                  </span>
                </div>
              )}

              {/* Patient Text Answer Input Area (Seamless Fallback) */}
              <div className="space-y-3 pt-2">
                <label
                  htmlFor="patient-answer-input"
                  className="block text-xs font-bold uppercase tracking-wider text-slate-700"
                >
                  {isHindi ? 'या यहाँ लिखें (Or Type Your Answer):' : 'Or Type Your Answer:'}
                </label>
                <div className="relative">
                  <input
                    id="patient-answer-input"
                    ref={inputRef}
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !isSubmitting && !isProcessingVoice && inputText.trim()) {
                        handleSendResponse();
                      }
                    }}
                    placeholder={
                      isHindi
                        ? 'यहाँ अपना उत्तर लिखें (उदा. 3 दिन से दर्द है)...'
                        : 'Type your symptoms or answer here...'
                    }
                    disabled={isSubmitting || isProcessingVoice || isRecording || isRequestingMic}
                    className="w-full px-5 py-4 rounded-2xl border-2 border-slate-300 focus:border-sky-600 focus:ring-4 focus:ring-sky-100 text-base sm:text-lg text-slate-900 font-medium placeholder-slate-400 bg-white transition-all shadow-inner"
                  />
                </div>

                {/* Submit / Continue Button */}
                <div className="flex items-center gap-3 pt-2">
                  <Button
                    variant="primary"
                    size="xl"
                    onClick={() => handleSendResponse()}
                    disabled={!inputText.trim() || isSubmitting || isProcessingVoice || isRecording || isRequestingMic}
                    rightIcon={<ArrowRight className="w-6 h-6" />}
                    className="w-full text-lg font-bold shadow-md rounded-2xl py-4 min-h-[56px]"
                    id="submit-answer-button"
                  >
                    {isSubmitting || isProcessingVoice
                      ? isHindi
                        ? 'प्रतीक्षा करें...'
                        : 'Please wait...'
                      : isHindi
                      ? 'आगे बढ़ें / भेजें (Continue)'
                      : 'Continue'}
                  </Button>
                </div>
              </div>
            </div>

            {/* Right 1 Col: Live Extracted Structured Data */}
            <div className="md:col-span-1 space-y-4">
              <ExtractedInfo data={extractedData} language={language} />

              <div className="p-4 rounded-2xl bg-white border border-slate-200 text-xs text-slate-600 space-y-2 shadow-xs">
                <div className="flex items-center gap-1.5 font-bold text-slate-800">
                  <HelpCircle className="w-4 h-4 text-sky-600" />
                  <span>{isHindi ? 'मदद एवं वॉइस निर्देश' : 'Voice & Text Instructions'}</span>
                </div>
                <p className="leading-relaxed text-[12px]">
                  {isHindi
                    ? 'आप बोलकर या लिखकर अपनी भाषा में बता सकते हैं। वॉइस मोड चालू करने पर सवाल बोलकर भी सुनाया जाएगा।'
                    : 'You can speak using the microphone or type your symptoms. When Voice Mode is ON, questions are also spoken aloud.'}
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-3 bg-white text-center text-xs text-slate-500">
        Medisaarthi • AI Pre-Consultation Voice & Text Assistant
      </footer>
    </div>
  );
}
