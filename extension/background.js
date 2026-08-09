const DEFAULT_API = "https://clip-queue-web-production.up.railway.app";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "kyro-save",
    title: "Сохранить в Kyro",
    contexts: ["link", "page", "video"],
    documentUrlPatterns: ["https://www.youtube.com/*", "https://youtu.be/*"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "kyro-save") return;
  const url = info.linkUrl || info.pageUrl || (tab && tab.url) || "";
  await saveUrl(url);
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "kyro-save") {
    saveUrl(msg.url || "")
      .then((r) => sendResponse(r))
      .catch((e) => sendResponse({ ok: false, error: String(e.message || e) }));
    return true;
  }
  return false;
});

async function getConfig() {
  const st = await chrome.storage.sync.get(["apiBase", "token"]);
  return {
    apiBase: (st.apiBase || DEFAULT_API).replace(/\/$/, ""),
    token: st.token || "",
  };
}

async function saveUrl(url) {
  const { apiBase, token } = await getConfig();
  if (!token) {
    return { ok: false, error: "Сначала войдите в Kyro на сайте и вставьте токен в расширении" };
  }
  if (!/youtu(\.be|be\.com)/i.test(url || "")) {
    return { ok: false, error: "Откройте страницу YouTube" };
  }
  const res = await fetch(`${apiBase}/api/videos/save`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      url,
      source: "chrome_extension",
      apply_classification: true,
      classify_async: true,
      status: "queue",
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { ok: false, error: data.error || `HTTP ${res.status}` };
  }
  const folder =
    (data.classified_into && data.classified_into[0] && data.classified_into[0].list_title) ||
    "";
  return {
    ok: true,
    title: (data.item && data.item.title) || "Сохранено",
    folder,
  };
}
