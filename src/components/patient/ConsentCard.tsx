import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Lock, UserCheck, AlertCircle, HeartHandshake } from 'lucide-react';

interface ConsentCardProps {
  agreed: boolean;
  onToggleAgree: (agreed: boolean) => void;
  language?: 'hi' | 'en';
}

export const ConsentCard: React.FC<ConsentCardProps> = ({
  agreed,
  onToggleAgree,
  language = 'hi',
}) => {
  const [showFaq, setShowFaq] = useState(false);

  const isHindi = language === 'hi';

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
      {/* Intro Banner */}
      <div className="flex items-start gap-4 p-4 rounded-xl bg-sky-50/70 border border-sky-100">
        <div className="w-10 h-10 rounded-lg bg-sky-600 flex items-center justify-center text-white shrink-0 shadow-xs">
          <HeartHandshake className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-sky-950">
            {isHindi ? 'परामर्श की बेहतर तैयारी' : 'Preparing for your consultation'}
          </h2>
          <p className="text-sm text-sky-900/80 mt-1 leading-relaxed">
            {isHindi
              ? 'हम आपसे आपके स्वास्थ्य के बारे में कुछ सरल प्रश्न पूछेंगे ताकि आपके डॉक्टर आपसे मिलने से पहले आपकी पूरी स्थिति को समझ सकें।'
              : "We'll ask a few simple questions about your health to prepare structured information for your doctor before you meet."}
          </p>
        </div>
      </div>

      {/* Key Guarantees */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
          <Lock className="w-5 h-5 text-sky-600 shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-semibold text-slate-900 block">
              {isHindi ? 'सीमित और अधिकृत पहुँच' : 'Access restricted to authorized users'}
            </span>
            <span className="text-slate-500 mt-0.5 block leading-relaxed">
              {isHindi
                ? 'आपकी जानकारी केवल आपके अधिकृत डॉक्टर के साथ साझा की जाती है।'
                : 'Your health responses are encrypted and accessible only by your treating doctor.'}
            </span>
          </div>
        </div>

        <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
          <UserCheck className="w-5 h-5 text-teal-600 shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-semibold text-slate-900 block">
              {isHindi ? 'डॉक्टर का पूर्ण नियंत्रण' : 'Doctor in Full Control'}
            </span>
            <span className="text-slate-500 mt-0.5 block leading-relaxed">
              {isHindi
                ? 'यह AI केवल सहायक है। उपचार का अंतिम निर्णय आपके डॉक्टर का ही होगा।'
                : 'AI assists in collecting data; diagnosis & treatment is verified by your physician.'}
            </span>
          </div>
        </div>
      </div>

      {/* Expandable Why do we ask this? */}
      <div className="border border-slate-200 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowFaq(!showFaq)}
          className="w-full flex items-center justify-between px-4 py-3 bg-slate-50/70 hover:bg-slate-100 text-left text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-sky-600" />
            <span>
              {isHindi ? 'हम यह जानकारी क्यों एकत्र करते हैं?' : 'Why do we ask these questions?'}
            </span>
          </div>
          {showFaq ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </button>
        {showFaq && (
          <div className="p-4 bg-white text-xs text-slate-600 leading-relaxed border-t border-slate-100 space-y-2">
            <p>
              {isHindi
                ? 'अस्पताल में अक्सर डॉक्टर के पास समय सीमित होता है। पहले से लक्षण, दर्द की अवधि और पुरानी दवाइयों की जानकारी दर्ज रहने से डॉक्टर सीधे आपके इलाज पर ध्यान केंद्रित कर पाते हैं और आपका समय बचता है।'
                : 'In busy hospital clinics, preparing your symptom onset, duration, and past medications in advance saves valuable consultation time, allowing your doctor to focus directly on your clinical examination and care plan.'}
            </p>
          </div>
        )}
      </div>

      {/* Checkbox Section */}
      <div className="pt-2 border-t border-slate-100">
        <label
          htmlFor="consent-checkbox"
          className={`flex items-start gap-3.5 p-4 rounded-xl border-2 transition-all cursor-pointer select-none ${
            agreed
              ? 'border-sky-600 bg-sky-50/40 text-slate-900'
              : 'border-slate-200 bg-slate-50 hover:bg-slate-100/80 text-slate-700'
          }`}
        >
          <input
            id="consent-checkbox"
            type="checkbox"
            checked={agreed}
            onChange={(e) => onToggleAgree(e.target.checked)}
            className="w-5 h-5 rounded text-sky-600 focus:ring-sky-500 border-slate-300 mt-0.5 cursor-pointer"
          />
          <div className="text-sm font-medium">
            <span className="font-semibold block text-slate-900">
              {isHindi ? 'मैं समझता/समझती हूँ और सहमत हूँ' : 'I understand and agree'}
            </span>
            <span className="text-xs text-slate-500 block mt-0.5">
              {isHindi
                ? 'मैं अपने लक्षणों की जानकारी डॉक्टर की तैयारी के लिए साझा करने की अनुमति देता/देती हूँ।'
                : 'I give consent to record my pre-consultation responses for my doctor.'}
            </span>
          </div>
        </label>
      </div>
    </div>
  );
};
