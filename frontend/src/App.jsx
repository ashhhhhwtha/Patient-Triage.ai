// PatientTriage.ai — Phase 4 frontend: fully wired to the FastAPI backend.
// Login with a real account -> JWT; every screen refreshes live over WebSocket.
import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Mic, MicOff, Activity, Stethoscope, Ambulance, UserCheck, User,
  Monitor, FileText, Download, Bell, Clock, ShieldCheck, ChevronRight,
  Zap, RefreshCw, Check, HeartPulse, Thermometer, Wind, Gauge,
  ClipboardList, LogOut, Wifi, WifiOff, AlertTriangle, History,
} from "lucide-react";
import { jsPDF } from "jspdf";
import {
  setToken, login, getQueue, registerPatient, postVitals, postOverride,
  postPrescription, getPrescription, getAudit, triggerSurge, connectWS,
  transcribeAudio, extractFields, lookupPatient, getCompleted, getHistory,
} from "./api";

/* ---------------- display maps (backend uses lowercase categories) ---------------- */
const CATS = ["emergency", "urgent", "lower"];
const CAT_LABEL = { emergency: "Emergency", urgent: "Urgent", lower: "Lower Urgency" };
const CAT_STYLE = {
  emergency: { bg: "bg-red-600", light: "bg-red-50", border: "border-red-600", ring: "#dc2626" },
  urgent: { bg: "bg-amber-500", light: "bg-amber-50", border: "border-amber-500", ring: "#f59e0b" },
  lower: { bg: "bg-emerald-600", light: "bg-emerald-50", border: "border-emerald-600", ring: "#059669" },
};

const ACCOUNTS = [
  { username: "kiosk", hint: "kiosk123", label: "Reception Kiosk", role: "kiosk" },
  { username: "nurse1", hint: "nurse123", label: "Nurse J. Kalita", role: "nurse" },
  { username: "doc1", hint: "doctor123", label: "Dr. A. Choudhury — Cardiology", role: "doctor" },
  { username: "doc2", hint: "doctor123", label: "Dr. S. Bhattacharya — Pediatrics", role: "doctor" },
  { username: "doc3", hint: "doctor123", label: "Dr. M. Begum — Duty Doctor (all departments)", role: "doctor" },
  { username: "patient", hint: "patient123", label: "📱 Patient — my visit (phone view)", role: "patient" },
];

const SAMPLE_VOICE = [
  "My name is Rina Sen, I am 36 years old, female. I have had severe stomach pain and vomiting since morning.",
  "I am Amit Verma, 61, male. Chest pain and breathless when climbing stairs today.",
  "This is for my son, he is 5, fever since last night and a rash on his chest.",
];

function parseVoice(text) {
  const out = { name: "", age: "", gender: "", concern: text };
  const nameM = text.match(/(?:my name is|i am|this is)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)/i);
  if (nameM) out.name = nameM[1];
  const ageM = text.match(/(\d{1,3})\s*(?:years old|yrs|years|,)/i) || text.match(/he is (\d{1,2})/i) || text.match(/\b(\d{1,3})\b/);
  if (ageM) out.age = ageM[1];
  if (/female|woman|she\b/i.test(text)) out.gender = "F";
  else if (/\bmale|man\b|he\b|son/i.test(text)) out.gender = "M";
  return out;
}

/* ---------------- small UI pieces ---------------- */
function ConfidenceRing({ value, color }) {
  const pct = Math.round((value || 0) * 100);
  const r = 16, c = 2 * Math.PI * r;
  return (
    <div className="relative w-11 h-11 flex items-center justify-center shrink-0" title={`Confidence ${pct}%`}>
      <svg width="44" height="44" className="-rotate-90">
        <circle cx="22" cy="22" r={r} fill="none" stroke="#e2e8f0" strokeWidth="4" />
        <circle cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} strokeLinecap="round" />
      </svg>
      <span className="absolute text-[10px] font-bold text-slate-700">{pct}%</span>
    </div>
  );
}

function CatBadge({ cat, escalated }) {
  const s = CAT_STYLE[cat];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold text-white ${s.bg}`}>
      {CAT_LABEL[cat]}{escalated && <AlertTriangle size={11} />}
    </span>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
const inputCls = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-500";

const APPEARANCE_FLAGS = ["pale", "sweating", "distressed", "confused", "lethargic", "bleeding visible", "looks well"];
function AppearancePicker({ value, onChange }) {
  const toggle = (f) =>
    onChange(value.includes(f) ? value.filter((x) => x !== f)
      : [...value.filter((x) => (f === "looks well" ? false : x !== "looks well")), f]);
  return (
    <div className="flex flex-wrap gap-1.5">
      {APPEARANCE_FLAGS.map((f) => (
        <button type="button" key={f} onClick={() => toggle(f)}
          className={`px-2.5 py-1 rounded-full text-xs border ${value.includes(f) ? "bg-slate-800 text-white border-slate-800" : "bg-white border-slate-300 text-slate-600 hover:border-slate-500"}`}>
          {f}
        </button>
      ))}
    </div>
  );
}

function VitalsCapture({ vitals, setVitals }) {
  const capture = () =>
    setVitals({
      hr: 62 + Math.floor(Math.random() * 55),
      bp_sys: 98 + Math.floor(Math.random() * 55),
      bp_dia: 60 + Math.floor(Math.random() * 30),
      spo2: 91 + Math.floor(Math.random() * 9),
      temp: Math.round((36.2 + Math.random() * 2.6) * 10) / 10,
    });
  const items = [
    { k: "spo2", label: "SpO₂ %", icon: Wind },
    { k: "hr", label: "Heart rate", icon: HeartPulse },
    { k: "bp_sys", label: "BP systolic", icon: Gauge },
    { k: "bp_dia", label: "BP diastolic", icon: Gauge },
    { k: "temp", label: "Temp °C", icon: Thermometer },
  ];
  return (
    <div className="bg-sky-50 border border-sky-200 rounded-xl p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold text-sky-900 uppercase tracking-wider flex items-center gap-1"><Activity size={13} /> Connected vitals devices</span>
        <button type="button" onClick={capture} className="text-xs bg-sky-600 hover:bg-sky-700 text-white px-3 py-1.5 rounded-lg font-semibold">
          Capture from oximeter · BP cuff · thermometer
        </button>
      </div>
      <div className="grid grid-cols-5 gap-2">
        {items.map(({ k, label, icon: Icon }) => (
          <div key={k} className="bg-white rounded-lg p-2 text-center border border-sky-100">
            <Icon size={14} className="mx-auto text-sky-600" />
            <input className="w-full text-center text-sm font-bold bg-transparent focus:outline-none" placeholder="—"
              value={vitals?.[k] ?? ""}
              onChange={(e) => setVitals({ ...(vitals || {}), [k]: e.target.value === "" ? null : Number(e.target.value) })} />
            <div className="text-[9px] text-slate-500">{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================ LOGIN ================================ */
function Login({ onLogin }) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const quick = async (a) => {
    setBusy(a.username); setErr("");
    try {
      const u = await login(a.username, a.hint);
      setToken(u.token);
      onLogin({ ...u, username: a.username });
    } catch (e) {
      setErr(e?.response?.data?.detail || "Login failed — is the backend running?");
    } finally { setBusy(""); }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md">
        <div className="flex items-center gap-2 mb-1">
          <HeartPulse className="text-sky-600" size={24} />
          <h1 className="font-bold text-xl">PatientTriage.ai</h1>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Pick a role to explore the system — one click, no typing. Every action you take is
          recorded against that identity in the audit trail.
        </p>
        <div className="grid grid-cols-1 gap-2 mb-2">
          {ACCOUNTS.map((a) => (
            <button key={a.username} onClick={() => quick(a)} disabled={!!busy}
              className="text-left p-3 rounded-xl border border-slate-200 hover:border-sky-500 hover:bg-sky-50 disabled:opacity-50 flex items-center justify-between">
              <div>
                <div className="font-bold text-sm">{a.label}</div>
                <div className="text-[11px] text-slate-400 capitalize">{a.role} console</div>
              </div>
              <span className="text-xs font-semibold text-sky-700">
                {busy === a.username ? "Signing in…" : "Enter →"}
              </span>
            </button>
          ))}
        </div>
        {err && <div className="mt-1 text-xs text-red-600 font-semibold">{err}</div>}
        <p className="mt-3 text-[10px] text-slate-400">
          One-click demo accounts (JWT role auth is real behind the scenes). Production uses
          hospital staff SSO; patients receive a tokenized SMS link at check-in.
        </p>
      </div>
    </div>
  );
}

/* ================================ MAIN APP ================================ */
export default function TriageApp() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("board");
  const [queue, setQueue] = useState([]);
  const [auditRows, setAuditRows] = useState([]);
  const [notifs, setNotifs] = useState([]);   // {type, text, patient_id, at}
  const [wsOk, setWsOk] = useState(false);
  const [toast, setToast] = useState(null);
  const wsRef = useRef(null);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3200); };

  const refresh = useCallback(() => {
    getQueue().then(setQueue).catch(() => {});
    getAudit().then(setAuditRows).catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) return;
    refresh();
    const ws = connectWS((msg) => {
      if (msg.event === "queue_updated") refresh();
      if (msg.event === "prescription_ready") {
        refresh();
        setNotifs((n) => [{ type: "rx", patient_id: msg.data.patient_id, at: new Date().toLocaleTimeString(),
          text: `Prescription for ${msg.data.name} signed by ${msg.data.doctor} — sent to patient's phone.` }, ...n]);
        showToast(`Prescription ready: ${msg.data.name}`);
      }
      if (msg.event === "reassess_due") {
        refresh();
        setNotifs((n) => [{ type: "reassess", patient_id: msg.data.patient_id, at: new Date().toLocaleTimeString(),
          text: `${msg.data.name} has waited past the safe threshold — re-assessment required.` }, ...n]);
        showToast(`Re-assess: ${msg.data.name}`);
      }
    }, setWsOk);
    wsRef.current = ws;
    return () => ws.close();
  }, [user, refresh]);

  if (!user) return <Login onLogin={(u) => { setUser(u); setView(u.role === "kiosk" ? "kiosk" : u.role === "doctor" ? "doctor" : u.role === "patient" ? "patient" : "board"); }} />;

  const allTabs = [
    { id: "board", label: "Queue Board", icon: Monitor, roles: ["nurse", "doctor"] },
    { id: "kiosk", label: "Kiosk", icon: Mic, roles: ["kiosk", "nurse"] },
    { id: "ambulance", label: "Ambulance", icon: Ambulance, roles: ["kiosk", "nurse"] },
    { id: "nurse", label: "Nurse Review", icon: UserCheck, roles: ["nurse"] },
    { id: "doctor", label: "Doctor", icon: Stethoscope, roles: ["doctor"] },
    { id: "patient", label: "Patient Portal", icon: User, roles: ["patient"] },
    { id: "audit", label: "Audit Trail", icon: ClipboardList, roles: ["nurse", "doctor"] },
  ];
  const tabs = allTabs.filter((t) => t.roles.includes(user.role));

  const doSurge = async () => {
    try { const r = await triggerSurge(); showToast(`Surge: ${r.injected} patients injected`); }
    catch { showToast("Surge failed — check backend"); }
  };

  return (
    <div className="min-h-screen bg-slate-100 font-sans text-slate-800">
      <header className="bg-slate-900 text-white">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <HeartPulse className="text-sky-400" size={22} />
            <div>
              <div className="font-bold tracking-tight leading-none">PatientTriage.ai</div>
              <div className="text-[10px] text-slate-400 tracking-widest uppercase">Decision support · Clinician always in charge</div>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2 text-xs">
            <span className={`flex items-center gap-1 px-2 py-1 rounded-full ${wsOk ? "bg-emerald-700" : "bg-red-700"}`}>
              {wsOk ? <Wifi size={12} /> : <WifiOff size={12} />} {wsOk ? "live" : "offline"}
            </span>
            {user.role !== "patient" && (
              <button onClick={doSurge} className="bg-red-700 hover:bg-red-600 px-2 py-1 rounded-full flex items-center gap-1">
                <Zap size={12} /> Simulate 3× surge
              </button>
            )}
            <span className="bg-slate-800 px-2 py-1 rounded-full">{user.display}</span>
            <button onClick={() => { wsRef.current?.close(); setUser(null); }}
              className="bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded-full flex items-center gap-1">
              <LogOut size={12} /> Sign out
            </button>
          </div>
        </div>
        <nav className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setView(t.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-t-lg whitespace-nowrap ${view === t.id ? "bg-slate-100 text-slate-900 font-semibold" : "text-slate-300 hover:text-white"}`}>
              <t.icon size={15} /> {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-5">
        {view === "board" && <Board queue={queue} />}
        {view === "kiosk" && <Kiosk onDone={(t) => showToast(`Added to queue — ${CAT_LABEL[t.category]} (${Math.round(t.confidence * 100)}% conf, ${t.specialty})`)} />}
        {view === "ambulance" && <AmbulanceEntry onDone={(t) => showToast(`Dispatched — ${CAT_LABEL[t.category]} (${t.specialty})`)} />}
        {view === "nurse" && <NurseView queue={queue} showToast={showToast} />}
        {view === "doctor" && <DoctorView queue={queue} user={user} showToast={showToast} />}
        {view === "patient" && <PatientPortal queue={queue} notifs={notifs} />}
        {view === "audit" && <AuditView rows={auditRows} />}
      </main>

      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-slate-900 text-white text-sm px-4 py-2 rounded-full shadow-lg flex items-center gap-2 z-50">
          <Check size={14} className="text-emerald-400" /> {toast}
        </div>
      )}
    </div>
  );
}

/* ================================ BOARD ================================ */
function PatientRow({ p, i, showCatBadge }) {
  const s = CAT_STYLE[p.category];
  return (
    <div className={`p-3 border-l-4 ${s.border} ${p.reassess_due ? "bg-amber-50" : ""}`}>
      <div className="flex items-start gap-2">
        <span className="text-xs font-mono text-slate-400 mt-1">#{i + 1}</span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm flex items-center gap-1.5 flex-wrap">
            {p.name} <span className="text-slate-400 font-normal">· {p.age}{p.gender}</span>
            {p.source === "ambulance" && <Ambulance size={13} className="text-red-600" />}
            {!p.has_history && <span className="text-[10px] bg-slate-200 px-1.5 rounded-full">no record</span>}
            {showCatBadge && <CatBadge cat={p.category} escalated={p.escalated} />}
          </div>
          <div className="text-xs text-slate-500 truncate">{p.concern}</div>
          <div className="text-[11px] text-slate-500 mt-1 flex gap-3 flex-wrap">
            {!showCatBadge && <span>{p.specialty}</span>}
            <span>score {p.score}</span>
            <span>waited {p.waited_min}m · est. {p.est_wait_min}m</span>
          </div>
          {p.reassess_due && (
            <div className="mt-1 text-[11px] font-semibold text-amber-700 flex items-center gap-1">
              <RefreshCw size={11} /> Re-assessment due — waited past safe threshold
            </div>
          )}
        </div>
        <ConfidenceRing value={p.confidence} color={s.ring} />
      </div>
    </div>
  );
}

function Board({ queue }) {
  const [groupBy, setGroupBy] = useState("department");
  const byDept = {};
  queue.forEach((p) => { if (!byDept[p.specialty]) byDept[p.specialty] = []; byDept[p.specialty].push(p); });
  const deptGroups = Object.entries(byDept).sort((a, b) => {
    const sev = (l) => Math.min(...l.map((p) => CATS.indexOf(p.category)));
    return sev(a[1]) - sev(b[1]) || b[1].length - a[1].length;
  });
  const catGroups = CATS.map((c) => ({ cat: c, list: queue.filter((p) => p.category === c) }));

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h2 className="font-bold text-lg">Live triage board</h2>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg overflow-hidden border border-slate-300 text-xs font-semibold">
            {[["department", "By department"], ["severity", "By severity"]].map(([k, label]) => (
              <button key={k} onClick={() => setGroupBy(k)}
                className={`px-3 py-1.5 ${groupBy === k ? "bg-slate-800 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
                {label}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-500">{queue.length} in queue · live via WebSocket</span>
        </div>
      </div>

      {groupBy === "department" ? (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {deptGroups.length === 0 && <div className="text-sm text-slate-400">Queue is empty.</div>}
          {deptGroups.map(([dept, list]) => (
            <div key={dept} className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="bg-slate-800 text-white px-3 py-2 flex items-center justify-between">
                <span className="font-bold text-sm">{dept}</span>
                <span className="flex items-center gap-1.5">
                  {CATS.map((c) => {
                    const n = list.filter((p) => p.category === c).length;
                    return n > 0 ? <span key={c} className={`${CAT_STYLE[c].bg} text-[10px] font-bold px-1.5 py-0.5 rounded-full`}>{n}</span> : null;
                  })}
                  <span className="text-[10px] text-slate-300 ml-1">{list.length} waiting</span>
                </span>
              </div>
              <div className="divide-y divide-slate-100 max-h-[420px] overflow-y-auto">
                {list.map((p, i) => <PatientRow key={p.id} p={p} i={i} showCatBadge />)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-4">
          {catGroups.map(({ cat, list }) => {
            const s = CAT_STYLE[cat];
            return (
              <div key={cat} className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className={`${s.bg} text-white px-3 py-2 flex items-center justify-between`}>
                  <span className="font-bold text-sm">{CAT_LABEL[cat]}</span>
                  <span className="text-xs bg-white/25 px-2 py-0.5 rounded-full">{list.length}</span>
                </div>
                <div className="divide-y divide-slate-100 max-h-[520px] overflow-y-auto">
                  {list.length === 0 && <div className="p-4 text-xs text-slate-400">No patients in this band.</div>}
                  {list.map((p, i) => <PatientRow key={p.id} p={p} i={i} />)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ================================ KIOSK ================================ */
function Kiosk({ onDone }) {
  const [step, setStep] = useState(1);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [form, setForm] = useState({ name: "", age: "", gender: "", concern: "", pain: 0, has_history: false });
  const [vitals, setVitals] = useState(null);
  const [appearance, setAppearance] = useState([]);
  const [busy, setBusy] = useState(false);
  const [welcome, setWelcome] = useState(null);   // returning-patient record
  const [looking, setLooking] = useState(false);
  const recRef = useRef(null);

  const findRecord = async () => {
    setLooking(true); setWelcome(null);
    try {
      const r = await lookupPatient(form.name, Number(form.age) || undefined);
      if (r.found) {
        setWelcome(r.records[0]);
        setForm((f) => ({ ...f, has_history: true }));
      } else setWelcome({ none: true });
    } catch { setWelcome({ none: true }); }
    finally { setLooking(false); }
  };

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setTranscript("(Voice not available in this browser — use a sample below or type.)"); return; }
    try {
      const rec = new SR();
      rec.lang = "en-IN"; rec.interimResults = true; rec.continuous = true;
      rec.onresult = (e) => setTranscript(Array.from(e.results).map((r) => r[0].transcript).join(" "));
      rec.onend = () => setRecording(false);
      rec.start(); recRef.current = rec; setRecording(true);
    } catch { setTranscript("(Microphone blocked — use a sample or type.)"); }
  };
  const stopVoice = () => { recRef.current?.stop(); setRecording(false); };

  // HD voice: records audio and sends it to the backend /transcribe (Whisper via Groq)
  const mediaRef = useRef(null);
  const startHDVoice = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        const fd = new FormData();
        fd.append("audio", blob, "speech.webm");
        setTranscript("Transcribing…");
        try {
          const data = await transcribeAudio(fd);
          applyTranscript(data.text || "(no speech detected)");
        } catch { setTranscript("(Whisper unavailable — use the normal mic instead)"); }
      };
      rec.start(); mediaRef.current = rec; setRecording(true);
    } catch { setTranscript("(Microphone blocked)"); }
  };
  const stopHDVoice = () => { mediaRef.current?.stop(); setRecording(false); };

  const applyTranscript = async (t) => {
    setTranscript(t);
    try {
      // AI LAYER 2: LLM understands the messy speech -> structured fields + red flags.
      // Red flags are appended into the concern so the RULES FLOOR sees them —
      // the LLM informs triage; it never decides severity.
      const d = await extractFields(t);
      // normalized symptoms + red flags go INTO the concern text, so the
      // triage engine's vocabulary matching and rules floor both see them
      const extras = [
        d.symptoms?.length ? `symptoms: ${d.symptoms.join(", ")}` : null,
        d.red_flags?.length ? `red flags: ${d.red_flags.join(", ")}` : null,
      ].filter(Boolean).join("; ");
      const concern = extras ? `${d.concern} (${extras})` : d.concern;
      setForm((f) => ({
        ...f,
        name: d.name || f.name,
        age: d.age ?? f.age,
        gender: d.gender || f.gender,
        concern: concern || t,
      }));
    } catch {
      // fallback: regex parsing — the demo can never break on an LLM hiccup
      const parsed = parseVoice(t);
      setForm((f) => ({ ...f, name: parsed.name || f.name, age: parsed.age || f.age, gender: parsed.gender || f.gender, concern: t }));
    }
  };

  const submit = async () => {
    setBusy(true);
    try {
      const r = await registerPatient({
        name: form.name || "Walk-in patient", age: Number(form.age) || 30, gender: form.gender || "",
        concern: form.concern, pain: Number(form.pain) || 0, has_history: form.has_history,
        source: "kiosk", appearance, vitals: vitals || undefined,
      });
      onDone(r.triage);
      setStep(1); setForm({ name: "", age: "", gender: "", concern: "", pain: 0, has_history: false });
      setVitals(null); setAppearance([]); setTranscript("");
    } catch { onDone({ category: "lower", confidence: 0, specialty: "error — check backend" }); }
    finally { setBusy(false); }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-2xl shadow-sm p-6">
        <div className="flex items-center gap-2 mb-1">
          <Mic className="text-sky-600" size={20} />
          <h2 className="font-bold text-lg">Reception kiosk — self check-in</h2>
        </div>
        <p className="text-sm text-slate-500 mb-4">Speak your name, age and problem. The AI fills the form; confirm before it goes to triage.</p>
        <div className="flex gap-2 mb-5 text-xs font-semibold">
          {["1 · Tell us your problem", "2 · Vitals check", "3 · Confirm & submit"].map((s, i) => (
            <span key={s} className={`px-3 py-1.5 rounded-full ${step === i + 1 ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-500"}`}>{s}</span>
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <div className="bg-slate-50 rounded-xl p-4 text-center">
              <button onClick={recording ? stopVoice : startVoice}
                className={`mx-auto w-20 h-20 rounded-full flex items-center justify-center text-white shadow-lg transition ${recording ? "bg-red-600 animate-pulse" : "bg-sky-600 hover:bg-sky-700"}`}>
                {recording ? <MicOff size={30} /> : <Mic size={30} />}
              </button>
              <div className="text-xs text-slate-500 mt-2">{recording ? "Listening… tap to stop" : "Tap to speak"}</div>
              <button onClick={recording ? stopHDVoice : startHDVoice}
                className="mt-2 text-xs bg-violet-600 hover:bg-violet-700 text-white px-3 py-1.5 rounded-full font-semibold">
                {recording ? "Stop HD voice" : "🎙 HD voice (Whisper)"}
              </button>
              <div className="flex flex-wrap justify-center gap-1.5 mt-3">
                {SAMPLE_VOICE.map((s, i) => (
                  <button key={i} onClick={() => applyTranscript(s)} className="text-[11px] bg-white border border-slate-300 rounded-full px-2.5 py-1 hover:border-sky-500">
                    Sample voice {i + 1}
                  </button>
                ))}
              </div>
              {transcript && (
                <div className="mt-3 text-sm bg-white border border-slate-200 rounded-lg p-3 text-left">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Transcript</span>
                  <p>{transcript}</p>
                  <button onClick={() => applyTranscript(transcript)} className="mt-1 text-xs text-sky-700 font-semibold">Extract name / age / gender / concern →</button>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Field label="Name"><input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <Field label="Age"><input type="number" className={inputCls} value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} /></Field>
              <Field label="Gender">
                <select className={inputCls} value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
                  <option value="">—</option><option value="M">Male</option><option value="F">Female</option><option value="O">Other</option>
                </select>
              </Field>
              <Field label="Pain (0–10)"><input type="number" min="0" max="10" className={inputCls} value={form.pain} onChange={(e) => setForm({ ...form, pain: e.target.value })} /></Field>
            </div>
            <Field label="Concern (editable)">
              <textarea className={inputCls} rows={2} value={form.concern} onChange={(e) => setForm({ ...form, concern: e.target.value })} placeholder="e.g. chest pain since morning…" />
            </Field>
            <div className="flex items-center gap-3 flex-wrap">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.has_history} onChange={(e) => setForm({ ...form, has_history: e.target.checked })} />
                I have visited this hospital before (record on file)
              </label>
              <button type="button" onClick={findRecord} disabled={!form.name || looking}
                className="text-xs bg-slate-800 hover:bg-slate-900 disabled:opacity-40 text-white px-3 py-1.5 rounded-full font-semibold">
                {looking ? "Searching…" : "🔎 Find my previous record"}
              </button>
            </div>
            {welcome && !welcome.none && (
              <div className="text-sm bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                <b>Welcome back, {welcome.name}!</b> Last visit {String(welcome.last_visit).slice(0, 10)} — {welcome.concern}
                {welcome.specialty ? ` (${welcome.specialty})` : ""}. Record linked — triage confidence improves with history.
                <div className="text-[10px] text-slate-500 mt-1">Demo lookup by name. Production links via MRN/ABHA number through the hospital EHR — never name-matching.</div>
              </div>
            )}
            {welcome?.none && (
              <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-2">No previous record found — continuing as a first-time visit.</div>
            )}
            <button onClick={() => setStep(2)} disabled={!form.concern}
              className="w-full bg-sky-600 hover:bg-sky-700 disabled:opacity-40 text-white font-semibold rounded-xl py-3 flex items-center justify-center gap-1">
              Next: vitals check <ChevronRight size={16} />
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <VitalsCapture vitals={vitals} setVitals={setVitals} />
            <div className="flex gap-2">
              <button onClick={() => setStep(1)} className="flex-1 border border-slate-300 rounded-xl py-3 text-sm font-semibold">Back</button>
              <button onClick={() => setStep(3)} className="flex-1 bg-sky-600 hover:bg-sky-700 text-white font-semibold rounded-xl py-3">
                {vitals ? "Next: confirm" : "Skip (no devices) — AI will lower its confidence"}
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <Field label="How does the patient look? (patient or nurse ticks what applies)">
              <AppearancePicker value={appearance} onChange={setAppearance} />
            </Field>
            <div className="bg-slate-50 rounded-xl p-3 text-sm">
              <b>{form.name || "Walk-in"}</b> · {form.age || "?"}{form.gender || ""} · pain {form.pain}/10<br />
              <span className="text-slate-600">{form.concern}</span><br />
              <span className="text-xs text-slate-500">
                Vitals: {vitals ? `HR ${vitals.hr} · BP ${vitals.bp_sys}/${vitals.bp_dia} · SpO₂ ${vitals.spo2}% · ${vitals.temp}°C` : "not captured"} · Looks: {appearance.join(", ") || "—"}
              </span>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(2)} className="flex-1 border border-slate-300 rounded-xl py-3 text-sm font-semibold">Back</button>
              <button onClick={submit} disabled={busy} className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white font-semibold rounded-xl py-3">
                {busy ? "Submitting…" : "Submit to triage"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ================================ AMBULANCE ================================ */
function AmbulanceEntry({ onDone }) {
  const [form, setForm] = useState({ name: "", age: "", gender: "", concern: "", pain: 5 });
  const [vitals, setVitals] = useState(null);
  const [appearance, setAppearance] = useState([]);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await registerPatient({
        name: form.name || "Unknown patient", age: Number(form.age) || 40, gender: form.gender || "",
        concern: form.concern, pain: Number(form.pain) || 0, has_history: false,
        source: "ambulance", appearance, vitals: vitals || undefined,
      });
      onDone(r.triage);
      setForm({ name: "", age: "", gender: "", concern: "", pain: 5 }); setVitals(null); setAppearance([]);
    } catch { onDone({ category: "lower", specialty: "error — check backend" }); }
    finally { setBusy(false); }
  };

  return (
    <div className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm p-6">
      <div className="flex items-center gap-2 mb-1">
        <Ambulance className="text-red-600" size={20} />
        <h2 className="font-bold text-lg">Ambulance / pre-arrival entry</h2>
      </div>
      <p className="text-sm text-slate-500 mb-4">Crew or nurse enters details en route. The patient joins the queue before arriving — ambulance arrivals floor at Urgent minimum.</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <Field label="Name (or 'Unknown')"><input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Age (estimate ok)"><input type="number" className={inputCls} value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} /></Field>
        <Field label="Gender">
          <select className={inputCls} value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
            <option value="">—</option><option value="M">M</option><option value="F">F</option><option value="O">Other</option>
          </select>
        </Field>
        <Field label="Pain (0–10)"><input type="number" min="0" max="10" className={inputCls} value={form.pain} onChange={(e) => setForm({ ...form, pain: e.target.value })} /></Field>
      </div>
      <Field label="Chief complaint / mechanism">
        <textarea className={inputCls} rows={2} value={form.concern} onChange={(e) => setForm({ ...form, concern: e.target.value })} placeholder="e.g. road accident, bleeding from head, unconscious briefly…" />
      </Field>
      <div className="my-3"><VitalsCapture vitals={vitals} setVitals={setVitals} /></div>
      <Field label="Observed condition"><AppearancePicker value={appearance} onChange={setAppearance} /></Field>
      <button onClick={submit} disabled={!form.concern || busy}
        className="mt-4 w-full bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white font-semibold rounded-xl py-3">
        {busy ? "Dispatching…" : "Dispatch to ED queue"}
      </button>
    </div>
  );
}

/* ================================ NURSE ================================ */
function NurseView({ queue, showToast }) {
  const [sel, setSel] = useState(null);
  const [newCat, setNewCat] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const p = queue.find((x) => x.id === sel);

  const saveOverride = async () => {
    setBusy(true);
    try {
      await postOverride({ patient_id: p.id, to_category: newCat, reason });
      showToast("Override saved — recorded in audit; feeds nightly retraining");
      setReason("");
    } catch (e) { showToast(e?.response?.data?.detail || "Override failed"); }
    finally { setBusy(false); }
  };

  const worsenVitals = async () => {
    setBusy(true);
    try {
      const v = p.vitals || {};
      await postVitals(p.id, {
        hr: (v.hr ?? 90) + 15, bp_sys: v.bp_sys ?? 120, bp_dia: v.bp_dia ?? 78,
        spo2: Math.max(85, (v.spo2 ?? 97) - 4), temp: v.temp ?? 36.8,
      });
      showToast("New vitals recorded — patient automatically re-triaged");
    } catch { showToast("Failed — check backend"); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <div className="bg-white rounded-2xl shadow-sm p-4">
        <h2 className="font-bold flex items-center gap-2 mb-1"><UserCheck size={18} className="text-emerald-600" /> Nurse review queue</h2>
        <p className="text-xs text-slate-500 mb-3">Check the AI's work. Every override is audited and feeds the nightly model retraining.</p>
        <div className="divide-y divide-slate-100 max-h-[560px] overflow-y-auto">
          {queue.map((q) => (
            <button key={q.id} onClick={() => { setSel(q.id); setNewCat(q.category); setReason(""); }}
              className={`w-full text-left p-2.5 flex items-center gap-2 hover:bg-slate-50 ${sel === q.id ? "bg-sky-50" : ""}`}>
              <ConfidenceRing value={q.confidence} color={CAT_STYLE[q.category].ring} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold flex items-center gap-1.5">
                  {q.name} <span className="text-slate-400 font-normal">{q.age}{q.gender}</span>
                  {q.reassess_due && <RefreshCw size={13} className="text-amber-600" />}
                </div>
                <div className="text-xs text-slate-500 truncate">{q.concern}</div>
              </div>
              <CatBadge cat={q.category} escalated={q.escalated} />
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm p-4">
        {p ? (
          <>
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold">{p.name} · {p.age}{p.gender} {p.source === "ambulance" && "· 🚑"}</h3>
                <p className="text-sm text-slate-600">{p.concern}</p>
              </div>
              <CatBadge cat={p.category} escalated={p.escalated} />
            </div>
            <div className="mt-3 bg-slate-50 rounded-xl p-3 text-xs space-y-1 max-h-56 overflow-y-auto">
              <div className="font-bold text-slate-600 uppercase tracking-wider text-[10px]">
                Why the AI decided this (score {p.score}, confidence {Math.round(p.confidence * 100)}%, {p.model_version || "hybrid"})
              </div>
              {(p.reasons || []).map((r, i) => <div key={i} className="flex gap-1.5"><span className="text-sky-500">›</span>{r}</div>)}
            </div>
            <button onClick={worsenVitals} disabled={busy}
              className="mt-3 w-full border border-slate-300 hover:border-slate-500 text-sm font-semibold rounded-lg py-2.5 flex items-center justify-center gap-1">
              <RefreshCw size={14} /> Re-record vitals (demo: worsen) → auto re-triage
            </button>
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Override category</div>
              <div className="flex gap-2 mb-2">
                {CATS.map((c) => (
                  <button key={c} onClick={() => setNewCat(c)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${newCat === c ? `${CAT_STYLE[c].bg} text-white border-transparent` : "border-slate-300"}`}>
                    {CAT_LABEL[c]}
                  </button>
                ))}
              </div>
              <input className={inputCls} placeholder="Override reason (required — goes to audit log)" value={reason} onChange={(e) => setReason(e.target.value)} />
              <button disabled={!reason || newCat === p.category || busy} onClick={saveOverride}
                className="mt-2 w-full bg-slate-800 hover:bg-slate-900 disabled:opacity-40 text-white text-sm font-semibold rounded-lg py-2.5">
                Save override (audited · retrains model)
              </button>
            </div>
          </>
        ) : (
          <div className="text-center text-sm text-slate-400 py-16">Select a patient to review the AI's reasoning.</div>
        )}
      </div>
    </div>
  );
}

/* ================================ DOCTOR ================================ */
function HistoryPanel({ hist }) {
  if (!hist) return null;
  if (!hist.visits || hist.visits.length === 0) {
    return (
      <div className="mb-2 text-xs text-slate-500 bg-slate-50 rounded-lg p-2 flex items-center gap-1.5">
        <History size={13} className="text-slate-400" /> First recorded visit — no prior history on file.
      </div>
    );
  }
  return (
    <div className="mb-2 bg-violet-50 border border-violet-200 rounded-xl p-3">
      <div className="text-[10px] font-bold uppercase tracking-wider text-violet-700 mb-1 flex items-center gap-1">
        <History size={12} /> Previous visits · AI summary
      </div>
      <p className="text-xs text-slate-700 mb-2">{hist.summary}</p>
      <div className="space-y-1.5 max-h-44 overflow-y-auto">
        {hist.visits.map((v) => (
          <div key={v.id} className="text-xs bg-white border border-violet-100 rounded-lg p-2">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold">{v.when}</span>
              <span className="text-slate-500">· {v.specialty || "—"} · {CAT_LABEL[v.category] || v.category}</span>
              {v.related ? (
                <span className="text-[10px] bg-violet-600 text-white px-1.5 py-0.5 rounded-full font-bold"
                  title={v.matched_on?.length ? `Matched on: ${v.matched_on.join(", ")}` : ""}>
                  related to today
                </span>
              ) : (
                <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full font-semibold">unrelated</span>
              )}
            </div>
            <div className="text-slate-600 mt-0.5">{v.concern}</div>
            {v.override && <div className="text-[11px] text-amber-700 mt-0.5">Nurse override: {v.override}</div>}
            {v.prescription && <div className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">Rx: {v.prescription}</div>}
          </div>
        ))}
      </div>
      <div className="text-[10px] text-slate-400 mt-1.5">
        {hist.llm_used ? "Simplified by LLM (key detected) — facts only, never decides urgency." : "Deterministic digest — runs offline, fully auditable."}
        {" "}Linked by name for the demo; production links via MRN/ABHA through the EHR.
      </div>
    </div>
  );
}

function DoctorView({ queue, user, showToast }) {
  const [sel, setSel] = useState(null);
  const [rx, setRx] = useState("");
  const [busy, setBusy] = useState(false);
  const [hist, setHist] = useState(null);
  const list = user.dept ? queue.filter((p) => p.specialty === user.dept) : queue;
  const p = list.find((x) => x.id === sel);

  useEffect(() => {
    if (!sel) { setHist(null); return; }
    setHist(null);
    getHistory(sel).then(setHist).catch(() => setHist({ visits: [], summary: "", llm_used: false }));
  }, [sel]);

  const send = async () => {
    setBusy(true);
    try {
      await postPrescription({ patient_id: p.id, text: rx });
      showToast(`Prescription sent to ${p.name}'s phone`);
      setSel(null); setRx("");
    } catch (e) { showToast(e?.response?.data?.detail || "Failed — doctor role required"); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <div className="bg-white rounded-2xl shadow-sm p-4">
        <h2 className="font-bold flex items-center gap-2 mb-2"><Stethoscope size={18} className="text-sky-700" /> {user.display}</h2>
        <div className="text-xs bg-sky-50 text-sky-800 rounded-lg px-3 py-2 mb-3">
          {user.dept || "All departments"} console · {list.length} waiting · emergency cases first · {user.dept ? "you only see patients routed to your department" : "duty officer — covering every department, emergencies first across the board"}
        </div>
        <div className="divide-y divide-slate-100 max-h-[520px] overflow-y-auto">
          {list.length === 0 && <div className="p-4 text-xs text-slate-400">No waiting patients for {user.dept || "you"} right now.</div>}
          {list.map((q, i) => (
            <button key={q.id} onClick={() => { setSel(q.id); setRx(""); }}
              className={`w-full text-left p-2.5 flex items-center gap-2 hover:bg-slate-50 ${sel === q.id ? "bg-sky-50" : ""}`}>
              <span className="text-xs font-mono text-slate-400">#{i + 1}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold">{q.name} <span className="text-slate-400 font-normal">{q.age}{q.gender}</span></div>
                <div className="text-xs text-slate-500 truncate">{q.concern}</div>
              </div>
              <CatBadge cat={q.category} escalated={q.escalated} />
            </button>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-2xl shadow-sm p-4">
        {p ? (
          <>
            <h3 className="font-bold">{p.name} · {p.age}{p.gender}</h3>
            <div className="text-xs text-slate-500 mb-2">
              {p.specialty} · {CAT_LABEL[p.category]} · confidence {Math.round(p.confidence * 100)}% · est. wait {p.est_wait_min}m
            </div>
            <div className="bg-slate-50 rounded-xl p-3 text-sm mb-2">{p.concern}</div>
            <HistoryPanel hist={hist} />
            <div className="text-xs text-slate-600 mb-2">
              Vitals: {p.vitals ? `HR ${p.vitals.hr} · BP ${p.vitals.bp_sys}/${p.vitals.bp_dia} · SpO₂ ${p.vitals.spo2}% · ${p.vitals.temp}°C` : "none captured"}
            </div>
            <Field label="Online prescription">
              <textarea className={inputCls} rows={6} value={rx} onChange={(e) => setRx(e.target.value)}
                placeholder={"Diagnosis:\nRx:\n1. …\nAdvice / follow-up:"} />
            </Field>
            <button disabled={!rx || busy} onClick={send}
              className="mt-2 w-full bg-sky-700 hover:bg-sky-800 disabled:opacity-40 text-white font-semibold rounded-xl py-3 flex items-center justify-center gap-1.5">
              <FileText size={16} /> {busy ? "Sending…" : "Sign & send to patient's phone"}
            </button>
          </>
        ) : (
          <div className="text-center text-sm text-slate-400 py-16">Select a patient to consult and prescribe.</div>
        )}
      </div>
    </div>
  );
}

/* ================================ PATIENT PORTAL ================================ */
function BookingCard({ }) {
  const [book, setBook] = useState({ name: "", age: "", gender: "", concern: "", pain: 7 });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const submit = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await registerPatient({
        name: book.name, age: Number(book.age) || 40, gender: book.gender || "",
        concern: book.concern, pain: Number(book.pain) || 7, has_history: false,
        source: "online-booking", appearance: [],
      });
      setMsg(`Booked — triaged ${CAT_LABEL[r.triage.category]} (${r.triage.specialty}). The ED is expecting you.`);
      setBook({ name: "", age: "", gender: "", concern: "", pain: 7 });
    } catch { setMsg("Booking failed — check backend"); }
    finally { setBusy(false); }
  };
  return (
    <div className="bg-white rounded-2xl shadow-sm p-4">
      <h2 className="font-bold mb-1">Emergency pre-booking</h2>
      <p className="text-xs text-slate-500 mb-3">For very urgent cases: register from home / en route so the ED is ready when you arrive. Not a replacement for calling an ambulance.</p>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <Field label="Name"><input className={inputCls} value={book.name} onChange={(e) => setBook({ ...book, name: e.target.value })} /></Field>
        <Field label="Age"><input type="number" className={inputCls} value={book.age} onChange={(e) => setBook({ ...book, age: e.target.value })} /></Field>
        <Field label="Gender">
          <select className={inputCls} value={book.gender} onChange={(e) => setBook({ ...book, gender: e.target.value })}>
            <option value="">—</option><option value="M">M</option><option value="F">F</option>
          </select>
        </Field>
      </div>
      <Field label="What is happening?">
        <textarea className={inputCls} rows={2} value={book.concern} onChange={(e) => setBook({ ...book, concern: e.target.value })} placeholder="e.g. father has chest pain and is sweating, we are 15 min away" />
      </Field>
      <button disabled={!book.concern || !book.name || busy} onClick={submit}
        className="mt-3 w-full bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white font-semibold rounded-xl py-3">
        {busy ? "Booking…" : "Book emergency arrival"}
      </button>
      {msg && <div className="mt-2 text-xs font-semibold text-emerald-700">{msg}</div>}
      <div className="mt-3 text-[11px] text-slate-500 bg-slate-50 rounded-lg p-2.5">
        Privacy: encrypted in transit and at rest, role-based access, every view/edit audited. Jurisdiction: India (DPDP Act 2023) — swappable for HIPAA/GDPR.
      </div>
    </div>
  );
}

function PatientPortal({ queue, notifs }) {
  const [mode, setMode] = useState("waiting");   // "waiting" | "prescription"
  const [me, setMe] = useState(null);
  const [rxData, setRxData] = useState(null);
  const [done, setDone] = useState([]);          // completed visits

  useEffect(() => { getCompleted().then(setDone).catch(() => {}); }, [queue]);

  const list = mode === "waiting" ? queue : done;
  const p = list.find((x) => x.id === Number(me)) || null;
  const myNotifs = notifs.filter((n) => n.patient_id === Number(me));
  const pos = mode === "waiting" && p
    ? queue.filter((q) => q.specialty === p.specialty).findIndex((q) => q.id === p.id) + 1
    : 0;

  useEffect(() => {
    if (mode === "prescription" && p && !rxData) {
      getPrescription(p.id).then(setRxData).catch(() => {});
    }
  }, [mode, p, rxData]);

  const switchMode = (m) => { setMode(m); setMe(null); setRxData(null); };

  const downloadPDF = () => {
    if (!rxData || !p) return;
    const doc = new jsPDF();
    doc.setFontSize(16); doc.text("PatientTriage.ai — e-Prescription", 20, 20);
    doc.setFontSize(11);
    doc.text(`Patient: ${p.name} (${p.age}${p.gender})    Doctor: ${rxData.doctor}`, 20, 32);
    doc.text(`Issued: ${rxData.at}`, 20, 39);
    doc.text(doc.splitTextToSize(`Concern: ${p.concern}`, 170), 20, 49);
    doc.text(doc.splitTextToSize(rxData.text, 170), 20, 62);
    doc.setFontSize(9);
    doc.text("Digitally signed - Logged in the hospital audit trail", 20, 285);
    doc.save(`prescription-${p.name.replace(/\s+/g, "-")}.pdf`);
  };

  return (
    <div className="grid lg:grid-cols-2 gap-4">
    <div className="bg-white rounded-2xl shadow-sm p-4">
      <h2 className="font-bold flex items-center gap-2 mb-2"><User size={18} className="text-violet-600" /> My visit (patient phone view)</h2>

      {/* mode switch: waiting vs prescription */}
      <div className="flex rounded-xl overflow-hidden border border-slate-300 text-sm font-semibold mb-3">
        {[["waiting", "⏳ I'm waiting"], ["prescription", "💊 My prescription"]].map(([k, label]) => (
          <button key={k} onClick={() => switchMode(k)}
            className={`flex-1 py-2.5 ${mode === k ? "bg-violet-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
            {label}
          </button>
        ))}
      </div>

      <Field label={mode === "waiting" ? "Demo: pick which waiting patient you are" : "Demo: pick your completed visit"}>
        <select className={inputCls} value={me ?? ""} onChange={(e) => { setMe(e.target.value); setRxData(null); }}>
          <option value="">—</option>
          {list.map((t) => <option key={t.id} value={t.id}>{mode === "prescription" ? "✓ " : ""}{t.name} ({t.age}{t.gender})</option>)}
        </select>
      </Field>
      {mode === "prescription" && list.length === 0 && (
        <p className="mt-2 text-xs text-slate-400">No completed consultations yet — once a doctor signs a prescription, the visit appears here.</p>
      )}

      {p && mode === "waiting" && (
        <div className="mt-3 space-y-3">
          <div className={`rounded-xl p-4 ${CAT_STYLE[p.category].light}`}>
            <div className="flex items-center justify-between">
              <CatBadge cat={p.category} escalated={p.escalated} />
              <ConfidenceRing value={p.confidence} color={CAT_STYLE[p.category].ring} />
            </div>
            <div className="mt-2 text-sm">
              <div className="font-semibold">Queue position: #{pos} in {p.specialty}</div>
              <div className="text-slate-600 flex items-center gap-1 mt-0.5">
                <Clock size={13} /> Estimated wait: <b>{p.est_wait_min} min</b> · waited {p.waited_min} min
              </div>
              <div className="text-[11px] text-slate-500 mt-1">Updates live. If your condition worsens, tell the desk immediately — you'll be re-assessed.</div>
            </div>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1"><Bell size={13} /> Notifications</div>
            {myNotifs.length === 0 ? <p className="text-xs text-slate-400">No notifications yet.</p> :
              myNotifs.map((n, i) => (
                <div key={i} className="text-sm bg-violet-50 border border-violet-200 rounded-lg p-2.5 mb-1.5">
                  <span className="text-[10px] text-violet-400 font-mono mr-2">{n.at}</span>{n.text}
                </div>
              ))}
          </div>
        </div>
      )}

      {p && mode === "prescription" && (
        <div className="mt-3 space-y-3">
          <div className="rounded-xl p-4 bg-emerald-50 border border-emerald-200">
            <div className="text-sm font-semibold text-slate-700 flex items-center gap-1">
              <ShieldCheck size={15} className="text-emerald-600" /> Consultation complete — {p.specialty}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">{p.concern}</div>
          </div>
          {rxData ? (
            <div className="border border-slate-200 rounded-xl p-3">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Prescription · {rxData.doctor}</div>
              <pre className="text-xs whitespace-pre-wrap bg-slate-50 rounded-lg p-2 mb-2">{rxData.text}</pre>
              <button onClick={downloadPDF} className="w-full bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg py-2.5 flex items-center justify-center gap-1.5">
                <Download size={15} /> Download prescription (PDF)
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-400">Fetching your prescription…</p>
          )}
        </div>
      )}
    </div>
    <BookingCard />
    </div>
  );
}

/* ================================ AUDIT ================================ */
function AuditView({ rows }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm p-4 max-w-4xl mx-auto">
      <h2 className="font-bold flex items-center gap-2 mb-1"><ClipboardList size={18} /> Audit trail</h2>
      <p className="text-xs text-slate-500 mb-3">Append-only. Every registration, AI decision, override, vitals re-check, surge and prescription — with actor and time.</p>
      <div className="space-y-1.5 max-h-[560px] overflow-y-auto font-mono text-xs">
        {rows.map((a, i) => (
          <div key={i} className="flex gap-2 border-b border-slate-100 pb-1.5">
            <span className="text-slate-400 shrink-0 w-36 truncate">{a.at}</span>
            <span className="text-sky-700 shrink-0 w-32 truncate">{a.actor}</span>
            <span className="text-amber-700 shrink-0 w-20">{a.action}</span>
            <span className="text-slate-700">{a.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
