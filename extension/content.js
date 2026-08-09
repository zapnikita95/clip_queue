(function () {
  if (window.__kyroExt) return;
  window.__kyroExt = true;

  function ensureBtn() {
    if (!location.pathname.startsWith("/watch")) return;
    if (document.getElementById("kyro-save-btn")) return;
    const host =
      document.querySelector("#top-level-buttons-computed") ||
      document.querySelector("#actions") ||
      document.querySelector("#menu-container");
    if (!host) return;
    const btn = document.createElement("button");
    btn.id = "kyro-save-btn";
    btn.type = "button";
    btn.textContent = "В Kyro";
    btn.style.cssText =
      "margin-left:8px;padding:8px 12px;border-radius:18px;border:0;background:#e85d4c;color:#fff;font:600 13px/1 system-ui;cursor:pointer";
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = "…";
      try {
        const r = await chrome.runtime.sendMessage({ type: "kyro-save", url: location.href });
        btn.textContent = r && r.ok ? "В Kyro ✓" : "Ошибка";
        if (r && r.ok) setTimeout(() => { btn.textContent = "В Kyro"; btn.disabled = false; }, 2000);
        else btn.disabled = false;
      } catch (_) {
        btn.textContent = "Ошибка";
        btn.disabled = false;
      }
    };
    host.prepend(btn);
  }

  ensureBtn();
  const obs = new MutationObserver(() => ensureBtn());
  obs.observe(document.documentElement, { childList: true, subtree: true });
})();
