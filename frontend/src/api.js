// All communication with the FastAPI backend lives in this one file.
import axios from "axios";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const api = axios.create({ baseURL: BASE });

export function setToken(token) {
  api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

export const login = (username, password) =>
  api.post("/auth/login", { username, password }).then((r) => r.data);
export const getQueue = () => api.get("/queue").then((r) => r.data);
export const registerPatient = (p) => api.post("/patients", p).then((r) => r.data);
export const postVitals = (id, v) => api.post(`/patients/${id}/vitals`, v).then((r) => r.data);
export const postOverride = (o) => api.post("/overrides", o).then((r) => r.data);
export const postPrescription = (rx) => api.post("/prescriptions", rx).then((r) => r.data);
export const getPrescription = (id) => api.get(`/prescriptions/${id}`).then((r) => r.data);
export const getAudit = () => api.get("/audit").then((r) => r.data);
export const triggerSurge = () => api.post("/patients/demo/surge").then((r) => r.data);

// Live updates: server pushes {event, data}; we hand every message to the app.
export function connectWS(onEvent, onStatus) {
  const url = BASE.replace(/^http/, "ws") + "/ws/queue";
  const ws = new WebSocket(url);
  ws.onopen = () => onStatus?.(true);
  ws.onclose = () => onStatus?.(false);
  ws.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)); } catch { /* ignore malformed */ }
  };
  return ws;
}