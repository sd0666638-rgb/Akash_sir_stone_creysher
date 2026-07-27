import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("stone_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function downloadBlob(path, filename) {
  const response = await api.get(path, { responseType: "blob" });
  const blob = new Blob([response.data], {
    type: response.headers["content-type"] || "application/octet-stream",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const disposition = response.headers["content-disposition"] || "";
  const headerFilename = disposition.match(/filename="?([^"]+)"?/i)?.[1];
  anchor.href = url;
  anchor.download = filename || headerFilename || "document.pdf";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function printPdf(path) {
  const response = await api.get(path, { responseType: "blob" });
  const blob = new Blob([response.data], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const frame = document.createElement("iframe");
  frame.title = "Invoice print preview";
  frame.style.position = "fixed";
  frame.style.width = "1px";
  frame.style.height = "1px";
  frame.style.right = "0";
  frame.style.bottom = "0";
  frame.style.border = "0";

  function cleanup() {
    frame.remove();
    URL.revokeObjectURL(url);
  }

  frame.addEventListener(
    "load",
    () => {
      window.setTimeout(() => {
        frame.contentWindow?.focus();
        frame.contentWindow?.print();
        window.setTimeout(cleanup, 60_000);
      }, 250);
    },
    { once: true }
  );
  frame.src = url;
  document.body.appendChild(frame);
}

export default api;
