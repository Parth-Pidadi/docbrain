import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

export const uploadDocument = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/api/upload/", form);
};

export const extractDocument = (docId) =>
  api.post(`/api/extract/${docId}`);

export const askQuestion = (question, docIds = null) =>
  api.post("/api/qa/", { question, doc_ids: docIds });

export default api;
