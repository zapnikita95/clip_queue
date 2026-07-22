(() => {
  const TOKEN_KEY = "cq_session_token";
  const $ = (sel, root = document) => root.querySelector(sel);
  const app = $("#app");
  const toastEl = $("#toast");
  let me = null;
  let toastTimer = null;

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(t) {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  }

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    const t = token();
    if (t) headers.Authorization = `Bearer ${t}`;
    const res = await fetch(path, { ...opts, headers, credentials: "include" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.error || `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 2800);
  }

  // --- Undo bar (Gmail-style) ---
  let undoTick = null;
  let undoPending = null;

  function ensureUndoBar() {
    let bar = $("#undo-bar");
    if (bar) return bar;
    bar = document.createElement("div");
    bar.id = "undo-bar";
    bar.className = "undo-bar hidden";
    bar.innerHTML = `
      <span class="undo-msg"></span>
      <span class="undo-count"></span>
      <button type="button" class="undo-btn" id="undo-action">Отменить</button>
      <button type="button" class="undo-x" id="undo-dismiss" aria-label="Закрыть">×</button>`;
    document.body.appendChild(bar);
    return bar;
  }

  function commitPendingUndo() {
    if (!undoPending) return;
    const p = undoPending;
    undoPending = null;
    clearInterval(undoTick);
    undoTick = null;
    const bar = $("#undo-bar");
    if (bar) bar.classList.add("hidden");
    try { p.onCommit && p.onCommit(); } catch (_) {}
  }

  function showUndo({ message, seconds = 8, onUndo, onCommit }) {
    // Previous pending action commits immediately
    commitPendingUndo();
    toastEl.classList.add("hidden");
    const bar = ensureUndoBar();
    const msg = bar.querySelector(".undo-msg");
    const cnt = bar.querySelector(".undo-count");
    let left = seconds;
    msg.textContent = message;
    cnt.textContent = `${left}с`;
    bar.classList.remove("hidden");
    undoPending = { onUndo, onCommit };
    clearInterval(undoTick);
    undoTick = setInterval(() => {
      left -= 1;
      cnt.textContent = `${left}с`;
      if (left <= 0) commitPendingUndo();
    }, 1000);
    $("#undo-action").onclick = () => {
      const p = undoPending;
      undoPending = null;
      clearInterval(undoTick);
      undoTick = null;
      bar.classList.add("hidden");
      try { p && p.onUndo && p.onUndo(); } catch (_) {}
    };
    $("#undo-dismiss").onclick = () => commitPendingUndo();
  }

  const LEXICON_SNOOZE_KEY = "cq_lexicon_snooze_until";

  function lexiconSnoozed() {
    const until = Number(localStorage.getItem(LEXICON_SNOOZE_KEY) || 0);
    return until > Date.now();
  }

  function setLexiconSnooze(msOrForever) {
    if (msOrForever === "forever") {
      localStorage.setItem(LEXICON_SNOOZE_KEY, String(Date.now() + 1000 * 60 * 60 * 24 * 365 * 50));
      return;
    }
    localStorage.setItem(LEXICON_SNOOZE_KEY, String(Date.now() + Number(msOrForever)));
  }

  function openLexiconPrompt(videoId, { note = "", title = "" } = {}) {
    if (lexiconSnoozed()) return;
    let sheet = $("#note-sheet-global");
    if (sheet) sheet.remove();
    sheet = document.createElement("div");
    sheet.id = "note-sheet-global";
    sheet.className = "note-sheet";
    sheet.innerHTML = `
      <div class="note-sheet-card">
        <b>Как бы ты описал этот видос?</b>
        ${title ? `<div class="muted" style="margin-top:4px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(title)}</div>` : ""}
        <p class="muted" style="margin:8px 0 10px;font-size:13px">Своими словами — потом поиск поймёт «стрёмную хрень» или «уют на вечер».</p>
        <textarea id="watch-note" rows="2" placeholder="уют на вечер / ржака не стендап / …">${escapeHtml(note)}</textarea>
        <div class="btn-row" style="margin-top:12px;flex-wrap:wrap">
          <button type="button" class="btn" id="watch-note-save">Сохранить</button>
          <button type="button" class="btn ghost" id="watch-note-skip">Пропустить</button>
        </div>
        <div class="lexicon-snooze">
          <label class="muted" for="lexicon-snooze-sel">Не спрашивать</label>
          <select id="lexicon-snooze-sel">
            <option value="">сейчас спросить</option>
            <option value="3600000">час</option>
            <option value="86400000">день</option>
            <option value="604800000">неделю</option>
            <option value="1209600000">2 недели</option>
            <option value="forever">никогда</option>
          </select>
        </div>
      </div>`;
    document.body.appendChild(sheet);
    const close = () => sheet.remove();
    sheet.addEventListener("click", (e) => { if (e.target === sheet) close(); });
    $("#watch-note-skip").onclick = () => {
      const v = $("#lexicon-snooze-sel")?.value;
      if (v === "forever") setLexiconSnooze("forever");
      else if (v) setLexiconSnooze(Number(v));
      close();
    };
    $("#watch-note-save").onclick = async () => {
      const text = ($("#watch-note")?.value || "").trim();
      const v = $("#lexicon-snooze-sel")?.value;
      if (v === "forever") setLexiconSnooze("forever");
      else if (v) setLexiconSnooze(Number(v));
      if (text) {
        try {
          await api(`/api/library/${encodeURIComponent(videoId)}`, {
            method: "PATCH",
            body: JSON.stringify({ note: text }),
          });
          toast("Запомнил твои слова");
        } catch (e) {
          toast(e.message);
        }
      }
      close();
    };
    requestAnimationFrame(() => $("#watch-note")?.focus());
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtSec(s) {
    const n = Math.max(0, Math.round(Number(s) || 0));
    if (n < 60) return `${n} сек`;
    const m = Math.floor(n / 60);
    const r = n % 60;
    return r ? `${m} мин ${r} сек` : `${m} мин`;
  }

  function mountProgress(el, { title = "Работаю…", detail = "" } = {}) {
    if (!el) return null;
    el.innerHTML = `
      <div class="progress-box" data-progress>
        <div class="progress-head">
          <div class="progress-spin" aria-hidden="true"></div>
          <div class="progress-copy">
            <div class="progress-title">${escapeHtml(title)}</div>
            <div class="progress-detail">${escapeHtml(detail)}</div>
          </div>
          <div class="progress-meta">
            <div class="progress-pct">0%</div>
            <div class="progress-eta">считаю время…</div>
          </div>
        </div>
        <div class="progress-bar"><i style="width:2%"></i></div>
        <ul class="progress-log"></ul>
      </div>`;
    return el.querySelector("[data-progress]");
  }

  function updateProgress(box, ev = {}) {
    if (!box) return;
    const pct = Math.max(0, Math.min(100, Number(ev.pct) || 0));
    const title = ev.title || "Работаю…";
    const detail = ev.detail || "";
    box.querySelector(".progress-title").textContent = title;
    box.querySelector(".progress-detail").textContent = detail;
    box.querySelector(".progress-pct").textContent = `${Math.round(pct)}%`;
    const bar = box.querySelector(".progress-bar > i");
    if (bar) bar.style.width = `${Math.max(2, pct)}%`;
    let etaText = "считаю время…";
    if (ev.eta_sec != null && pct < 100) etaText = `ещё ~${fmtSec(ev.eta_sec)}`;
    else if (pct >= 100) etaText = ev.elapsed_sec != null ? `готово за ${fmtSec(ev.elapsed_sec)}` : "готово";
    else if (ev.elapsed_sec != null) etaText = `уже ${fmtSec(ev.elapsed_sec)}`;
    box.querySelector(".progress-eta").textContent = etaText;
    if (detail || title) {
      const log = box.querySelector(".progress-log");
      if (log && (!log.dataset.last || log.dataset.last !== `${title}|${detail}`)) {
        log.dataset.last = `${title}|${detail}`;
        const li = document.createElement("li");
        li.textContent = detail ? `${title} — ${detail}` : title;
        log.prepend(li);
        while (log.children.length > 8) log.lastChild.remove();
      }
    }
  }

  function finishProgress(box, { ok = true, title, detail, pct = 100, elapsed_sec } = {}) {
    if (!box) return;
    box.classList.toggle("done", ok);
    box.classList.toggle("error", !ok);
    updateProgress(box, {
      pct,
      title: title || (ok ? "Готово" : "Ошибка"),
      detail: detail || "",
      eta_sec: 0,
      elapsed_sec,
    });
  }

  /** Fake stepped progress while a non-streaming request runs */
  function runBusySteps(box, steps, promise) {
    let i = 0;
    const t0 = Date.now();
    const tick = () => {
      const step = steps[Math.min(i, steps.length - 1)];
      const pct = Math.min(92, 8 + Math.round((i / Math.max(1, steps.length)) * 84));
      const elapsed = (Date.now() - t0) / 1000;
      const remain = Math.max(2, (steps.length - i) * 2.2);
      updateProgress(box, {
        pct,
        title: step.title,
        detail: step.detail || "",
        elapsed_sec: elapsed,
        eta_sec: remain,
      });
      i += 1;
    };
    tick();
    const timer = setInterval(tick, 900);
    return promise.finally(() => clearInterval(timer));
  }

  async function streamNdjson(path, { method = "POST", body = "{}", onEvent } = {}) {
    const headers = { "Content-Type": "application/json", Accept: "application/x-ndjson" };
    const t = token();
    if (t) headers.Authorization = `Bearer ${t}`;
    const res = await fetch(path, { method, headers, body });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let last = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n");
      buf = parts.pop() || "";
      for (const line of parts) {
        const s = line.trim();
        if (!s) continue;
        let ev;
        try { ev = JSON.parse(s); } catch (_) { continue; }
        last = ev;
        if (onEvent) onEvent(ev);
      }
    }
    if (buf.trim()) {
      try {
        last = JSON.parse(buf.trim());
        if (onEvent) onEvent(last);
      } catch (_) {}
    }
    return last;
  }

  function tagPillsHtml(tags, { removable = false, videoId = "" } = {}) {
    if (!tags?.length) return `<span class="muted" style="font-size:13px">Тегов пока нет</span>`;
    return tags.map((t) => {
      const label = `${t.emoji ? t.emoji + " " : ""}${t.name}`;
      if (removable && videoId) {
        return `<button type="button" class="tag-pill tag-pill-btn" data-untag="${t.id}" title="Снять тег">${escapeHtml(label)} ×</button>`;
      }
      return `<span class="tag-pill">${escapeHtml(label)}</span>`;
    }).join("");
  }

  function watchUrl(item) {
    return item.watch_url || `https://www.youtube.com/watch?v=${item.video_id}`;
  }

  function cardMenuHtml(item, { listId = "", draftFolder = false } = {}) {
    return `
      <div class="card-menu">
        <button type="button" class="card-menu-btn" data-menu-toggle aria-label="Ещё">⋯</button>
        <div class="card-menu-pop hidden">
          <button type="button" data-act="boost2">Очень интересно</button>
          <button type="button" data-act="boost1">Интересно</button>
          <button type="button" data-act="boost0">Обычный интерес</button>
          <button type="button" data-act="boost_down">Менее интересно</button>
          <button type="button" data-act="watched">Просмотрено</button>
          ${listId ? `<button type="button" data-act="remove-cat">Убрать из категории</button>` : ""}
          ${draftFolder ? `<button type="button" data-act="remove-draft">Убрать из категории</button>` : ""}
          <button type="button" data-act="dismiss" class="danger">Удалить из Clip Queue</button>
        </div>
      </div>`;
  }

  function cardHtml(item, opts = {}) {
    const listId = opts.listId || "";
    const dur = item.duration_label ? `<span class="badge">${escapeHtml(item.duration_label)}</span>` : "";
    const boost = Number(item.interest || 0);
    const boostMark = boost >= 2 ? "🔥🔥" : boost === 1 ? "🔥" : boost < 0 ? "↓" : "";
    const pills = (item.user_tags || []).slice(0, 3).map((t) =>
      `<span class="tag-pill tag-pill-sm">${escapeHtml((t.emoji || "") + " " + t.name)}</span>`
    ).join("");
    return `
      <div class="card" data-video-id="${escapeHtml(item.video_id)}" data-list-id="${escapeHtml(String(listId || ""))}">
        ${cardMenuHtml(item, { listId })}
        <a class="card-main" href="/v/${encodeURIComponent(item.video_id)}" data-nav draggable="false">
          <div class="card-thumb">
            <img src="${escapeHtml(item.thumb_url)}" alt="" loading="lazy" draggable="false" />
            <button type="button" class="thumb-eye" data-act="watched" title="Просмотрено" aria-label="Просмотрено">👁</button>
            ${dur}
            ${boostMark ? `<span class="card-boost">${boostMark}</span>` : ""}
          </div>
          <div class="card-body">
            <h3 class="card-title">${escapeHtml(item.title)}</h3>
            <div class="card-meta">${escapeHtml(item.channel_title || "YouTube")}</div>
            ${pills ? `<div class="card-tags">${pills}</div>` : ""}
          </div>
        </a>
        <div class="card-actions">
          <a class="btn play-btn" href="${escapeHtml(watchUrl(item))}" target="_blank" rel="noopener" title="Смотреть на YouTube" draggable="false">▶</a>
        </div>
      </div>`;
  }

  function hideCardOptimistic(videoId, listId) {
    const sel = listId
      ? `.card[data-video-id="${CSS.escape(videoId)}"][data-list-id="${CSS.escape(String(listId))}"]`
      : `.card[data-video-id="${CSS.escape(videoId)}"]`;
    const nodes = [...document.querySelectorAll(sel)];
    nodes.forEach((el) => {
      el.dataset.undoHidden = "1";
      el.style.display = "none";
    });
    return () => {
      nodes.forEach((el) => {
        el.style.display = "";
        delete el.dataset.undoHidden;
      });
    };
  }

  async function runCardAction(act, videoId, listId, meta = {}) {
    if (!videoId || !act) return;
    try {
      if (act === "boost1" || act === "boost2" || act === "boost0" || act === "boost_down") {
        const level = act === "boost2" ? 2 : act === "boost1" ? 1 : act === "boost_down" ? -1 : 0;
        await api(`/api/library/${encodeURIComponent(videoId)}`, {
          method: "PATCH",
          body: JSON.stringify({ interest: level }),
        });
        const labels = {
          2: "Очень интересно — выше в теме",
          1: "Интересно",
          0: "Обычный интерес",
          [-1]: "Менее интересно — ниже в теме",
        };
        toast(labels[level] || "Ок");
        // Soft visual: refresh boost marks without full reload
        document.querySelectorAll(`.card[data-video-id="${CSS.escape(videoId)}"] .card-boost`).forEach((el) => el.remove());
        if (level >= 1) {
          document.querySelectorAll(`.card[data-video-id="${CSS.escape(videoId)}"] .card-thumb`).forEach((thumb) => {
            const span = document.createElement("span");
            span.className = "card-boost";
            span.textContent = level >= 2 ? "🔥🔥" : "🔥";
            thumb.appendChild(span);
          });
        }
      } else if (act === "watched") {
        const restore = hideCardOptimistic(videoId, listId);
        const title = meta.title || "";
        showUndo({
          message: "Просмотрено",
          seconds: 8,
          onUndo: restore,
          onCommit: async () => {
            try {
              await api(`/api/library/${encodeURIComponent(videoId)}`, {
                method: "PATCH",
                body: JSON.stringify({ status: "watched" }),
              });
              document.querySelectorAll(`.card[data-video-id="${CSS.escape(videoId)}"]`).forEach((el) => el.remove());
              openLexiconPrompt(videoId, { title });
            } catch (e) {
              restore();
              toast(e.message);
            }
          },
        });
      } else if (act === "dismiss") {
        const restore = hideCardOptimistic(videoId, listId);
        showUndo({
          message: "Удалено из Clip Queue",
          seconds: 8,
          onUndo: restore,
          onCommit: async () => {
            try {
              await api(`/api/library/${encodeURIComponent(videoId)}`, {
                method: "PATCH",
                body: JSON.stringify({ status: "dismissed" }),
              });
              document.querySelectorAll(`.card[data-video-id="${CSS.escape(videoId)}"]`).forEach((el) => el.remove());
            } catch (e) {
              restore();
              toast(e.message);
            }
          },
        });
      } else if (act === "remove-cat" && listId) {
        const restore = hideCardOptimistic(videoId, listId);
        showUndo({
          message: "Убрано из категории",
          seconds: 8,
          onUndo: restore,
          onCommit: async () => {
            try {
              await api(`/api/lists/${encodeURIComponent(listId)}/items/${encodeURIComponent(videoId)}`, {
                method: "DELETE",
              });
              document.querySelectorAll(
                `.card[data-video-id="${CSS.escape(videoId)}"][data-list-id="${CSS.escape(String(listId))}"]`
              ).forEach((el) => el.remove());
            } catch (e) {
              restore();
              toast(e.message);
            }
          },
        });
      } else if (act === "remove-draft") {
        // organize draft — just hide with undo that reloads parent paint if needed
        const card = document.querySelector(`.card[data-video-id="${CSS.escape(videoId)}"]`);
        if (card) {
          const restore = hideCardOptimistic(videoId, listId);
          showUndo({
            message: "Убрано из черновика",
            seconds: 6,
            onUndo: restore,
            onCommit: () => {
              card.remove();
              card.dispatchEvent(new CustomEvent("cq-draft-remove", { bubbles: true, detail: { videoId } }));
            },
          });
        }
      }
    } catch (e) {
      toast(e.message);
    }
  }

  function closeAllCardMenus() {
    document.querySelectorAll(".card-menu-pop").forEach((p) => p.classList.add("hidden"));
  }

  function wireCardMenus(root = document) {
    root.querySelectorAll(".card").forEach((card) => {
      if (card.dataset.wired === "1") return;
      card.dataset.wired = "1";
      const vid = card.getAttribute("data-video-id");
      const listId = card.getAttribute("data-list-id") || "";
      const title = card.querySelector(".card-title")?.textContent || "";
      const toggle = card.querySelector("[data-menu-toggle]");
      const pop = card.querySelector(".card-menu-pop");
      if (toggle && pop) {
        toggle.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          const wasOpen = !pop.classList.contains("hidden");
          closeAllCardMenus();
          if (!wasOpen) pop.classList.remove("hidden");
        };
      }
      card.querySelectorAll("[data-act]").forEach((btn) => {
        btn.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (pop) pop.classList.add("hidden");
          runCardAction(btn.getAttribute("data-act"), vid, listId, { title });
        };
      });
    });
  }

  // Click outside closes ⋯ menus
  if (!window.__cqMenuOutside) {
    window.__cqMenuOutside = true;
    document.addEventListener("click", (e) => {
      if (e.target.closest(".card-menu")) return;
      closeAllCardMenus();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeAllCardMenus();
    });
  }

  function topbar(active) {
    const name = me?.name || me?.email || "";
    return `
      <header class="topbar">
        <a class="brand" href="/home" data-nav>
          <div class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#fff" d="M8.2 5.4v13.2l11-6.6-11-6.6z"/></svg>
          </div>
          <div class="brand-name">Clip Queue</div>
        </a>
        <form class="smart-search" id="smart-search" action="/search" method="get">
          <input type="search" name="q" id="smart-q" placeholder="Что хочешь посмотреть?" autocomplete="off" enterkeyhint="search" />
          <button type="button" class="smart-mic" id="smart-mic" title="Голосом" aria-label="Голосом">🎤</button>
          <button type="submit" class="smart-go" title="Найти">⌕</button>
        </form>
        <nav class="nav">
          <button class="nav-btn ${active === "home" ? "active" : ""}" data-route="/home">Главная</button>
          <button class="nav-btn ${active === "queue" ? "active" : ""}" data-route="/queue">Очередь</button>
          <button class="nav-btn ${active === "channels" ? "active" : ""}" data-route="/channels">Каналы</button>
          <button class="nav-btn ${active === "settings" ? "active" : ""}" data-route="/settings">Настройки</button>
          <button class="nav-btn" id="logout-btn" title="${escapeHtml(name)}">Выйти</button>
        </nav>
      </header>
      <button type="button" class="fab-add" id="fab-add" title="Добавить видео">+</button>`;
  }

  function wireSmartSearch() {
    const form = $("#smart-search");
    if (!form || form.dataset.wired === "1") return;
    form.dataset.wired = "1";
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = ($("#smart-q")?.value || "").trim();
      if (!q) return toast("Напиши, что ищешь");
      navigate(`/search?q=${encodeURIComponent(q)}`);
    });
    const mic = $("#smart-mic");
    if (mic) {
      mic.onclick = async () => {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SR) {
          const rec = new SR();
          rec.lang = "ru-RU";
          rec.interimResults = false;
          mic.classList.add("listening");
          toast("Слушаю…");
          rec.onresult = (ev) => {
            const text = (ev.results?.[0]?.[0]?.transcript || "").trim();
            if (text && $("#smart-q")) $("#smart-q").value = text;
            mic.classList.remove("listening");
            if (text) navigate(`/search?q=${encodeURIComponent(text)}`);
          };
          rec.onerror = () => {
            mic.classList.remove("listening");
            toast("Не расслышал — попробуй ещё");
          };
          rec.onend = () => mic.classList.remove("listening");
          try { rec.start(); } catch (_) { mic.classList.remove("listening"); }
          return;
        }
        // Fallback: record short clip → Whisper API
        if (!navigator.mediaDevices?.getUserMedia) {
          return toast("Голос в этом браузере недоступен");
        }
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const rec = new MediaRecorder(stream);
          const chunks = [];
          rec.ondataavailable = (e) => chunks.push(e.data);
          mic.classList.add("listening");
          toast("Запись 5 сек…");
          rec.start();
          await new Promise((r) => setTimeout(r, 5000));
          rec.stop();
          stream.getTracks().forEach((t) => t.stop());
          await new Promise((r) => { rec.onstop = r; });
          const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
          const fd = new FormData();
          fd.append("audio", blob, "voice.webm");
          const headers = {};
          const t = token();
          if (t) headers.Authorization = `Bearer ${t}`;
          const res = await fetch("/api/voice/transcribe", { method: "POST", body: fd, headers, credentials: "include" });
          const data = await res.json().catch(() => ({}));
          mic.classList.remove("listening");
          if (!res.ok) return toast(data.error || "Whisper недоступен");
          if (data.text && $("#smart-q")) {
            $("#smart-q").value = data.text;
            navigate(`/search?q=${encodeURIComponent(data.text)}`);
          }
        } catch (e) {
          mic.classList.remove("listening");
          toast(e.message || "Микрофон недоступен");
        }
      };
    }
  }

  function enableDragScroll(root = document) {
    root.querySelectorAll(".rail-track, .folder-rail, .drag-scroll").forEach((el) => {
      if (el.dataset.dragScroll === "1") return;
      el.dataset.dragScroll = "1";
      el.classList.add("drag-scroll-ready");
      let down = false;
      let startX = 0;
      let startY = 0;
      let startScroll = 0;
      let moved = false;

      const isControl = (target) =>
        !!target.closest(
          "button, select, input, textarea, label, .card-menu, .play-btn, .thumb-eye, .eye-btn, .rail-handle, .folder-assign, a.btn"
        );

      el.addEventListener("pointerdown", (e) => {
        if (e.pointerType === "mouse" && e.button !== 0) return;
        if (isControl(e.target)) return;
        // Organize: HTML5 DnD between folders — don't steal the gesture
        if (e.target.closest(".folder-tile[draggable='true']")) return;
        down = true;
        moved = false;
        startX = e.clientX;
        startY = e.clientY;
        startScroll = el.scrollLeft;
        try {
          el.setPointerCapture(e.pointerId);
        } catch (_) {}
      });

      el.addEventListener("pointermove", (e) => {
        if (!down) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        if (!moved) {
          if (Math.abs(dx) < 5 && Math.abs(dy) < 5) return;
          // Vertical intent → let page scroll; horizontal → rail
          if (Math.abs(dy) > Math.abs(dx) + 4) {
            down = false;
            el.classList.remove("is-dragging");
            return;
          }
          moved = true;
          el.classList.add("is-dragging");
        }
        el.scrollLeft = startScroll - dx;
        e.preventDefault();
      });

      const endDrag = () => {
        down = false;
        el.classList.remove("is-dragging");
      };
      el.addEventListener("pointerup", endDrag);
      el.addEventListener("pointercancel", endDrag);
      el.addEventListener("lostpointercapture", endDrag);

      // After a drag, kill the click that would open the card
      el.addEventListener(
        "click",
        (e) => {
          if (moved) {
            e.preventDefault();
            e.stopPropagation();
            moved = false;
          }
        },
        true
      );

      el.addEventListener("dragstart", (e) => {
        // Organize draft tiles still use HTML5 DnD between folders
        if (e.target.closest(".folder-tile[draggable='true']")) return;
        if (e.target.closest("img, a.card-main, .card")) e.preventDefault();
      });
    });
  }

  function wireNav() {
    document.querySelectorAll("[data-route]").forEach((btn) => {
      btn.onclick = () => navigate(btn.getAttribute("data-route"));
    });
    document.querySelectorAll("[data-nav]").forEach((a) => {
      a.addEventListener("click", (e) => {
        const href = a.getAttribute("href");
        if (href && href.startsWith("/")) {
          e.preventDefault();
          navigate(href);
        }
      });
    });
    const logout = $("#logout-btn");
    if (logout) {
      logout.onclick = async () => {
        try { await api("/api/auth/logout", { method: "POST", body: "{}" }); } catch (_) {}
        setToken("");
        me = null;
        navigate("/login");
      };
    }
    const fab = $("#fab-add");
    if (fab) fab.onclick = () => openAddSheet();
    wireSmartSearch();
    document.querySelectorAll("#bottom-nav button").forEach((b) => {
      const r = b.getAttribute("data-route");
      const path = location.pathname;
      const on =
        path === r ||
        (r === "/home" && path === "/") ||
        (r === "/settings" && (path === "/onboard" || path === "/settings"));
      b.classList.toggle("active", on);
    });
    enableDragScroll(app);
    wireCardMenus(app);
  }

  async function ensureAuth() {
    // Cookie session can keep you in even if localStorage was wiped mid-redeploy
    if (!token()) {
      try {
        const data = await api("/api/me");
        me = data.user;
        return true;
      } catch (e) {
        if (e.status === 401) return false;
        return false;
      }
    }
    try {
      const data = await api("/api/me");
      me = data.user;
      return true;
    } catch (e) {
      // Only wipe login on real 401. Redeploy 502/timeout must NOT kick you out.
      if (e.status === 401) {
        setToken("");
        me = null;
        return false;
      }
      if (me) return true;
      try {
        await new Promise((r) => setTimeout(r, 800));
        const data = await api("/api/me");
        me = data.user;
        return true;
      } catch (e2) {
        if (e2.status === 401) {
          setToken("");
          me = null;
          return false;
        }
        // Token still in localStorage — stay optimistic during blips
        return !!token();
      }
    }
  }

  async function renderLogin() {
    const status = await fetch("/api/auth/google/status").then((r) => r.json()).catch(() => ({}));
    const err = new URL(location.href).searchParams.get("error");
    app.innerHTML = `
      <div class="login-wrap">
        <div class="panel" style="width:min(460px,100%)">
          <h2>Clip Queue</h2>
          <p class="hint">Войди через Google — сразу после входа сами заберём лайки, плейлисты и подписки в библиотеку.</p>
          ${err ? `<p class="hint" style="color:#ff8a80">Ошибка входа: ${escapeHtml(err)}</p>` : ""}
          <div class="btn-row" style="flex-direction:column;align-items:stretch">
            ${status.configured
              ? `<a class="btn" href="/api/auth/google/start" style="text-align:center">Войти через Google / YouTube</a>`
              : `<div class="empty">Google OAuth ещё не настроен (GOOGLE_CLIENT_ID / SECRET на сервере). Пока можно dev-вход.</div>`}
            <button class="btn ghost" id="dev-login">Быстрый вход (dev)</button>
          </div>
          <details style="margin-top:18px">
            <summary class="muted" style="cursor:pointer">Вход по email (запасной)</summary>
            <div style="margin-top:12px">
              <div class="field">
                <label>Email</label>
                <input id="email" type="email" placeholder="you@mail.com" autocomplete="email" />
              </div>
              <div class="field hidden" id="code-field">
                <label>Код</label>
                <input id="code" inputmode="numeric" placeholder="123456" />
              </div>
              <div class="btn-row">
                <button class="btn secondary" id="send-code">Получить код</button>
                <button class="btn secondary hidden" id="verify-code">Войти</button>
              </div>
            </div>
          </details>
          <p class="sister">Сестра <a href="https://movie-planner.ru" target="_blank" rel="noopener">Movie Planner</a>.</p>
        </div>
      </div>`;
    $("#send-code").onclick = async () => {
      try {
        const data = await api("/api/auth/magic-link", {
          method: "POST",
          body: JSON.stringify({ email: $("#email").value.trim() }),
        });
        $("#code-field").classList.remove("hidden");
        $("#verify-code").classList.remove("hidden");
        if (data.dev_code) {
          $("#code").value = data.dev_code;
          toast(`Dev-код: ${data.dev_code}`);
        } else toast("Код в логах сервера");
      } catch (e) {
        toast(e.message);
      }
    };
    $("#verify-code").onclick = async () => {
      try {
        const data = await api("/api/auth/verify", {
          method: "POST",
          body: JSON.stringify({
            email: $("#email").value.trim(),
            code: $("#code").value.trim(),
          }),
        });
        setToken(data.token);
        me = data.user;
        navigate("/onboard");
      } catch (e) {
        toast(e.message);
      }
    };
    $("#dev-login").onclick = async () => {
      try {
        const data = await api("/api/auth/dev-login", { method: "POST", body: "{}" });
        setToken(data.token);
        me = data.user;
        navigate("/onboard");
      } catch (e) {
        toast(e.message);
      }
    };
  }

  async function runYoutubeSync({ autoGoHome = false, full = false } = {}) {
    const out = $("#sync-out");
    if (!out) return null;
    document.querySelectorAll("#sync-yt, #sync-yt-full").forEach((b) => {
      b.classList.add("busy");
      b.disabled = true;
    });
    const box = mountProgress(out, {
      title: full ? "Полный синк YouTube" : "Дельта: только новое",
      detail: full ? "Глубокий обход" : "Уже известное пропускаю",
    });
    try {
      const started = await api("/api/youtube/sync", {
        method: "POST",
        body: JSON.stringify({ full: full ? 1 : 0 }),
      });
      const jobId = started.job?.id;
      if (!jobId) throw new Error("Сервер не вернул job_id");
      updateProgress(box, started.job);

      let last = started.job;
      const t0 = Date.now();
      while (true) {
        await new Promise((r) => setTimeout(r, 600));
        const st = await api(`/api/youtube/sync/status?job_id=${encodeURIComponent(jobId)}`);
        last = st.job || {};
        if (last.status === "error" || last.type === "error") {
          finishProgress(box, {
            ok: false,
            title: last.title || "Ошибка",
            detail: last.error || last.detail || "",
            elapsed_sec: last.elapsed_sec,
          });
          throw new Error(last.error || last.detail || "Синк оборвался");
        }
        if (last.status === "done" || last.type === "done") {
          finishProgress(box, {
            ok: true,
            title: last.title || "YouTube у тебя в Clip Queue",
            detail: last.detail || "",
            elapsed_sec: last.elapsed_sec,
          });
          break;
        }
        updateProgress(box, last);
        if (Date.now() - t0 > 8 * 60 * 1000) {
          throw new Error("Синк слишком долгий (>8 мин) — смотри логи Railway");
        }
      }

      const s = last.stats || {};
      const mode = s.mode === "full" ? "полный" : "дельта";
      toast(`${mode}: +${s.liked_new || 0} лайков, +${s.playlist_items_new || 0} из плейлистов`);
      if (autoGoHome) {
        setTimeout(() => navigate("/home"), 700);
      }
      return s;
    } catch (e) {
      finishProgress(box, { ok: false, title: "Синк не вышел", detail: e.message });
      toast(e.message);
      return null;
    } finally {
      document.querySelectorAll("#sync-yt, #sync-yt-full").forEach((b) => {
        b.classList.remove("busy");
        b.disabled = false;
      });
    }
  }

  async function renderAuthCallback() {
    const params = new URL(location.href).searchParams;
    const t = params.get("token");
    if (!t) {
      toast("Нет токена");
      return navigate("/login", true);
    }
    setToken(t);
    const ok = await ensureAuth();
    let lib = 0;
    try {
      const meData = await api("/api/me");
      lib = meData.library_count || 0;
    } catch (_) {}
    const wantAutosync = params.get("autosync") === "1" && lib === 0;
    if (wantAutosync) {
      toast("Первый вход — тяну YouTube");
      return navigate("/settings?autosync=1", true);
    }
    toast(ok ? "Снова в аккаунте" : "Токен сохранён");
    return navigate("/home", true);
  }

  async function renderOnboard() {
    const meData = await api("/api/me");
    const wantAutosync =
      new URL(location.href).searchParams.get("autosync") === "1" &&
      !(meData.library_count > 0);
    app.innerHTML = `
      ${topbar("settings")}
      <section class="hero">
        <h1>Настройки</h1>
        <p>Онбординг (первый синк + разложить) — один раз. Дальше живёшь на главной; сюда — дельта или Takeout.</p>
      </section>
      <div class="panel" style="margin-bottom:16px">
        <h2>YouTube</h2>
        <p class="hint">
          По умолчанию <b>дельта</b>: только новое. Полный обход — если что-то пропустил.<br>
          Watch Later API не отдаёт — копируй в обычный плейлист.
        </p>
        <p class="muted">Статус: ${meData.youtube_connected ? "Google подключён" : "нужен вход через Google"} · в библиотеке: ${meData.library_count || 0}</p>
        <div class="btn-row">
          <button class="btn" id="sync-yt" ${meData.youtube_connected ? "" : "disabled"}>Обновить (дельта)</button>
          <button class="btn secondary" id="sync-yt-full" ${meData.youtube_connected ? "" : "disabled"}>Полный синк</button>
          ${!meData.youtube_connected && meData.google_oauth_configured
            ? `<a class="btn secondary" href="/api/auth/google/start">Войти через Google</a>` : ""}
          <a class="btn ghost" href="/home" data-nav>На главную</a>
        </div>
        <div id="sync-out"></div>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>2. История (опционально, Takeout)</h2>
        <p class="hint">Если нужна именно история «что смотрел» — takeout.google.com → YouTube → watch-history.json.</p>
        <div class="btn-row">
          <label class="file-btn">
            Выбрать JSON
            <input type="file" id="takeout-file" accept=".json,application/json" />
          </label>
        </div>
        <div id="takeout-out"></div>
      </div>
      <div class="panel">
        <h2>Умная категоризация</h2>
        <p class="hint">Один раз разложи библиотеку по темам — дальше категории живут на главной. Новые видео подхватываются правилами.</p>
        <div class="btn-row">
          <a class="btn" href="/organize" data-nav>Открыть</a>
        </div>
      </div>`;
    wireNav();
    $("#sync-yt").onclick = () => runYoutubeSync({ autoGoHome: false, full: false });
    const fullBtn = $("#sync-yt-full");
    if (fullBtn) {
      fullBtn.onclick = () => {
        if (!confirm("Полный синк заново обойдёт лайки/плейлисты. Обычно хватает дельты. Продолжить?")) return;
        runYoutubeSync({ autoGoHome: false, full: true });
      };
    }
    if (wantAutosync && meData.youtube_connected) {
      runYoutubeSync({ autoGoHome: true, full: true });
    }
    $("#takeout-file").onchange = async (ev) => {
      const file = ev.target.files?.[0];
      if (!file) return;
      const out = $("#takeout-out");
      const box = mountProgress(out, {
        title: "Читаю Takeout",
        detail: file.name,
      });
      try {
        const text = await file.text();
        updateProgress(box, { pct: 18, title: "Парсю JSON", detail: `${Math.round(file.size / 1024)} КБ` });
        const json = JSON.parse(text);
        const data = await runBusySteps(box, [
          { title: "Гружу историю на сервер", detail: "watch-history.json" },
          { title: "Разбираю просмотры", detail: "складываю в библиотеку" },
          { title: "Отмечаю уже просмотренные", detail: "статус watched" },
          { title: "Почти готово", detail: "пишу итог" },
        ], api("/api/youtube/takeout", {
          method: "POST",
          body: JSON.stringify(json),
        }));
        const s = data.stats || {};
        finishProgress(box, {
          ok: true,
          title: "Takeout загружен",
          detail: JSON.stringify(s),
          elapsed_sec: undefined,
        });
        toast("Takeout загружен");
      } catch (e) {
        finishProgress(box, { ok: false, title: "Импорт не вышел", detail: e.message });
        toast(e.message);
      }
    };
  }

  function folderTileHtml(it, folderIdx, folderOptionsHtml) {
    return `
      <div class="folder-tile card" draggable="true" data-video-id="${escapeHtml(it.video_id)}" data-from-folder="${folderIdx}">
        ${cardMenuHtml(it, { draftFolder: true })}
        <a class="card-main" href="/v/${encodeURIComponent(it.video_id)}" data-nav draggable="false">
          <div class="folder-tile-media card-thumb">
            <img src="${escapeHtml(it.thumb_url || "")}" alt="" loading="lazy" draggable="false" />
            <button type="button" class="thumb-eye" data-act="watched" title="Просмотрено" aria-label="Просмотрено">👁</button>
            ${it.duration_label ? `<span class="badge">${escapeHtml(it.duration_label)}</span>` : ""}
          </div>
          <div class="folder-tile-title card-title">${escapeHtml(it.title || "Без названия")}</div>
          <div class="folder-tile-meta card-meta">${escapeHtml(it.channel_title || "")}</div>
        </a>
        <div class="folder-tile-actions card-actions">
          <a class="btn play-btn" href="${escapeHtml(watchUrl(it))}" target="_blank" rel="noopener" title="YouTube" draggable="false">▶</a>
          <select class="folder-assign" data-assign-video="${escapeHtml(it.video_id)}" data-from-folder="${folderIdx}" title="Ещё в категорию">
            <option value="">+ ещё</option>
            ${folderOptionsHtml}
          </select>
        </div>
      </div>`;
  }

  function folderPreviewHtml(folder, idx, allFolders) {
    const items = folder.items || [];
    const opts = (allFolders || [])
      .map((f, i) => i === idx ? "" : `<option value="${i}">${escapeHtml(f.title || "Папка")}</option>`)
      .join("");
    return `
      <div class="folder-card" data-folder-idx="${idx}" data-drop-folder="${idx}">
        <div class="folder-head">
          <div class="folder-head-text">
            <b>${escapeHtml(folder.title || "Папка")}</b>
            <div class="muted">${folder.count || (folder.video_ids || []).length} видео</div>
          </div>
          <div class="folder-head-meta">
            <span class="count">${folder.count || (folder.video_ids || []).length}</span>
          </div>
        </div>
        <div class="folder-rail">
          ${items.length
            ? items.map((it) => folderTileHtml(it, idx, opts)).join("")
            : `<div class="muted" style="padding:12px">Пусто — перетащи сюда ролик</div>`}
        </div>
        ${(folder.video_ids || []).length > items.length
          ? `<div class="muted" style="padding:0 14px 12px;font-size:12px">Показаны ${items.length} из ${folder.video_ids.length}</div>`
          : ""}
      </div>`;
  }

  async function renderOrganize() {
    app.innerHTML = `
      ${topbar("organize")}
      <section class="hero">
        <h1>Умная категоризация</h1>
        <p>Собери темы один раз и нажми «Сохранить» — они появятся на главной. Перетащи ролики между темами. С нуля — только кнопкой ниже.</p>
      </section>
      <div class="panel">
        <div class="btn-row">
          <button class="btn" id="apply-proposal">Сохранить</button>
          <button class="btn secondary" id="propose">Переразложить с нуля</button>
          <label class="chip" style="cursor:pointer;display:inline-flex;align-items:center;gap:8px">
            <input type="checkbox" id="copy-mode" />
            Копировать в ещё одну папку
          </label>
        </div>
        <div id="active-rules" class="muted" style="margin-top:12px;font-size:13px"></div>
        <div id="proposal-box" style="margin-top:16px"></div>
      </div>`;
    wireNav();
    let lastProposal = null;

    const paintRules = async () => {
      try {
        const r = await api("/api/organize/rules");
        const rules = r.rules || [];
        $("#active-rules").innerHTML = rules.length
          ? `Сейчас действует <b style="color:var(--text)">${rules.length}</b> правил после прошлого «Сохранить». Новые шары пойдут по ним.`
          : `Пока не сохранено — поправь папки и нажми «Сохранить».`;
      } catch (_) {
        $("#active-rules").textContent = "";
      }
    };

    const findItem = (folder, videoId) => {
      const fromItems = (folder.items || []).find((x) => x.video_id === videoId);
      if (fromItems) return fromItems;
      return { video_id: videoId, title: videoId, channel_title: "", thumb_url: "", duration_label: "" };
    };

    const relocateVideo = (fromIdx, toIdx, videoId, { copy = false } = {}) => {
      if (!lastProposal?.folders || fromIdx === toIdx) return;
      const from = lastProposal.folders[fromIdx];
      const to = lastProposal.folders[toIdx];
      if (!from || !to) return;
      const item = findItem(from, videoId);
      if (!copy) {
        from.video_ids = (from.video_ids || []).filter((id) => id !== videoId);
        from.items = (from.items || []).filter((x) => x.video_id !== videoId);
        from.count = from.video_ids.length;
      }
      if (!(to.video_ids || []).includes(videoId)) {
        to.video_ids = [videoId, ...(to.video_ids || [])];
        to.items = [item, ...(to.items || [])].slice(0, 14);
      }
      to.count = (to.video_ids || []).length;
      paintProposal(lastProposal);
      toast(copy
        ? `Добавлено ещё в «${to.title}»`
        : `Перенесено в «${to.title}»`);
    };

    const paintProposal = (proposal) => {
      lastProposal = proposal;
      const list = proposal.folders || [];
      const folders = list.map((f, i) => folderPreviewHtml(f, i, list)).join("");
      const host = $("#proposal-box");
      host.innerHTML = `
        <p style="margin:0 0 12px;color:var(--text)">${escapeHtml(proposal.summary || "")}</p>
        ${(proposal.limitations || []).map((x) => `<div class="muted" style="font-size:12px">• ${escapeHtml(x)}</div>`).join("")}
        <p class="muted" style="font-size:13px;margin:10px 0 0">Перетащи карточку в другую тему. На десктопе можно тянуть карусель мышкой.</p>
        <div class="folder-list" style="margin-top:14px">${folders || `<div class="empty">Папок нет — нажми «Переразложить с нуля»</div>`}</div>`;
      wireNav();

      document.querySelectorAll(".folder-tile").forEach((tile) => {
        tile.addEventListener("dragstart", (e) => {
          tile.classList.add("dragging");
          e.dataTransfer.setData("text/plain", JSON.stringify({
            videoId: tile.getAttribute("data-video-id"),
            fromIdx: Number(tile.getAttribute("data-from-folder")),
          }));
          e.dataTransfer.effectAllowed = "copyMove";
        });
        tile.addEventListener("dragend", () => tile.classList.remove("dragging"));
      });

      document.querySelectorAll("[data-drop-folder]").forEach((zone) => {
        zone.addEventListener("dragover", (e) => {
          e.preventDefault();
          zone.classList.add("drop-hover");
        });
        zone.addEventListener("dragleave", () => zone.classList.remove("drop-hover"));
        zone.addEventListener("drop", (e) => {
          e.preventDefault();
          zone.classList.remove("drop-hover");
          let payload;
          try { payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}"); } catch (_) { return; }
          const toIdx = Number(zone.getAttribute("data-drop-folder"));
          const copy = !!$("#copy-mode")?.checked || e.altKey;
          relocateVideo(payload.fromIdx, toIdx, payload.videoId, { copy });
        });
      });

      document.querySelectorAll(".folder-assign").forEach((sel) => {
        sel.onchange = () => {
          const toIdx = Number(sel.value);
          if (Number.isNaN(toIdx)) return;
          const videoId = sel.getAttribute("data-assign-video");
          const fromIdx = Number(sel.getAttribute("data-from-folder"));
          relocateVideo(fromIdx, toIdx, videoId, { copy: true });
          sel.value = "";
        };
      });

      $("#apply-proposal").classList.toggle("hidden", !list.length);
      enableDragScroll(host);
      wireCardMenus(host);
      host.querySelectorAll('[data-act="remove-draft"]').forEach((btn) => {
        btn.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          const card = btn.closest(".card");
          const videoId = card?.getAttribute("data-video-id");
          const fromIdx = Number(card?.getAttribute("data-from-folder"));
          if (!lastProposal?.folders?.[fromIdx] || !videoId) return;
          const from = lastProposal.folders[fromIdx];
          from.video_ids = (from.video_ids || []).filter((id) => id !== videoId);
          from.items = (from.items || []).filter((x) => x.video_id !== videoId);
          from.count = from.video_ids.length;
          paintProposal(lastProposal);
          toast(`Убрано из «${from.title || "темы"}»`);
        };
      });
    };

    const runPropose = async () => {
      const btn = $("#propose");
      btn.classList.add("busy");
      const box = mountProgress($("#proposal-box"), {
        title: "Собираю структуру заново",
        detail: "Старая раскладка на экране заменится черновиком",
      });
      try {
        const data = await runBusySteps(box, [
          { title: "Смотрю библиотеку", detail: "очередь и каналы" },
          { title: "Кластеризую", detail: "темы, длины, каналы" },
          { title: "Черновик папок", detail: "раскладываю видео" },
        ], api("/api/organize/propose", { method: "POST", body: JSON.stringify({ use_llm: false }) }));
        const purged = data.proposal?.music_purged || 0;
        const broken = data.proposal?.broken_purged || 0;
        const shorts = data.proposal?.shortform_purged || 0;
        const bits = [];
        if (purged) bits.push(`музыка ${purged}`);
        if (shorts) bits.push(`короткие ${shorts}`);
        if (broken) bits.push(`битые ${broken}`);
        finishProgress(box, {
          ok: true,
          title: bits.length ? `Черновик · убрал: ${bits.join(", ")}` : "Черновик готов",
          detail: "Проверь и нажми «Сохранить»",
        });
        paintProposal(data.proposal);
        if (bits.length) toast(`Убрал из очереди: ${bits.join(", ")}`);
      } catch (e) {
        finishProgress(box, { ok: false, title: "Не собралось", detail: e.message });
      } finally {
        btn.classList.remove("busy");
      }
    };

    $("#propose").onclick = () => {
      if (!confirm("Собрать раскладку заново? Текущий черновик на экране заменится. Уже сохранённое в БД останется, пока не нажмёшь «Сохранить».")) {
        return;
      }
      runPropose();
    };
    const doSave = async () => {
      if (!lastProposal || !(lastProposal.folders || []).length) {
        toast("Нечего сохранять — сначала собери или открой раскладку");
        return;
      }
      const btn = $("#apply-proposal");
      if (btn) {
        btn.classList.add("busy");
        btn.disabled = true;
        btn.textContent = "Сохраняю…";
      }
      toast("Сохраняю категории…");
      const box = mountProgress($("#proposal-box"), {
        title: "Сохраняю",
        detail: "Папки + правила для новых видео",
      });
      try {
        const payload = {
          proposal: {
            summary: lastProposal.summary || "",
            proposal_id: lastProposal.proposal_id,
            folders: (lastProposal.folders || []).map((f) => ({
              title: f.title,
              theme_id: f.theme_id,
              video_ids: f.video_ids || (f.items || []).map((x) => x.video_id),
              rules: f.rules || [],
            })),
          },
          proposal_id: lastProposal.proposal_id,
        };
        const data = await api("/api/organize/apply", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        finishProgress(box, {
          ok: true,
          title: "Сохранено",
          detail: `Папок: ${(data.lists || []).length} · правил: ${data.rules_saved || 0}`,
        });
        toast(`Готово: ${(data.lists || []).length} категорий на главной`);
        setTimeout(() => navigate("/home"), 400);
      } catch (e) {
        finishProgress(box, { ok: false, title: "Не сохранилось", detail: e.message });
        toast(e.message || "Ошибка сохранения");
      } finally {
        if (btn) {
          btn.classList.remove("busy");
          btn.disabled = false;
          btn.textContent = "Сохранить";
        }
      }
    };
    $("#apply-proposal").onclick = () => doSave();

    await paintRules();
    try {
      const saved = await api("/api/organize/structure");
      if (saved.has_structure && (saved.folders || []).length) {
        paintProposal({
          summary: saved.summary || "Твоя сохранённая раскладка",
          folders: saved.folders,
          limitations: ["Это уже сохранённое — правь и жми «Сохранить», или «Переразложить с нуля»"],
        });
      } else {
        $("#proposal-box").innerHTML = `
          <div class="empty">
            Раскладки ещё нет. Нажми «Переразложить с нуля», поправь папки и сохрани —
            они появятся на главной.
          </div>`;
      }
    } catch (e) {
      $("#proposal-box").innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
    }
  }

  async function renderHome() {
    const [shell, structure] = await Promise.all([
      api("/api/home/shell").catch(() => ({ counts: {}, rails: [] })),
      api("/api/organize/structure").catch(() => ({ has_structure: false, folders: [], recent: [], growing: [] })),
    ]);
    const folders = structure.folders || [];
    const recent = structure.recent || [];
    const growing = structure.growing || [];
    const has = !!structure.has_structure && folders.length;

    const growingHtml = growing.length
      ? `<div class="growing-row">${growing.map((g) => `
          <div class="growing-chip">
            <b>${escapeHtml(g.title)}</b>
            <span class="muted">+${g.added} за 2 нед.</span>
          </div>`).join("")}</div>`
      : "";

    app.innerHTML = `
      ${topbar("home")}
      <section class="hero">
        <h1>${has ? "Что посмотреть" : "Сначала разложи видео"}</h1>
        <p>${has
          ? "Твои темы. Перетащи ⋮⋮ у названия, чтобы поменять порядок. Новые шары сами попадают в категории."
          : "Онбординг: синк → умная категоризация → Сохранить. Потом главная — центр продукта."}</p>
        <div class="stats">
          <div class="stat">Папок: <b>${folders.length}</b></div>
          <div class="stat">Очередь: <b>${shell.counts?.queue ?? "—"}</b></div>
          <div class="stat">Начатые: <b>${shell.counts?.started || 0}</b></div>
        </div>
        ${growingHtml}
        <div class="btn-row" style="margin-top:14px">
          <a class="btn secondary" href="/queue?status=queue&kind=video" data-nav>Очередь</a>
          <a class="btn ghost" href="/channels" data-nav>Каналы</a>
          <a class="btn ghost" href="/settings" data-nav>Настройки</a>
        </div>
      </section>
      <div id="rails"></div>`;
    wireNav();
    const host = $("#rails");
    if (!has && !recent.length) {
      host.innerHTML = `
        <div class="panel">
          <div class="empty">Пока пусто — в Настройках открой «Умную категоризацию», сохрани темы один раз.</div>
          <div class="btn-row" style="margin-top:12px">
            <a class="btn" href="/organize" data-nav>Умная категоризация</a>
          </div>
        </div>`;
      return;
    }
    if (recent.length) {
      const block = document.createElement("section");
      block.className = "rail";
      block.innerHTML = `
        <div class="rail-head">
          <h2>Недавно добавил</h2>
          <span class="muted" style="font-size:13px">${recent.length}</span>
        </div>
        <div class="rail-track drag-scroll">
          ${recent.map((it) => cardHtml(it)).join("")}
        </div>`;
      host.appendChild(block);
    }
    for (const folder of folders) {
      const block = document.createElement("section");
      block.className = "rail";
      const listId = folder.list_id != null ? String(folder.list_id) : "";
      if (listId) block.setAttribute("data-list-id", listId);
      const items = folder.items || [];
      const hot = growing.some((g) => (g.title || "").toLowerCase() === (folder.title || "").toLowerCase());
      block.innerHTML = `
        <div class="rail-head">
          <div class="rail-head-left">
            ${listId ? `<button type="button" class="rail-handle" title="Перетащить категорию" aria-label="Перетащить">⋮⋮</button>` : ""}
            <h2>${hot ? "🔥 " : ""}${escapeHtml(folder.title)}</h2>
          </div>
          <span class="muted" style="font-size:13px">${folder.count || items.length} видео</span>
        </div>
        <div class="rail-track drag-scroll">
          ${items.length
            ? items.map((it) => cardHtml({
                ...it,
                watch_url: it.watch_url || `https://www.youtube.com/watch?v=${it.video_id}`,
              }, { listId })).join("")
            : `<div class="empty" style="min-width:260px">Пусто</div>`}
        </div>`;
      host.appendChild(block);
    }
    enableDragScroll(host);
    wireCardMenus(host);
    wireNav();

    // Category row reorder via grip handle
    let dragRail = null;
    host.querySelectorAll(".rail[data-list-id]").forEach((rail) => {
      const handle = rail.querySelector(".rail-handle");
      if (!handle) return;
      handle.addEventListener("dragstart", (e) => {
        dragRail = rail;
        rail.classList.add("rail-dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", rail.getAttribute("data-list-id") || "");
      });
      handle.addEventListener("dragend", () => {
        rail.classList.remove("rail-dragging");
        host.querySelectorAll(".rail-drop-target").forEach((el) => el.classList.remove("rail-drop-target"));
        dragRail = null;
      });
      handle.setAttribute("draggable", "true");
      rail.addEventListener("dragover", (e) => {
        if (!dragRail || dragRail === rail) return;
        e.preventDefault();
        rail.classList.add("rail-drop-target");
        const rect = rail.getBoundingClientRect();
        const before = e.clientY < rect.top + rect.height / 2;
        if (before) host.insertBefore(dragRail, rail);
        else host.insertBefore(dragRail, rail.nextSibling);
      });
      rail.addEventListener("dragleave", () => rail.classList.remove("rail-drop-target"));
      rail.addEventListener("drop", async (e) => {
        e.preventDefault();
        rail.classList.remove("rail-drop-target");
        const order = [...host.querySelectorAll(".rail[data-list-id]")].map((el) => el.getAttribute("data-list-id"));
        try {
          await api("/api/lists/reorder", {
            method: "POST",
            body: JSON.stringify({ order }),
          });
          toast("Порядок категорий сохранён");
        } catch (err) {
          toast(err.message || "Не удалось сохранить порядок");
        }
      });
    });
  }

  async function renderQueue() {
    const params = new URL(location.href).searchParams;
    let kind = params.get("kind") || "video";
    let status = params.get("status") || "queue";
    if (!["queue", "in_progress", "watched", "archived"].includes(status)) status = "queue";
    // Watched / started: show everything in that bucket (music/shorts too)
    if (status === "watched" || status === "in_progress") kind = params.get("kind") || "all";
    const channel = params.get("channel") || "";
    const qs = new URLSearchParams({
      status,
      kind,
      limit: "120",
    });
    if (channel) qs.set("channel", channel);
    const data = await api(`/api/library?${qs}`);
    const items = data.items || [];
    const statusTitle = {
      queue: "Очередь",
      in_progress: "Начатые",
      watched: "Просмотренные",
      archived: "Архив",
    }[status] || "Очередь";
    const statusHint = {
      queue: "Только длинные (6 мин – 10 ч). Короткие, клипы и 10+ часов — вкладками ниже.",
      in_progress: "Открыл на YouTube или отметил «Начал». Из общей очереди уже убрано.",
      watched: "Уже посмотрел — в очереди этих роликов больше нет.",
      archived: "Скрытые из плана.",
    }[status];
    app.innerHTML = `
      ${topbar("queue")}
      <section class="hero">
        <h1>${channel ? escapeHtml(channel) : statusTitle}</h1>
        <p>${channel
          ? `Видео канала · <a href="/channels" data-nav>все каналы</a>`
          : statusHint}</p>
      </section>
      <div class="filter-chips" id="status-chips">
        <button type="button" class="chip ${status === "queue" ? "active" : ""}" data-status="queue">Очередь</button>
        <button type="button" class="chip ${status === "in_progress" ? "active" : ""}" data-status="in_progress">Начатые</button>
        <button type="button" class="chip ${status === "watched" ? "active" : ""}" data-status="watched">Просмотренные</button>
      </div>
      <div class="filter-chips" id="kind-chips">
        <button type="button" class="chip ${kind === "video" ? "active" : ""}" data-kind="video">Видео 6м–10ч</button>
        <button type="button" class="chip ${kind === "shortform" || kind === "shorts" ? "active" : ""}" data-kind="shortform">До 6 мин</button>
        <button type="button" class="chip ${kind === "music" ? "active" : ""}" data-kind="music">Музыка</button>
        <button type="button" class="chip ${kind === "marathon" ? "active" : ""}" data-kind="marathon">10+ часов</button>
        <button type="button" class="chip ${kind === "all" ? "active" : ""}" data-kind="all">Всё</button>
        <a class="chip" href="/channels" data-nav>Каналы →</a>
        ${channel ? `<button type="button" class="chip" id="clear-channel">Сбросить канал</button>` : ""}
      </div>
      <div class="field" style="max-width:420px">
        <input id="q-filter" placeholder="Поиск по названию или каналу" />
      </div>
      <div class="muted" style="margin:0 0 12px;font-size:13px">Показано: ${items.length}${channel ? ` · ${escapeHtml(channel)}` : ""}</div>
      <div class="grid" id="queue-grid">
        ${items.length ? items.map(cardHtml).join("") : `<div class="empty">Пусто. ${status === "queue" ? `<a href="/queue?status=in_progress" data-nav>Начатые</a> · <a href="/channels" data-nav>каналы</a>` : `<a href="/queue?status=queue" data-nav>В очередь</a>`}</div>`}
      </div>`;
    wireNav();
    wireCardMenus(app);
    const paint = (list) => {
      $("#queue-grid").innerHTML = list.length
        ? list.map(cardHtml).join("")
        : `<div class="empty">Ничего не нашлось</div>`;
      wireNav();
      wireCardMenus($("#queue-grid"));
    };
    $("#q-filter").oninput = (e) => {
      const q = e.target.value.trim().toLowerCase();
      paint(!q ? items : items.filter((i) => `${i.title} ${i.channel_title}`.toLowerCase().includes(q)));
    };
    const goQueue = (nextStatus, nextKind) => {
      const next = new URL(location.href);
      next.searchParams.set("status", nextStatus);
      next.searchParams.set("kind", nextKind);
      if (channel) next.searchParams.set("channel", channel);
      else next.searchParams.delete("channel");
      navigate(next.pathname + next.search);
    };
    document.querySelectorAll("#status-chips [data-status]").forEach((btn) => {
      btn.onclick = () => {
        const st = btn.getAttribute("data-status");
        goQueue(st, st === "queue" ? (kind === "all" ? "video" : kind) : "all");
      };
    });
    document.querySelectorAll("#kind-chips [data-kind]").forEach((btn) => {
      btn.onclick = () => goQueue(status, btn.getAttribute("data-kind"));
    });
    const clearCh = $("#clear-channel");
    if (clearCh) {
      clearCh.onclick = () => navigate(`/queue?status=${encodeURIComponent(status)}&kind=${encodeURIComponent(kind)}`);
    }
  }

  async function renderChannels() {
    const params = new URL(location.href).searchParams;
    const kind = params.get("kind") || "video";
    const theme = params.get("theme") || "";
    const durMinMin = Number(params.get("dur_min") || 0); // seconds
    const durMaxMin = Number(params.get("dur_max") || 0);
    // UI slider in minutes
    let minM = Math.floor(durMinMin / 60) || 0;
    let maxM = durMaxMin ? Math.floor(durMaxMin / 60) : 180;

    const qs = new URLSearchParams({
      kind,
      status: "queue",
      expand: "1",
      videos_limit: "18",
    });
    if (theme) qs.set("theme", theme);
    if (durMinMin > 0) qs.set("dur_min", String(durMinMin));
    if (durMaxMin > 0) qs.set("dur_max", String(durMaxMin));

    const data = await api(`/api/channels?${qs}`);
    const channels = data.channels || [];
    const themeOpts = data.themes || [];

    const fmtRange = (a, b) => {
      const f = (m) => (m >= 60 ? `${Math.floor(m / 60)}ч ${m % 60}м` : `${m}м`);
      return `${f(a)} – ${f(b)}`;
    };

    app.innerHTML = `
      ${topbar("channels")}
      <section class="hero">
        <h1>Каналы</h1>
        <p>Видео прямо здесь — листай карусель. Фильтр по теме и длительности.</p>
      </section>
      <div class="filter-chips" id="kind-chips">
        <button type="button" class="chip ${kind === "video" ? "active" : ""}" data-kind="video">Видео</button>
        <button type="button" class="chip ${kind === "all" ? "active" : ""}" data-kind="all">Всё</button>
        <button type="button" class="chip ${kind === "music" ? "active" : ""}" data-kind="music">Музыка</button>
        <button type="button" class="chip ${kind === "shorts" ? "active" : ""}" data-kind="shorts">Шортсы</button>
      </div>
      <div class="filter-chips" id="theme-chips" style="margin-top:8px">
        <button type="button" class="chip ${!theme ? "active" : ""}" data-theme="">Все темы</button>
        ${themeOpts.slice(0, 12).map((t) => `
          <button type="button" class="chip ${theme === t.id ? "active" : ""}" data-theme="${escapeHtml(t.id)}">${escapeHtml(t.title)}</button>
        `).join("")}
      </div>
      <div class="panel dur-filter" style="margin:14px 0">
        <div class="dur-filter-head">
          <b>Длительность</b>
          <span class="muted" id="dur-label">${fmtRange(minM, maxM)}</span>
        </div>
        <div class="dur-sliders">
          <label>от <input type="range" id="dur-min" min="0" max="180" step="5" value="${minM}" /></label>
          <label>до <input type="range" id="dur-max" min="5" max="180" step="5" value="${maxM}" /></label>
        </div>
        <button type="button" class="btn secondary" id="dur-apply" style="margin-top:10px">Применить</button>
      </div>
      <div class="channel-rails" id="channel-rails">
        ${channels.length
          ? channels.map((c) => `
            <section class="rail channel-block">
              <div class="rail-head">
                <div class="channel-rail-title">
                  <img class="channel-avatar sm" src="${escapeHtml(c.thumb_url || "")}" alt="" loading="lazy"
                    onerror="this.style.opacity='0.25'" />
                  <div>
                    <h2>${escapeHtml(c.channel_title)}</h2>
                    <div class="muted" style="font-size:13px">${c.count} видео</div>
                  </div>
                </div>
              </div>
              <div class="rail-track drag-scroll">
                ${(c.videos || []).length
                  ? (c.videos || []).map((it) => cardHtml(it)).join("")
                  : `<div class="empty" style="min-width:220px">Нет видео под фильтр</div>`}
              </div>
            </section>`).join("")
          : `<div class="empty">Ничего не нашлось — сбрось фильтры или сделай синк в Настройках</div>`}
      </div>`;
    wireNav();
    wireCardMenus(app);

    const go = (next = {}) => {
      const u = new URL(location.href);
      u.pathname = "/channels";
      u.searchParams.set("kind", next.kind ?? kind);
      if (next.theme !== undefined) {
        if (next.theme) u.searchParams.set("theme", next.theme);
        else u.searchParams.delete("theme");
      } else if (theme) u.searchParams.set("theme", theme);
      else u.searchParams.delete("theme");
      const dMin = next.dur_min !== undefined ? next.dur_min : durMinMin;
      const dMax = next.dur_max !== undefined ? next.dur_max : durMaxMin;
      if (dMin > 0) u.searchParams.set("dur_min", String(dMin));
      else u.searchParams.delete("dur_min");
      if (dMax > 0) u.searchParams.set("dur_max", String(dMax));
      else u.searchParams.delete("dur_max");
      navigate(u.pathname + u.search);
    };

    document.querySelectorAll("#kind-chips [data-kind]").forEach((btn) => {
      btn.onclick = () => go({ kind: btn.getAttribute("data-kind") });
    });
    document.querySelectorAll("#theme-chips [data-theme]").forEach((btn) => {
      btn.onclick = () => go({ theme: btn.getAttribute("data-theme") || "" });
    });
    const minEl = $("#dur-min");
    const maxEl = $("#dur-max");
    const label = $("#dur-label");
    const syncLabel = () => {
      let a = Number(minEl.value);
      let b = Number(maxEl.value);
      if (a > b) [a, b] = [b, a];
      label.textContent = fmtRange(a, b);
    };
    minEl.oninput = syncLabel;
    maxEl.oninput = syncLabel;
    $("#dur-apply").onclick = () => {
      let a = Number(minEl.value);
      let b = Number(maxEl.value);
      if (a > b) [a, b] = [b, a];
      go({ dur_min: a * 60, dur_max: b * 60 });
    };
    enableDragScroll($("#channel-rails"));
  }

  function shareParams() {
    const u = new URL(location.href);
    return {
      url: u.searchParams.get("url") || "",
      text: u.searchParams.get("text") || "",
      title: u.searchParams.get("title") || "",
    };
  }

  function pickUrlFromShare({ url, text }) {
    if (url) return url;
    const m = String(text || "").match(/https?:\/\/\S+/);
    return m ? m[0] : text || "";
  }

  function parseUrlBlob(raw) {
    const text = String(raw || "").trim();
    if (!text) return [];
    const found = text.match(/https?:\/\/[^\s,;]+/gi) || [];
    if (found.length) return [...new Set(found.map((u) => u.replace(/[),.\]]+$/, "")))];
    return text.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean);
  }

  async function openAddSheet(prefill = "") {
    let overlay = $("#add-sheet");
    if (overlay) overlay.remove();
    overlay = document.createElement("div");
    overlay.id = "add-sheet";
    overlay.className = "sheet-overlay";
    overlay.innerHTML = `
      <div class="sheet-card" role="dialog" aria-label="Добавить видео">
        <div class="sheet-head">
          <h2>Добавить</h2>
          <button type="button" class="btn ghost" id="add-close">Закрыть</button>
        </div>
        <p class="hint">Ctrl/⌘+V → Enter. Несколько ссылок — с новой строки (Ctrl/⌘+Enter).</p>
        <div class="field">
          <textarea id="yt-urls" rows="4" placeholder="https://youtu.be/…">${escapeHtml(prefill)}</textarea>
        </div>
        <div class="btn-row">
          <button class="btn" id="save-urls">В очередь</button>
          <label class="btn secondary file-btn">Файл со ссылками
            <input type="file" id="urls-file" accept=".txt,.csv,text/plain" hidden />
          </label>
        </div>
        <div id="add-out" class="muted" style="margin-top:12px;font-size:13px"></div>
      </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    const ta = $("#yt-urls");
    const doSave = async () => {
      const urls = parseUrlBlob(ta.value);
      if (!urls.length) return toast("Вставь хотя бы одну ссылку");
      const out = $("#add-out");
      out.textContent = `Добавляю ${urls.length}…`;
      let ok = 0;
      let fail = 0;
      for (const url of urls) {
        try {
          await api("/api/videos/save", { method: "POST", body: JSON.stringify({ url }) });
          ok += 1;
        } catch (_) {
          fail += 1;
        }
      }
      out.textContent = `Готово: ${ok} · ошибок: ${fail}`;
      toast(`Добавлено: ${ok}`);
      if (ok) setTimeout(close, 600);
    };
    $("#add-close").onclick = close;
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    $("#urls-file").onchange = async (ev) => {
      const f = ev.target.files?.[0];
      if (!f) return;
      const text = await f.text();
      ta.value = ((ta.value || "") + "\n" + text).trim();
      ta.focus();
    };
    $("#save-urls").onclick = () => doSave();
    ta.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      if (e.ctrlKey || e.metaKey) {
        // Ctrl/⌘+Enter → newline
        e.preventDefault();
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const v = ta.value;
        ta.value = `${v.slice(0, start)}\n${v.slice(end)}`;
        ta.selectionStart = ta.selectionEnd = start + 1;
        return;
      }
      e.preventDefault();
      doSave();
    });
    // Focus immediately so Ctrl+V → Enter works without extra click
    requestAnimationFrame(() => {
      ta.focus();
      const len = ta.value.length;
      ta.setSelectionRange(len, len);
    });
  }

  async function renderAdd() {
    const shared = shareParams();
    const initial = pickUrlFromShare(shared);
    // Dedicated /add kept for share target / PWA — opens sheet on current shell
    app.innerHTML = `${topbar("home")}<div class="panel"><div class="muted">Открываю добавление…</div></div>`;
    wireNav();
    openAddSheet(initial);
  }

  async function renderLists() {
    toast("Списки = твоя раскладка на главной");
    return navigate("/home", true);
  }

  async function renderTagsPage() {
    return navigate("/settings", true);
  }

  async function renderSearch() {
    const q0 = new URL(location.href).searchParams.get("q") || "";
    app.innerHTML = `
      ${topbar("home")}
      <section class="hero">
        <h1>Умный поиск</h1>
        <p>Пиши как чувствуешь: «видосик на вечер», «ржачный но не стендап», «геймплей не обзор». Ищем по твоей библиотеке — название, описание, теги и твои слова.</p>
      </section>
      <div class="panel">
        <form id="search-form" class="smart-search smart-search-lg">
          <input type="search" id="search-q" value="${escapeHtml(q0)}" placeholder="Что хочешь посмотреть?" />
          <button type="button" class="smart-mic" id="search-mic" title="Голосом" aria-label="Голосом">🎤</button>
          <button type="submit" class="smart-go" title="Найти" aria-label="Найти">⌕</button>
        </form>
        <div id="search-meta" class="muted" style="margin-top:10px;font-size:13px"></div>
        <div id="search-out" style="margin-top:16px"></div>
      </div>`;
    wireNav();
    const run = async (q) => {
      const out = $("#search-out");
      const meta = $("#search-meta");
      if (!q || q.trim().length < 2) {
        out.innerHTML = `<div class="empty">Введи хотя бы пару слов</div>`;
        return;
      }
      out.innerHTML = `<div class="muted">Ищу…</div>`;
      try {
        const data = await api(`/api/search?q=${encodeURIComponent(q.trim())}&limit=40`);
        const interp = data.interpreted || {};
        const bits = [];
        if (interp.rewritten && interp.rewritten !== q) bits.push(`понял как «${interp.rewritten}»`);
        if ((interp.must_not || []).length) bits.push(`без: ${(interp.must_not || []).join(", ")}`);
        if ((interp.prefer || []).length) bits.push(`ближе: ${(interp.prefer || []).join(", ")}`);
        meta.textContent = bits.length ? bits.join(" · ") : `${(data.items || []).length} совпадений`;
        const all = data.items || [];
        const isShortish = (it) =>
          it.is_short || it.is_shortform || it.content_kind === "shorts" || it.content_kind === "shortform"
          || (typeof it.duration_sec === "number" && it.duration_sec > 0 && it.duration_sec <= 180);
        const main = all.filter((it) => !isShortish(it));
        const shorts = all.filter((it) => isShortish(it));
        meta.textContent = bits.length
          ? bits.join(" · ")
          : `${main.length} совпадений${shorts.length ? ` · ${shorts.length} шортов скрыто` : ""}`;
        if (!main.length && !shorts.length) {
          out.innerHTML = `<div class="empty">В библиотеке ничего близкого. Попробуй другие слова или разметь пару роликов своими словами.</div>`;
          return;
        }
        let html = "";
        if (main.length) {
          html += `<div class="search-grid" id="search-grid">${main.map(cardHtml).join("")}</div>`;
        } else {
          html += `<div class="empty">Длинных роликов нет — только шорты по запросу.</div>`;
        }
        if (shorts.length) {
          html += `
            <details class="shorts-fold" style="margin-top:18px">
              <summary class="muted">Шорты / короткие (${shorts.length}) — обычно не для очереди</summary>
              <div class="search-grid" style="margin-top:12px">${shorts.map(cardHtml).join("")}</div>
            </details>`;
        }
        out.innerHTML = html;
        wireCardMenus(out);
      } catch (e) {
        out.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
      }
    };
    $("#search-form").onsubmit = (e) => {
      e.preventDefault();
      const q = ($("#search-q")?.value || "").trim();
      navigate(`/search?q=${encodeURIComponent(q)}`, true);
      run(q);
    };
    const mic = $("#search-mic");
    if (mic) {
      mic.onclick = () => {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return toast("Голос: Chrome / Safari");
        const rec = new SR();
        rec.lang = "ru-RU";
        mic.classList.add("listening");
        rec.onresult = (ev) => {
          const text = (ev.results?.[0]?.[0]?.transcript || "").trim();
          mic.classList.remove("listening");
          if (text && $("#search-q")) {
            $("#search-q").value = text;
            navigate(`/search?q=${encodeURIComponent(text)}`, true);
            run(text);
          }
        };
        rec.onerror = () => mic.classList.remove("listening");
        rec.onend = () => mic.classList.remove("listening");
        try { rec.start(); } catch (_) { mic.classList.remove("listening"); }
      };
    }
    if (q0) {
      if ($("#smart-q")) $("#smart-q").value = q0;
      run(q0);
    }
  }

  async function renderVideo(videoId) {
    const data = await api(`/api/videos/${encodeURIComponent(videoId)}`);
    const item = data.item;
    let allTags = { tags: [] };
    try { allTags = await api("/api/tags"); } catch (_) {}
    if (!(allTags.tags || []).length) {
      try { allTags = await api("/api/tags/seed-defaults", { method: "POST", body: "{}" }); } catch (_) {}
    }
    let similar = { items: [] };
    let ytRelated = { items: [], query: "" };
    try {
      similar = await api(`/api/videos/${encodeURIComponent(videoId)}/similar`);
    } catch (_) {}
    try {
      ytRelated = await api(`/api/videos/${encodeURIComponent(videoId)}/yt-related`);
    } catch (_) {}
    const assignedIds = new Set((item.user_tags || []).map((t) => t.id));
    const pickHtml = (allTags.tags || []).map((t) => {
      const on = assignedIds.has(t.id);
      const label = `${t.emoji ? t.emoji + " " : ""}${t.name}`;
      return `<button type="button" class="tag-pill tag-pill-btn ${on ? "tag-pill-on" : ""}" data-toggle-tag="${t.id}" data-tag-name="${escapeHtml(t.name)}">${escapeHtml(label)}${on ? " ✓" : ""}</button>`;
    }).join("");

    const unavailable = item.is_unavailable || /^(private|deleted) video$/i.test(item.title || "");
    const noteVal = item.note || "";
    app.innerHTML = `
      ${topbar("queue")}
      <div class="video-page">
        <div>
          <div class="video-hero">
            <img src="${escapeHtml(item.thumb_url)}" alt="" />
          </div>
          ${unavailable ? `<div class="warn-box">YouTube скрыл этот ролик (private/deleted). В лайках осталась заглушка — открыть на YouTube, скорее всего, не получится. Можно убрать из библиотеки.</div>` : ""}
          <h1 style="font-family:var(--display);letter-spacing:-0.03em;margin:16px 0 8px;font-size:1.6rem">${escapeHtml(item.title)}</h1>
          <div class="muted">${escapeHtml(item.channel_title || "")}${item.duration_label ? " · " + escapeHtml(item.duration_label) : ""}
            ${item.channel_title && !unavailable ? ` · <a href="/queue?kind=video&channel=${encodeURIComponent(item.channel_title)}" data-nav>все с канала</a>` : ""}
          </div>
          <div id="assigned-tags" class="tags-row" style="margin-top:12px">
            ${tagPillsHtml(item.user_tags || [], { removable: true, videoId })}
          </div>
          <p class="muted" style="margin-top:14px;line-height:1.5;white-space:pre-wrap">${escapeHtml((item.description || "").slice(0, 600))}</p>
          <div class="field lexicon-field" style="margin-top:16px">
            <label>Как ты это назовёшь (своя лексика)</label>
            <textarea id="user-note" rows="2" placeholder="Например: стрёмная хрень / уют на вечер / хуйня для деградантов">${escapeHtml(noteVal)}</textarea>
            <button type="button" class="btn secondary" id="save-note" style="margin-top:8px">Сохранить описание</button>
          </div>
        </div>
        <div class="panel">
          <div class="muted" style="margin:0 0 10px;font-size:13px">Статус: <b>${
            item.status === "watched" ? "просмотрено" :
            item.status === "in_progress" ? "начато" :
            item.status === "archived" ? "архив" : "в очереди"
          }</b></div>
          <div class="btn-row" style="flex-direction:column;align-items:stretch">
            <button class="btn" id="open-yt">Смотреть на YouTube</button>
            <button class="btn secondary" id="mark-started"${item.status === "in_progress" ? " disabled" : ""}>${item.status === "in_progress" ? "Уже в начатых" : "Отметить начатым"}</button>
            <button class="btn secondary" id="mark-watched"${item.status === "watched" ? " disabled" : ""}>${item.status === "watched" ? "Уже в просмотренных" : "Отметить просмотренным"}</button>
            <button class="btn ghost" id="back-queue">Вернуть в очередь</button>
            <button class="btn ghost" id="delete-item">Убрать из библиотеки</button>
          </div>
          <h3 style="margin:18px 0 8px;font-size:15px">Теги</h3>
          <div id="tag-picker" class="tags-cloud">${pickHtml || `<span class="muted">Сначала создай теги на вкладке «Теги»</span>`}</div>
          <div class="field" style="margin-top:12px">
            <label>Или новый тег</label>
            <div class="btn-row">
              <input id="new-tag" placeholder="название" style="flex:1" />
              <button class="btn secondary" id="add-tag">Создать и повесить</button>
            </div>
          </div>
          <button class="btn ghost" id="ai-tag" style="margin-top:8px;width:100%">Подсказать тему (AI)</button>
          <pre id="ai-out" class="muted" style="white-space:pre-wrap;font-size:12px;margin-top:8px"></pre>
          <div class="field" style="margin-top:16px">
            <label>В список</label>
            <div class="btn-row">
              <select id="list-select" style="flex:1;border-radius:12px;padding:10px;background:var(--bg-elev-2);color:var(--text);border:1px solid var(--border)"></select>
              <button class="btn secondary" id="add-to-list">Добавить</button>
            </div>
          </div>
          <a class="muted" href="/tags" data-nav style="display:inline-block;margin-top:10px;font-size:13px">Управлять тегами →</a>
        </div>
      </div>
      <section class="rail" style="margin-top:28px">
        <div class="rail-head"><h2>Похожие из твоих</h2>
          <span class="muted" style="font-size:13px">по описанию и вайбу</span>
        </div>
        <div class="rail-track drag-scroll">
          ${similar.items?.length ? similar.items.map(cardHtml).join("") : `<div class="empty">Добавь ещё видео — появятся похожие по смыслу</div>`}
        </div>
      </section>
      <section class="rail" style="margin-top:18px">
        <div class="rail-head"><h2>Похожие на YouTube</h2>
          <span class="muted" style="font-size:13px">${ytRelated.query ? escapeHtml(ytRelated.query) : "по теме"}</span>
        </div>
        <div class="rail-track drag-scroll" id="yt-related-rail">
          ${(ytRelated.items || []).length
            ? ytRelated.items.map((it) => `
              <div class="card yt-discover-card" data-video-id="${escapeHtml(it.video_id)}">
                <a class="card-main" href="${escapeHtml(it.watch_url)}" target="_blank" rel="noopener">
                  <div class="card-thumb">
                    <img src="${escapeHtml(it.thumb_url)}" alt="" loading="lazy" />
                    ${it.in_library ? `<span class="badge">уже есть</span>` : ""}
                  </div>
                  <div class="card-body">
                    <h3 class="card-title">${escapeHtml(it.title)}</h3>
                    <div class="card-meta">${escapeHtml(it.channel_title || "")}</div>
                  </div>
                </a>
                <div class="card-actions">
                  <a class="btn play-btn" href="${escapeHtml(it.watch_url)}" target="_blank" rel="noopener">▶</a>
                  ${it.in_library
                    ? `<a class="btn ghost" href="/v/${encodeURIComponent(it.video_id)}" data-nav>Открыть</a>`
                    : `<button type="button" class="btn secondary" data-save-yt="${escapeHtml(it.video_id)}">В очередь</button>`}
                </div>
              </div>`).join("")
            : `<div class="empty">Не нашлось — проверь YOUTUBE_API_KEY или попробуй другой ролик</div>`}
        </div>
      </section>
      <div id="note-sheet" class="note-sheet hidden"></div>`;
    wireNav();
    enableDragScroll(app);
    wireCardMenus(app);
    const lists = await api("/api/lists");
    const sel = $("#list-select");
    sel.innerHTML = (lists.lists || []).map((l) =>
      `<option value="${l.id}">${escapeHtml(l.title)}</option>`
    ).join("") || `<option value="">Нет списков</option>`;

    const refreshTags = (nextItem) => {
      const box = $("#assigned-tags");
      if (box) box.innerHTML = tagPillsHtml(nextItem.user_tags || [], { removable: true, videoId });
      wireUntag();
      // refresh picker state without full reload
      const ids = new Set((nextItem.user_tags || []).map((t) => t.id));
      document.querySelectorAll("[data-toggle-tag]").forEach((btn) => {
        const id = Number(btn.getAttribute("data-toggle-tag"));
        const on = ids.has(id);
        btn.classList.toggle("tag-pill-on", on);
        const name = btn.getAttribute("data-tag-name") || "";
        btn.textContent = on ? `${name} ✓` : name;
      });
    };

    function wireUntag() {
      document.querySelectorAll("[data-untag]").forEach((btn) => {
        btn.onclick = async (e) => {
          e.preventDefault();
          try {
            const r = await api(
              `/api/videos/${encodeURIComponent(videoId)}/tags/${btn.getAttribute("data-untag")}`,
              { method: "DELETE" }
            );
            refreshTags(r.item || { user_tags: [] });
            toast("Тег снят");
          } catch (err) {
            toast(err.message);
          }
        };
      });
    }
    wireUntag();

    document.querySelectorAll("[data-toggle-tag]").forEach((btn) => {
      btn.onclick = async () => {
        const tagId = Number(btn.getAttribute("data-toggle-tag"));
        const name = btn.getAttribute("data-tag-name");
        const on = btn.classList.contains("tag-pill-on");
        try {
          if (on) {
            const r = await api(
              `/api/videos/${encodeURIComponent(videoId)}/tags/${tagId}`,
              { method: "DELETE" }
            );
            refreshTags(r.item || { user_tags: [] });
          } else {
            const r = await api(`/api/videos/${encodeURIComponent(videoId)}/tags`, {
              method: "POST",
              body: JSON.stringify({ tag_id: tagId, name }),
            });
            refreshTags(r.item || { user_tags: r.user_tags || [] });
            toast(`Тег: ${name}`);
          }
        } catch (err) {
          toast(err.message);
        }
      };
    });

    $("#open-yt").onclick = async () => {
      try {
        const r = await api(`/api/videos/${encodeURIComponent(videoId)}/open`, {
          method: "POST",
          body: "{}",
        });
        window.open(r.watch_url || item.watch_url, "_blank", "noopener");
        if (r.moved_to_started) toast("Ушло в «Начатые» — из очереди убрано");
        else if (item.status === "queue") toast("Открыто");
      } catch (_) {
        window.open(item.watch_url, "_blank", "noopener");
      }
    };
    $("#mark-started").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "in_progress" }),
      });
      toast("В «Начатые» — из очереди убрано");
      renderVideo(videoId);
    };
    $("#mark-watched").onclick = () => {
      showUndo({
        message: "Просмотрено",
        seconds: 8,
        onUndo: () => {},
        onCommit: async () => {
          try {
            await api(`/api/library/${encodeURIComponent(videoId)}`, {
              method: "PATCH",
              body: JSON.stringify({ status: "watched" }),
            });
            openLexiconPrompt(videoId, { note: noteVal, title: item.title || "" });
            // soft refresh status without killing the prompt
            const btn = $("#mark-watched");
            if (btn) {
              btn.disabled = true;
              btn.textContent = "Уже в просмотренных";
            }
          } catch (e) {
            toast(e.message);
          }
        },
      });
    };
    // Remove old note-sheet inline handler block — lexicon is global
    const saveNoteBtn = $("#save-note");
    if (saveNoteBtn) {
      saveNoteBtn.onclick = async () => {
        const note = ($("#user-note")?.value || "").trim();
        await api(`/api/library/${encodeURIComponent(videoId)}`, {
          method: "PATCH",
          body: JSON.stringify({ note }),
        });
        toast(note ? "Описание сохранено" : "Описание очищено");
      };
    }
    document.querySelectorAll("[data-save-yt]").forEach((btn) => {
      btn.onclick = async () => {
        const vid = btn.getAttribute("data-save-yt");
        try {
          await api("/api/videos/save", {
            method: "POST",
            body: JSON.stringify({ url: `https://www.youtube.com/watch?v=${vid}` }),
          });
          toast("В очереди");
          btn.textContent = "Уже есть";
          btn.disabled = true;
        } catch (e) {
          toast(e.message);
        }
      };
    });
    $("#back-queue").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "queue" }),
      });
      toast("Снова в очереди");
      renderVideo(videoId);
    };
    $("#delete-item").onclick = () => {
      showUndo({
        message: "Убрать из библиотеки",
        seconds: 8,
        onUndo: () => {},
        onCommit: async () => {
          try {
            await api(`/api/library/${encodeURIComponent(videoId)}`, { method: "DELETE" });
            navigate("/queue");
          } catch (e) {
            toast(e.message);
          }
        },
      });
    };
    $("#add-tag").onclick = async () => {
      const name = $("#new-tag").value.trim();
      if (!name) return toast("Напиши тег");
      try {
        // create predefined + assign
        await api("/api/tags", { method: "POST", body: JSON.stringify({ name }) });
        const r = await api(`/api/videos/${encodeURIComponent(videoId)}/tags`, {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        toast(`Тег «${name}»`);
        renderVideo(videoId);
      } catch (e) {
        toast(e.message);
      }
    };
    $("#ai-tag").onclick = async () => {
      const btn = $("#ai-tag");
      btn.classList.add("busy");
      const box = mountProgress($("#ai-out"), {
        title: "Смотрю ролик",
        detail: "Подбираю тему и теги",
      });
      try {
        const r = await runBusySteps(box, [
          { title: "Читаю название и описание", detail: "контекст ролика" },
          { title: "Спрашиваю модель", detail: "тема и теги" },
          { title: "Вешаю теги", detail: "в библиотеку" },
        ], api(`/api/videos/${encodeURIComponent(videoId)}/suggest-themes`, {
          method: "POST",
          body: JSON.stringify({ apply: true }),
        }));
        finishProgress(box, {
          ok: true,
          title: "Теги готовы",
          detail: (r.suggestion?.tags || []).join(", ") || "без новых тегов",
        });
        toast(r.suggestion?.tags?.length ? `Теги: ${r.suggestion.tags.join(", ")}` : "Готово");
        setTimeout(() => renderVideo(videoId), 500);
      } catch (e) {
        finishProgress(box, { ok: false, title: "Не вышло", detail: e.message });
        toast(e.message);
      } finally {
        btn.classList.remove("busy");
      }
    };
    $("#add-to-list").onclick = async () => {
      const listId = sel.value;
      if (!listId) return toast("Сначала создай список");
      await api(`/api/lists/${listId}/items`, {
        method: "POST",
        body: JSON.stringify({ video_id: videoId }),
      });
      toast("В списке");
    };
  }

  async function navigate(path, replace = false) {
    if (replace) history.replaceState({}, "", path);
    else if (location.pathname + location.search !== path) history.pushState({}, "", path);
    await route();
  }

  async function route() {
    const path = location.pathname;
    if (path === "/auth/callback") return renderAuthCallback();
    const needAuth = path !== "/login";
    if (needAuth) {
      const ok = await ensureAuth();
      if (!ok) return renderLogin();
    }
    if (path === "/" || path === "/home") return renderHome();
    if (path === "/queue") return renderQueue();
    if (path === "/channels") return renderChannels();
    if (path === "/organize") return renderOrganize();
    if (path === "/search") return renderSearch();
    if (path === "/add") return renderAdd();
    if (path === "/lists") return renderLists();
    if (path === "/tags") return renderTagsPage();
    if (path === "/onboard" || path === "/settings") return renderOnboard();
    if (path === "/login") return renderLogin();
    const m = path.match(/^\/v\/([^/]+)/);
    if (m) return renderVideo(decodeURIComponent(m[1]));
    return renderHome();
  }

  window.addEventListener("popstate", () => route());
  document.querySelectorAll("#bottom-nav button").forEach((b) => {
    b.onclick = () => navigate(b.getAttribute("data-route"));
  });

  route();
})();
