const DEFAULT_API = "https://clip-queue-web-production.up.railway.app";

async function load() {
  const st = await chrome.storage.sync.get(["apiBase", "token"]);
  document.getElementById("api").value = st.apiBase || DEFAULT_API;
  document.getElementById("token").value = st.token || "";
}

document.getElementById("persist").onclick = async () => {
  await chrome.storage.sync.set({
    apiBase: document.getElementById("api").value.trim() || DEFAULT_API,
    token: document.getElementById("token").value.trim(),
  });
  const out = document.getElementById("out");
  out.className = "ok";
  out.textContent = "Сохранено";
};

document.getElementById("save").onclick = async () => {
  await chrome.storage.sync.set({
    apiBase: document.getElementById("api").value.trim() || DEFAULT_API,
    token: document.getElementById("token").value.trim(),
  });
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const out = document.getElementById("out");
  const r = await chrome.runtime.sendMessage({ type: "kyro-save", url: tab && tab.url });
  if (r && r.ok) {
    out.className = "ok";
    out.textContent = r.folder ? `${r.title} → ${r.folder}` : r.title || "Сохранено в Kyro";
  } else {
    out.className = "err";
    out.textContent = (r && r.error) || "Не удалось сохранить";
  }
};

load();
