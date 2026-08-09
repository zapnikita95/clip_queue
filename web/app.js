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

  /** Tone: calm, Вы, warm. Values: Kairos · Chronos · Kyber · Curate */
  const FAQ_ITEMS = [
    {
      q: "Почему Kyro?",
      a: `Каждый день мы сохраняем десятки видео: полезные лекции, идеи для проектов, туториалы, интервью, мысли, к которым хочется вернуться позже.

Но со временем YouTube превращается не в библиотеку, а в хаос. Ценные знания теряются среди сотен вкладок, плейлистов и забытых сохранений.

Kyro создан, чтобы вернуть порядок.

Название вдохновлено несколькими идеями.

Kairos — древнегреческое слово, означающее правильный момент или подходящее время. Это идея не просто хранить информацию, а находить её именно тогда, когда она нужна.

Chronos — время, напоминание о том, что наши сохранённые видео становятся частью личной истории: архивом мыслей, открытий и знаний.

Kyber — от греческого корня, связанного с управлением и навигацией. Как капитан управляет кораблём, Kyro помогает ориентироваться в потоке контента и направлять его в нужную сторону.

Curate — идея отбора и создания коллекции. Kyro не просто собирает видео — он помогает превратить случайный поток информации в осмысленную библиотеку.

Из этих идей родилось имя Kyro: место, где время, знания и порядок встречаются.`,
    },
    {
      q: "Что такое Kyro?",
      a: "Kyro — спокойное место для вашей библиотеки YouTube. Вы сохраняете ролики, раскладываете их по папкам и тегам и возвращаетесь к ним в нужный момент — без шума чужой ленты.",
    },
    {
      q: "Как добавить видео?",
      a: "В Android откройте ролик в YouTube и нажмите «Поделиться» → Kyro. В вебе вставьте ссылку через «Добавить» или сохраните из браузера. Мы бережно положим видео в вашу библиотеку.",
    },
    {
      q: "Что такое сохранённые?",
      a: "Это ролики, которые вы хотите посмотреть позже. Не бесконечная лента рекомендаций, а ваша личная библиотека: смотрите в подходящее время, отмечайте просмотренное и двигайтесь дальше.",
    },
    {
      q: "Как работает синхронизация с YouTube?",
      a: "После входа через Google Kyro может аккуратно подтянуть ваши лайки и плейлисты. Обновление забирает недавние изменения; полное обновление проходит библиотеку шире. Вы управляете этим из настроек.",
    },
    {
      q: "Зачем папки и теги?",
      a: "Папки и теги помогают курировать поток: собрать лекции отдельно от развлечений, отметить темы и быстрее находить нужное. Так случайные сохранения становятся осмысленной библиотекой.",
    },
    {
      q: "Что такое Google Takeout?",
      a: "Takeout — выгрузка ваших данных Google. Если загрузите watch-history.json, мы отметим уже просмотренные ролики в библиотеке. Это помогает привести историю в порядок без ручной работы.",
    },
    {
      q: "Можно ли смотреть видео внутри Kyro?",
      a: "Сейчас воспроизведение открывается на YouTube — там, где лежит сам ролик. Kyro помогает выбрать, что смотреть, и сохранить контекст; просмотр остаётся на привычной платформе.",
    },
  ];

  function faqSparkleBtnHtml() {
    return `<button type="button" class="faq-sparkle-btn" id="open-faq" title="Вопросы и ответы" aria-label="Вопросы и ответы">
      <span class="moth" aria-hidden="true"></span>
      <span class="moth" aria-hidden="true"></span>
      <span class="moth" aria-hidden="true"></span>
      ?
    </button>`;
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
          toast("Сохранили вашу формулировку");
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
        return `<span class="tag-pill tag-pill-edit" data-tag-id="${t.id}">
          <span>${escapeHtml(label)}</span>
          <button type="button" class="tag-x" data-untag="${t.id}" title="Снять тег" aria-label="Снять тег">×</button>
        </span>`;
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
          <button type="button" data-act="plan-tonight">В план на вечер</button>
          <button type="button" data-act="plan-week">В план на неделю</button>
          <button type="button" data-act="remind">Напомнить позже</button>
          <button type="button" data-act="reclassify">Не туда — другая папка</button>
          ${listId ? `<button type="button" data-act="remove-cat">Убрать из категории</button>` : ""}
          ${draftFolder ? `<button type="button" data-act="remove-draft">Убрать из категории</button>` : ""}
          <button type="button" data-act="dismiss" class="danger">Убрать из Kyro</button>
        </div>
      </div>`;
  }

  function cardHtml(item, opts = {}) {
    const listId = opts.listId || "";
    const row = !!opts.row;
    const dur = item.duration_label ? `<span class="badge">${escapeHtml(item.duration_label)}</span>` : "";
    const boost = Number(item.interest || 0);
    const boostMark = boost >= 2 ? "🔥🔥" : boost === 1 ? "🔥" : boost < 0 ? "↓" : "";
    const pills = (item.user_tags || []).slice(0, 3).map((t) =>
      `<span class="tag-pill tag-pill-sm">${escapeHtml((t.emoji || "") + " " + t.name)}</span>`
    ).join("");
    const cls = row ? "card card-row" : "card";
    return `
      <div class="${cls}" data-video-id="${escapeHtml(item.video_id)}" data-list-id="${escapeHtml(String(listId || ""))}" data-interest="${boost}">
        <span class="moth" aria-hidden="true"></span>
        <span class="moth" aria-hidden="true"></span>
        <span class="moth" aria-hidden="true"></span>
        ${cardMenuHtml(item, { listId })}
        <a class="card-main" href="/v/${encodeURIComponent(item.video_id)}" data-nav draggable="false">
          <div class="card-thumb">
            <img src="${escapeHtml(item.thumb_url)}" alt="" loading="lazy" draggable="false" />
            <button type="button" class="thumb-eye" data-act="watched" title="Просмотрено" aria-label="Просмотрено">👁</button>
            ${dur}
            ${boostMark ? `<span class="card-boost">${boostMark}</span>` : ""}
          </div>
          <div class="card-body">
            ${item.reason ? `<div class="muted" style="font-size:12px;margin-bottom:4px">${escapeHtml(item.reason)}</div>` : ""}
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

  function recentListHtml(items, opts = {}) {
    if (!items.length) return `<div class="empty">Пусто</div>`;
    return `<div class="recent-list">${items.map((it) => cardHtml(it, { ...opts, row: true })).join("")}</div>`;
  }

  function reorderRailsAfterInterest(videoId, level, boosted = []) {
    const boostSet = new Set([videoId, ...(boosted || [])].map(String));
    document.querySelectorAll(".rail-track").forEach((track) => {
      const cards = [...track.querySelectorAll(".card[data-video-id]")];
      if (!cards.some((c) => c.getAttribute("data-video-id") === videoId)) return;
      cards.forEach((c) => {
        const vid = c.getAttribute("data-video-id");
        let cur = Number(c.getAttribute("data-interest") || 0);
        if (vid === videoId) cur = level;
        else if (boostSet.has(vid) && level >= 1) cur = Math.min(2, Math.max(cur, level >= 2 ? 1 : cur || 1));
        else if (boostSet.has(vid) && level < 0) cur = Math.max(-1, cur - 1);
        c.setAttribute("data-interest", String(cur));
        const mark = c.querySelector(".card-boost");
        if (mark) mark.remove();
        if (cur >= 1) {
          const thumb = c.querySelector(".card-thumb");
          if (thumb) {
            const span = document.createElement("span");
            span.className = "card-boost";
            span.textContent = cur >= 2 ? "🔥🔥" : "🔥";
            thumb.appendChild(span);
          }
        }
      });
      cards
        .sort((a, b) => Number(b.getAttribute("data-interest") || 0) - Number(a.getAttribute("data-interest") || 0))
        .forEach((c) => track.appendChild(c));
      const primary = track.querySelector(`.card[data-video-id="${CSS.escape(videoId)}"]`);
      if (primary) {
        primary.classList.add("card-spark");
        setTimeout(() => primary.classList.remove("card-spark"), 700);
        if (level >= 1) {
          primary.scrollIntoView({ inline: "start", behavior: "smooth", block: "nearest" });
        } else if (level < 0) {
          primary.scrollIntoView({ inline: "end", behavior: "smooth", block: "nearest" });
        }
      }
    });
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
        const r = await api(`/api/library/${encodeURIComponent(videoId)}`, {
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
        reorderRailsAfterInterest(videoId, level, r.boosted || []);
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
          message: "Убрано из Kyro",
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
      } else if (act === "plan-tonight" || act === "plan-week") {
        const bucket = act === "plan-week" ? "week" : "tonight";
        await api("/api/home/plan", {
          method: "POST",
          body: JSON.stringify({ action: "add", bucket, video_id: videoId }),
        });
        toast(bucket === "week" ? "В плане на неделю" : "В плане на вечер");
      } else if (act === "remind") {
        const hours = parseInt(window.prompt("Через сколько часов напомнить?", "4") || "4", 10);
        const at = new Date(Date.now() + Math.max(1, hours || 4) * 3600 * 1000).toISOString();
        await api("/api/reminders", {
          method: "POST",
          body: JSON.stringify({ video_id: videoId, remind_at: at }),
        });
        toast("Напоминание сохранено");
      } else if (act === "reclassify") {
        const lists = await api("/api/lists").catch(() => ({ lists: [] }));
        const opts = (lists.lists || []).filter((l) => {
          const t = (l.title || "");
          return !t.startsWith("YT:") && !/скрыто/i.test(t);
        });
        if (!opts.length) {
          toast("Сначала создайте папки в «Разложить»");
          return;
        }
        const pick = window.prompt(
          "Номер папки:\n" + opts.map((l, i) => `${i + 1}. ${l.title}`).join("\n"),
          "1"
        );
        const idx = Math.max(0, (parseInt(pick || "1", 10) || 1) - 1);
        const target = opts[idx];
        if (!target) return;
        const r = await api(`/api/videos/${encodeURIComponent(videoId)}/reclassify`, {
          method: "POST",
          body: JSON.stringify({ list_id: target.id }),
        });
        toast(r.list_title ? `Переложили в «${r.list_title}»` : "Готово");
        if (listId) {
          document.querySelectorAll(
            `.card[data-video-id="${CSS.escape(videoId)}"][data-list-id="${CSS.escape(String(listId))}"]`
          ).forEach((el) => el.remove());
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
        <a class="brand" href="/home" data-nav aria-label="Kyro">
          <div class="brand-mark">
            <span class="brand-mark-text">Kyro</span>
          </div>
        </a>
        <form class="smart-search" id="smart-search" action="/search" method="get">
          <input type="search" name="q" id="smart-q" placeholder="Что хотите посмотреть?" autocomplete="off" enterkeyhint="search" />
          <button type="button" class="smart-mic" id="smart-mic" title="Голосом" aria-label="Голосом">🎤</button>
          <button type="submit" class="smart-go" title="Найти">⌕</button>
        </form>
        <nav class="nav">
          <button class="nav-btn ${active === "home" ? "active" : ""}" data-route="/home">Главная</button>
          <button class="nav-btn ${active === "queue" ? "active" : ""}" data-route="/queue">Библиотека</button>
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
      if (!q) return toast("Напишите, что ищете");
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
      let dragging = false;
      let startX = 0;
      let startY = 0;
      let startScroll = 0;
      let pointerId = null;
      const THRESH = 12;

      const isControl = (target) =>
        !!target.closest(
          "button, select, input, textarea, label, .card-menu, .play-btn, .thumb-eye, .eye-btn, .rail-handle, .folder-assign, a.btn"
        );

      el.addEventListener("pointerdown", (e) => {
        if (e.pointerType === "mouse" && e.button !== 0) return;
        if (isControl(e.target)) return;
        if (e.target.closest(".folder-tile[draggable='true']")) return;
        down = true;
        dragging = false;
        startX = e.clientX;
        startY = e.clientY;
        startScroll = el.scrollLeft;
        pointerId = e.pointerId;
        // Don't capture yet — plain click must open the card
      });

      el.addEventListener("pointermove", (e) => {
        if (!down) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        if (!dragging) {
          if (Math.abs(dx) < THRESH && Math.abs(dy) < THRESH) return;
          // Vertical page scroll → abort rail drag
          if (Math.abs(dy) > Math.abs(dx) + 2) {
            down = false;
            return;
          }
          dragging = true;
          el.classList.add("is-dragging");
          try {
            el.setPointerCapture(pointerId);
          } catch (_) {}
        }
        el.scrollLeft = startScroll - dx;
        e.preventDefault();
      });

      const endDrag = (e) => {
        const wasDragging = dragging;
        down = false;
        dragging = false;
        el.classList.remove("is-dragging");
        if (wasDragging) {
          // Swallow the click that follows a drag
          const kill = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
          };
          el.addEventListener("click", kill, { capture: true, once: true });
        }
      };
      el.addEventListener("pointerup", endDrag);
      el.addEventListener("pointercancel", endDrag);

      el.addEventListener("dragstart", (e) => {
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
          <h2>Kyro</h2>
          <p class="hint">Войдите через Google — мы бережно соберём ваши лайки и плейлисты в одну библиотеку.</p>
          ${err ? `<p class="hint" style="color:#ff8a80">Не удалось войти: ${escapeHtml(err)}</p>` : ""}
          <div class="btn-row" style="flex-direction:column;align-items:stretch">
            ${status.configured
              ? `<a class="btn" href="/api/auth/google/start" style="text-align:center">Войти через Google</a>`
              : `<div class="empty">Google OAuth ещё не настроен на сервере. Пока можно воспользоваться быстрым входом для разработки.</div>`}
            <button class="btn ghost" id="dev-login">Быстрый вход (для разработки)</button>
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
            title: last.title || "YouTube у тебя в Kyro",
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
    // If Android Custom Tabs landed here by mistake — bounce into the app.
    const ua = navigator.userAgent || "";
    if (/Android/i.test(ua)) {
      const deep = `clipqueue://auth?token=${encodeURIComponent(t)}&autosync=${encodeURIComponent(params.get("autosync") || "0")}`;
      const intent =
        `intent://auth?token=${encodeURIComponent(t)}` +
        `&autosync=${encodeURIComponent(params.get("autosync") || "0")}` +
        `#Intent;scheme=clipqueue;package=ru.clipqueue.app;end`;
      location.replace(intent);
      setTimeout(() => { location.href = deep; }, 300);
      app.innerHTML = `<section class="hero"><h1>Открываю приложение…</h1>
        <p><a class="btn" href="${deep}">Открыть Kyro</a></p></section>`;
      return;
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
      return navigate("/settings?autosync=1", true);
    }
    return navigate("/home", true);
  }

  async function renderOnboard() {
    const meData = await api("/api/me");
    const wantAutosync =
      new URL(location.href).searchParams.get("autosync") === "1" &&
      !(meData.library_count > 0);
    app.innerHTML = `
      ${topbar("settings")}
      <section class="hero hero-compact hero-with-faq">
        <div>
          <h1>Настройки</h1>
          <p class="muted" style="margin:6px 0 0">Управляйте библиотекой спокойно и в своём темпе</p>
        </div>
        ${faqSparkleBtnHtml()}
      </section>
      <div class="panel" style="margin-bottom:16px">
        <h2>YouTube</h2>
        <p class="muted">${meData.youtube_connected ? "подключён" : "нужно подключить Google"} · ${meData.library_count || 0} видео</p>
        <div class="btn-row">
          <button class="btn" id="sync-yt" ${meData.youtube_connected ? "" : "disabled"}>Обновить библиотеку</button>
          <button class="btn secondary" id="sync-yt-full" ${meData.youtube_connected ? "" : "disabled"}>Полное обновление</button>
          ${!meData.youtube_connected && meData.google_oauth_configured
            ? `<a class="btn secondary" href="/api/auth/google/start">Подключить Google</a>` : ""}
        </div>
        <div id="sync-out"></div>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>Категории</h2>
        <p class="muted" style="margin:0 0 10px">Разложите поток по темам — так сохранения становятся коллекцией.</p>
        <div class="btn-row">
          <a class="btn" href="/organize" data-nav>Разложить</a>
        </div>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>Takeout</h2>
        <p class="muted" style="margin:0 0 10px">Загрузите историю просмотров, чтобы отметить уже просмотренное.</p>
        <div class="btn-row">
          <label class="file-btn">
            JSON истории
            <input type="file" id="takeout-file" accept=".json,application/json" />
          </label>
        </div>
        <div id="takeout-out"></div>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>Дайджест</h2>
        <p class="muted" style="margin:0 0 10px">Раз в неделю — идеи из вашей очереди (автопуш + вручную). Тихие часы — без пушей.</p>
        <label class="muted" style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
          <input type="checkbox" id="digest-enabled" checked /> Включить еженедельный дайджест
        </label>
        <div class="btn-row" style="margin-bottom:8px">
          <label class="muted" style="font-size:13px">Тихо с
            <input type="number" id="quiet-start" min="0" max="23" value="23" style="width:56px;margin:0 6px" />
            до
            <input type="number" id="quiet-end" min="0" max="23" value="8" style="width:56px;margin:0 6px" />
            (UTC)
          </label>
          <button type="button" class="btn secondary" id="prefs-save">Сохранить</button>
        </div>
        <div class="btn-row">
          <button type="button" class="btn secondary" id="digest-preview">Посмотреть текст</button>
          <button type="button" class="btn" id="digest-send">Отправить себе</button>
        </div>
        <div id="digest-out" class="muted" style="margin-top:10px;white-space:pre-wrap;font-size:13px"></div>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>Метрики недели</h2>
        <p class="muted" style="margin:0 0 8px">North star: просмотры из плана Kyro.</p>
        <div id="metrics-out" class="muted" style="font-size:13px">Загрузка…</div>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>Расширение Chrome</h2>
        <p class="muted" style="margin:0 0 10px">Кнопка «В Kyro» на странице YouTube. Установите как распакованное расширение из папки <code>extension/</code> в репозитории.</p>
        <p class="muted" style="margin:0;font-size:13px">chrome://extensions → режим разработчика → «Загрузить распакованное» → выберите папку extension.</p>
      </div>
      <div class="panel">
        <h2>Аккаунт</h2>
        <p class="muted">${escapeHtml(meData.user?.email || me?.email || "")}</p>
        <div class="btn-row">
          <a class="btn ghost" href="https://movie-planner.ru/?open_login=1" target="_blank" rel="noopener">Кино — Movie Planner</a>
          <button class="btn secondary" id="settings-logout">Выйти</button>
        </div>
      </div>`;
    wireNav();
    try {
      const prefs = await api("/api/prefs");
      const p = prefs.prefs || {};
      const de = $("#digest-enabled");
      if (de) de.checked = p.digest_enabled !== false;
      const qs = $("#quiet-start");
      const qe = $("#quiet-end");
      if (qs && p.quiet_start != null) qs.value = p.quiet_start;
      if (qe && p.quiet_end != null) qe.value = p.quiet_end;
      const m = await api("/api/metrics/summary");
      const mo = $("#metrics-out");
      if (mo) {
        mo.innerHTML = `Planned watches: <b>${m.weekly_planned_watches || 0}</b> · дней с surface: <b>${m.surface_active_days || 0}</b> · в тематических папках: <b>${m.depth_themed_pct || 0}%</b>`;
      }
    } catch (_) {
      const mo = $("#metrics-out");
      if (mo) mo.textContent = "Нет данных";
    }
    const prefsSave = $("#prefs-save");
    if (prefsSave) {
      prefsSave.onclick = async () => {
        try {
          await api("/api/prefs", {
            method: "POST",
            body: JSON.stringify({
              digest_enabled: !!$("#digest-enabled")?.checked,
              quiet_start: Number($("#quiet-start")?.value || 23),
              quiet_end: Number($("#quiet-end")?.value || 8),
            }),
          });
          toast("Сохранено");
        } catch (e) {
          toast(e.message);
        }
      };
    }
    const digPrev = $("#digest-preview");
    const digSend = $("#digest-send");
    const digOut = $("#digest-out");
    if (digPrev) {
      digPrev.onclick = async () => {
        try {
          const d = await api("/api/home/digest");
          if (digOut) digOut.textContent = d.text || d.body || "";
        } catch (e) {
          toast(e.message);
        }
      };
    }
    if (digSend) {
      digSend.onclick = async () => {
        try {
          const d = await api("/api/home/digest/send", { method: "POST", body: "{}" });
          if (digOut) digOut.textContent = (d.digest && d.digest.text) || `Отправлено: ${d.sent || 0}`;
          toast(d.sent ? "Дайджест отправлен" : "Нет устройств для пуша — текст ниже");
        } catch (e) {
          toast(e.message);
        }
      };
    }
    const faqBtn = $("#open-faq");
    if (faqBtn) faqBtn.onclick = () => navigate("/faq");
    const settingsLogout = $("#settings-logout");
    if (settingsLogout) {
      settingsLogout.onclick = async () => {
        try { await api("/api/auth/logout", { method: "POST", body: "{}" }); } catch (_) {}
        setToken("");
        me = null;
        navigate("/login", true);
      };
    }
    $("#sync-yt").onclick = () => runYoutubeSync({ autoGoHome: false, full: false });
    const fullBtn = $("#sync-yt-full");
    if (fullBtn) {
      fullBtn.onclick = () => {
        if (!confirm("Полное обновление заново обойдёт лайки и плейлисты. Продолжить?")) return;
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
        title: "Читаем Takeout",
        detail: file.name,
      });
      try {
        const text = await file.text();
        updateProgress(box, { pct: 18, title: "Разбираем JSON", detail: `${Math.round(file.size / 1024)} КБ` });
        const json = JSON.parse(text);
        const data = await runBusySteps(box, [
          { title: "Загружаем историю на сервер", detail: "watch-history.json" },
          { title: "Разбираем просмотры", detail: "складываем в библиотеку" },
          { title: "Отмечаем уже просмотренные", detail: "статус watched" },
          { title: "Почти готово", detail: "сохраняем итог" },
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
        finishProgress(box, { ok: false, title: "Импорт не удался", detail: e.message });
        toast(e.message);
      }
    };
  }

  async function renderFaq() {
    app.innerHTML = `
      ${topbar("settings")}
      <section class="hero hero-compact">
        <h1>Вопросы и ответы</h1>
        <p>Спокойные ответы о Kyro и вашей библиотеке</p>
      </section>
      <div class="faq-list">
        ${FAQ_ITEMS.map((it, i) => `
          <details class="faq-item"${i === 0 ? " open" : ""}>
            <summary>${escapeHtml(it.q)}</summary>
            <div class="faq-body">${escapeHtml(it.a)}</div>
          </details>
        `).join("")}
      </div>
      <div class="btn-row" style="margin-top:20px">
        <a class="btn ghost" href="/settings" data-nav>← К настройкам</a>
      </div>`;
    wireNav();
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
    const pendingClassify = Number(structure.pending_classify || 0);
    const recentSource = (structure.recent_source || "").trim();
    const classifyJob = structure.classify_job || null;
    const canResumeClassify = !!(
      classifyJob
      && (classifyJob.status === "paused" || (classifyJob.status === "error" && classifyJob.resumable))
      && (classifyJob.done || classifyJob.done_ids_count)
    );
    const has = !!structure.has_structure && folders.length;

    const classifyBtnLabel = canResumeClassify
      ? `Продолжить · ${classifyJob.done || classifyJob.done_ids_count || 0}/${classifyJob.total || "?"}`
      : (pendingClassify > 0 ? `Разобрать · ${pendingClassify}` : "");

    const growingHtml = "";
    const classifyOnly = (pendingClassify > 0 || canResumeClassify)
      ? `<div class="btn-row" style="margin:10px 0 4px">
          <button type="button" class="btn home-classify-btn" id="home-classify">${escapeHtml(classifyBtnLabel)}</button>
        </div>
        <div id="home-classify-progress" class="home-classify-progress"></div>`
      : `<div id="home-classify-progress" class="home-classify-progress"></div>`;

    app.innerHTML = `
      ${topbar("home")}
      <section class="hero hero-compact">
        <h1>${has ? "Что посмотреть" : "Разложите видео"}</h1>
        <p class="hero-sub muted">План из того, что вы уже хотели — не лента</p>
        <div class="stats stats-compact">
          <div class="stat"><b>${folders.length}</b> папок</div>
          <div class="stat"><b>${shell.counts?.queue ?? "—"}</b> в очереди</div>
          <div class="stat"><b>${shell.counts?.started || 0}</b> начатых</div>
          <div class="stat muted" id="home-sync-stat" style="display:none">Синк…</div>
        </div>
        ${classifyOnly}
      </section>
      <section class="now-block" id="now-block">
        <div class="rail-head">
          <h2>Сейчас</h2>
          <span class="muted" style="font-size:13px" id="now-meta">подбираем…</span>
        </div>
        <div class="filter-chips" id="now-slots"></div>
        <div class="filter-chips" id="now-moods"></div>
        <div class="rail-track drag-scroll" id="now-picks"><div class="empty">Загрузка…</div></div>
        <div class="rail-head" style="margin-top:14px" id="suggest-head" hidden>
          <h2 style="font-size:1.05rem">Можно посмотреть</h2>
          <span class="muted" style="font-size:13px">из вашего желаемого</span>
        </div>
        <div class="rail-track drag-scroll" id="now-suggestions"></div>
      </section>
      <section class="plan-block" id="plan-block">
        <div class="rail-head">
          <h2>План</h2>
          <span class="muted" style="font-size:13px">вечер и неделя — ваш слой поверх очереди</span>
        </div>
        <div class="rail-head" style="margin-top:8px"><h3 style="font-size:0.95rem;margin:0">На вечер</h3></div>
        <div class="rail-track drag-scroll" id="plan-tonight"><div class="empty muted">Добавьте ролики через ⋯ → «В план на вечер»</div></div>
        <div class="rail-head" style="margin-top:10px"><h3 style="font-size:0.95rem;margin:0">На неделю</h3></div>
        <div class="rail-track drag-scroll" id="plan-week"><div class="empty muted">Пока пусто</div></div>
      </section>
      <div id="inbox-onboard" class="panel inbox-onboard" hidden style="margin:0 0 16px"></div>
      <p class="mp-sister muted"><a href="https://movie-planner.ru/?open_login=1" target="_blank" rel="noopener">Кино — в Movie Planner</a></p>
      <div id="rails"></div>`;
    wireNav();

    // «Сейчас» — план под слот / сценарий
    let nowSlot = "any";
    let nowMood = "";
    const paintNow = async () => {
      const picksEl = $("#now-picks");
      const sugEl = $("#now-suggestions");
      const meta = $("#now-meta");
      try {
        const qs = new URLSearchParams({ slot: nowSlot, limit: "6" });
        if (nowMood) qs.set("mood", nowMood);
        const data = await api(`/api/home/now?${qs}`);
        api("/api/metrics/track", {
          method: "POST",
          body: JSON.stringify({
            event_type: "now_impression",
            surface: "home_now",
            meta: { slot: nowSlot, mood: nowMood || null, n: (data.picks || []).length },
          }),
        }).catch(() => {});
        if (meta) meta.textContent = data.slot_label || "";
        const slotsEl = $("#now-slots");
        if (slotsEl && !(slotsEl.dataset.ready)) {
          slotsEl.innerHTML = (data.slots || []).map((s) =>
            `<button type="button" class="chip ${s.id === nowSlot ? "active" : ""}" data-slot="${escapeHtml(s.id)}">${escapeHtml(s.label)}</button>`
          ).join("");
          slotsEl.dataset.ready = "1";
          slotsEl.querySelectorAll("[data-slot]").forEach((btn) => {
            btn.onclick = () => {
              nowSlot = btn.getAttribute("data-slot") || "any";
              slotsEl.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === btn));
              paintNow();
            };
          });
        }
        const moodsEl = $("#now-moods");
        if (moodsEl && !(moodsEl.dataset.ready)) {
          moodsEl.innerHTML =
            `<button type="button" class="chip ${!nowMood ? "active" : ""}" data-mood="">Все сценарии</button>` +
            (data.moods || []).map((m) =>
              `<button type="button" class="chip" data-mood="${escapeHtml(m.id)}" title="${escapeHtml(m.hint || "")}">${escapeHtml(m.label)}</button>`
            ).join("");
          moodsEl.dataset.ready = "1";
          moodsEl.querySelectorAll("[data-mood]").forEach((btn) => {
            btn.onclick = () => {
              nowMood = btn.getAttribute("data-mood") || "";
              moodsEl.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === btn));
              paintNow();
            };
          });
        }
        const picks = data.picks || [];
        const started = data.started || [];
        const merged = [...started.filter((s) => !picks.some((p) => p.video_id === s.video_id)), ...picks];
        if (picksEl) {
          picksEl.innerHTML = merged.length
            ? merged.map((it) => cardHtml({
                ...it,
                watch_url: it.watch_url || `https://www.youtube.com/watch?v=${it.video_id}`,
              })).join("")
            : `<div class="empty">Пока нечего предложить — сохраните видео или нажмите «Разобрать»</div>`;
          wireCardMenus(picksEl);
          enableDragScroll(picksEl.parentElement || document);
          picksEl.querySelectorAll("a.play-btn").forEach((a) => {
            a.addEventListener("click", () => {
              const card = a.closest("[data-video-id]");
              const vid = card && card.getAttribute("data-video-id");
              if (!vid) return;
              api(`/api/videos/${encodeURIComponent(vid)}/open`, {
                method: "POST",
                body: JSON.stringify({ surface: "now" }),
              }).catch(() => {});
            });
          });
        }
        const sug = data.suggestions || [];
        const sugHead = $("#suggest-head");
        if (sugEl) {
          if (sug.length) {
            if (sugHead) sugHead.hidden = false;
            sugEl.innerHTML = sug.map((it) => `
              <div class="card suggest-card" data-video-id="${escapeHtml(it.video_id)}">
                <a class="card-main" href="/v/${encodeURIComponent(it.video_id)}" data-nav>
                  <div class="card-thumb"><img src="${escapeHtml(it.thumb_url)}" alt="" loading="lazy" /></div>
                  <div class="card-body">
                    <div class="muted" style="font-size:12px;margin-bottom:4px">${escapeHtml(it.reason || "")}</div>
                    <h3 class="card-title">${escapeHtml(it.title)}</h3>
                    <div class="card-meta">${escapeHtml(it.channel_title || "")}${it.duration_label ? " · " + escapeHtml(it.duration_label) : ""}</div>
                  </div>
                </a>
                <div class="card-actions">
                  <a class="btn play-btn" href="${escapeHtml(it.watch_url || `https://www.youtube.com/watch?v=${it.video_id}`)}" target="_blank" rel="noopener" data-surface="suggestion">▶</a>
                </div>
              </div>`).join("");
            sugEl.querySelectorAll("a.play-btn").forEach((a) => {
              a.addEventListener("click", () => {
                const card = a.closest("[data-video-id]");
                const vid = card && card.getAttribute("data-video-id");
                if (!vid) return;
                api(`/api/videos/${encodeURIComponent(vid)}/open`, {
                  method: "POST",
                  body: JSON.stringify({ surface: "suggestion" }),
                }).catch(() => {});
              });
            });
          } else {
            if (sugHead) sugHead.hidden = true;
            sugEl.innerHTML = "";
          }
        }
      } catch (e) {
        if (picksEl) picksEl.innerHTML = `<div class="empty">${escapeHtml(e.message || "Не удалось подобрать")}</div>`;
      }
    };
    paintNow();

    const paintPlan = async () => {
      try {
        const plan = await api("/api/home/plan");
        const tn = $("#plan-tonight");
        const wk = $("#plan-week");
        if (tn) {
          tn.innerHTML = (plan.tonight || []).length
            ? plan.tonight.map((it) => cardHtml(it)).join("")
            : `<div class="empty muted">Добавьте ролики через ⋯ → «В план на вечер»</div>`;
          wireCardMenus(tn);
          enableDragScroll(tn.parentElement || document);
        }
        if (wk) {
          wk.innerHTML = (plan.week || []).length
            ? plan.week.map((it) => cardHtml(it)).join("")
            : `<div class="empty muted">Пока пусто</div>`;
          wireCardMenus(wk);
          enableDragScroll(wk.parentElement || document);
        }
      } catch (_) {}
    };
    paintPlan();

    (async () => {
      const box = $("#inbox-onboard");
      if (!box) return;
      try {
        const st = await api("/api/onboarding/inbox");
        if (st.onboarding_done && st.has_inbox) return;
        box.hidden = false;
        box.innerHTML = `
          <h2 style="margin:0 0 8px">Ваша спецпапка</h2>
          <p class="muted" style="margin:0 0 10px">${escapeHtml(st.hint || "")}</p>
          <p class="muted" style="margin:0 0 12px;font-size:13px">
            Создайте в YouTube плейлист «смотреть позже» или Listen later — после синка Kyro возьмёт его как inbox желаемого.
            Затем нажмите «Разобрать», чтобы разложить по папкам.
          </p>
          <div class="btn-row">
            <button type="button" class="btn" id="inbox-onboard-ok">Понятно</button>
            ${!st.has_inbox ? `<button type="button" class="btn secondary" id="inbox-sync">Синхронизировать YouTube</button>` : ""}
          </div>`;
        const ok = $("#inbox-onboard-ok");
        if (ok) {
          ok.onclick = async () => {
            await api("/api/onboarding/inbox/done", { method: "POST", body: "{}" });
            box.hidden = true;
          };
        }
        const syn = $("#inbox-sync");
        if (syn) syn.onclick = () => runYoutubeSync({ autoGoHome: false, full: false });
      } catch (_) {}
    })();

    // Quiet delta sync on every home open — keeps «Недавно» / спецпапка fresh
    (async () => {
      const syncStat = $("#home-sync-stat");
      try {
        const me = await api("/api/me").catch(() => ({}));
        if (!me.youtube_connected) return;
        const lastAt = me.last_youtube_sync && me.last_youtube_sync.at
          ? Date.parse(me.last_youtube_sync.at)
          : 0;
        if (lastAt && Date.now() - lastAt < 3 * 60 * 1000) return; // <3 мин — не дёргаем
        if (syncStat) {
          syncStat.style.display = "";
          syncStat.innerHTML = "Синк…";
        }
        const start = await api("/api/youtube/sync", {
          method: "POST",
          body: JSON.stringify({ full: false }),
        });
        let job = start.job || {};
        const jobId = job.id;
        let guard = 0;
        while (job.status === "running" && guard < 90) {
          guard += 1;
          if (syncStat) {
            syncStat.innerHTML = escapeHtml(job.detail || job.title || "Синк…");
          }
          await new Promise((r) => setTimeout(r, 1200));
          const st = await api(`/api/youtube/sync/status?job_id=${encodeURIComponent(jobId)}`);
          job = st.job || {};
        }
        if (syncStat) {
          if (job.status === "done") {
            const s = job.stats || {};
            const n = (s.liked_new || 0) + (s.playlist_items_new || 0) + (s.inbox_new || 0);
            syncStat.innerHTML = n > 0 ? `Синк: +${n}` : "Синк ок";
            if (n > 0) setTimeout(() => renderHome(), 400);
            else setTimeout(() => { if (syncStat) syncStat.style.display = "none"; }, 2500);
          } else {
            syncStat.innerHTML = "Синк не удался";
          }
        }
      } catch (_) {
        if (syncStat) syncStat.style.display = "none";
      }
    })();

    const classifyBtn = $("#home-classify");
    if (classifyBtn) {
      const pollClassifyStatus = async (jobId) => {
        let lastErr = null;
        for (let attempt = 0; attempt < 6; attempt++) {
          try {
            const st = await api(`/api/organize/classify-pending/${encodeURIComponent(jobId)}`);
            return st.job || {};
          } catch (e) {
            lastErr = e;
            // Railway 502 on poll — job usually still running; retry
            if (e.status === 502 || e.status === 503 || e.status === 504) {
              await new Promise((r) => setTimeout(r, 1200 + attempt * 800));
              continue;
            }
            throw e;
          }
        }
        throw lastErr || new Error("HTTP 502");
      };

      const runClassify = async ({ resume = false } = {}) => {
        const boxHost = $("#home-classify-progress");
        classifyBtn.disabled = true;
        const box = mountProgress(boxHost, {
          title: resume ? "Продолжаю разбор" : "Разбираю новые",
          detail: resume ? "С чекпоинта…" : "Кладу видео по папкам…",
        });
        const showResumeUi = (job) => {
          finishProgress(box, {
            ok: false,
            title: "Разбор прерван",
            detail: job.detail || "Прогресс сохранён — можно продолжить",
            pct: Math.min(99, Number(job.pct) || 5),
          });
          const actions = document.createElement("div");
          actions.className = "btn-row";
          actions.style.marginTop = "10px";
          actions.innerHTML = `<button type="button" class="btn" id="classify-resume-btn">Продолжить</button>
            <button type="button" class="btn ghost" id="classify-dismiss-btn">Позже</button>`;
          boxHost.appendChild(actions);
          const resumeBtn = $("#classify-resume-btn");
          if (resumeBtn) {
            resumeBtn.onclick = () => runClassify({ resume: true });
          }
          const dismiss = $("#classify-dismiss-btn");
          if (dismiss) {
            dismiss.onclick = () => {
              classifyBtn.disabled = false;
              classifyBtn.textContent = `Продолжить · ${job.done || 0}/${job.total || "?"}`;
            };
          }
          classifyBtn.disabled = false;
          classifyBtn.textContent = `Продолжить · ${job.done || 0}/${job.total || "?"}`;
        };

        try {
          const start = await api("/api/organize/classify-pending", {
            method: "POST",
            body: JSON.stringify({ limit: 200, use_llm: true, resume }),
          });
          let job = start.job || {};
          const jobId = job.id;
          const t0 = Date.now();
          let streak502 = 0;
          while (job.status === "running") {
            updateProgress(box, {
              pct: job.pct || 5,
              title: job.title || "Разбираю",
              detail: job.detail || "",
              elapsed_sec: (Date.now() - t0) / 1000,
              eta_sec: job.eta_sec,
            });
            await new Promise((r) => setTimeout(r, 900));
            try {
              job = await pollClassifyStatus(jobId);
              streak502 = 0;
            } catch (e) {
              streak502 += 1;
              updateProgress(box, {
                pct: job.pct || 5,
                title: "Связь оборвалась",
                detail: `Повторяю опрос… (${e.message || "502"}) · прогресс на сервере сохранён`,
                elapsed_sec: (Date.now() - t0) / 1000,
              });
              if (streak502 >= 8) {
                // Mark as paused locally; server checkpoint remains
                showResumeUi({
                  ...job,
                  status: "paused",
                  detail: `Оборвалась связь после ${job.done || "?"} роликов — нажми «Продолжить»`,
                });
                return;
              }
            }
          }
          if (job.status === "paused" || (job.status === "error" && job.resumable)) {
            showResumeUi(job);
            return;
          }
          if (job.status === "error") {
            finishProgress(box, { ok: false, title: "Ошибка", detail: job.detail || job.error || "" });
            classifyBtn.disabled = false;
            return;
          }
          finishProgress(box, {
            ok: true,
            title: "Готово",
            detail: job.detail || `В папки: ${job.classified || 0}`,
            elapsed_sec: (Date.now() - t0) / 1000,
          });
          toast(`Разобрано: ${job.classified || 0}`);
          setTimeout(() => renderHome(), 600);
        } catch (e) {
          finishProgress(box, { ok: false, title: "Ошибка", detail: e.message || String(e) });
          // Offer resume if we likely have server checkpoint
          const actions = document.createElement("div");
          actions.className = "btn-row";
          actions.style.marginTop = "10px";
          actions.innerHTML = `<button type="button" class="btn" id="classify-resume-btn">Продолжить / повторить</button>`;
          boxHost.appendChild(actions);
          const resumeBtn = $("#classify-resume-btn");
          if (resumeBtn) resumeBtn.onclick = () => runClassify({ resume: true });
          classifyBtn.disabled = false;
          toast(e.message || "Не удалось разобрать");
        }
      };

      classifyBtn.onclick = () => runClassify({ resume: canResumeClassify });

      // If job is already running (another tab / reload) — attach progress
      if (classifyJob && classifyJob.status === "running") {
        runClassify({ resume: true });
      } else if (canResumeClassify) {
        const boxHost = $("#home-classify-progress");
        if (boxHost) {
          boxHost.innerHTML = `<div class="progress-box error" data-progress>
            <div class="progress-head">
              <div class="progress-copy">
                <div class="progress-title">Разбор прерван</div>
                <div class="progress-detail">${escapeHtml(classifyJob.detail || "Можно продолжить с чекпоинта")}</div>
              </div>
            </div>
            <div class="btn-row" style="margin-top:10px">
              <button type="button" class="btn" id="classify-resume-btn">Продолжить</button>
            </div>
          </div>`;
          const resumeBtn = $("#classify-resume-btn");
          if (resumeBtn) resumeBtn.onclick = () => runClassify({ resume: true });
        }
      }
    }

    const host = $("#rails");
    if (!has && !recent.length) {
      host.innerHTML = `
        <div class="panel">
          <div class="empty">Пока пусто</div>
          <div class="btn-row" style="margin-top:12px">
            <a class="btn" href="/organize" data-nav>Разложить по темам</a>
          </div>
        </div>`;
      return;
    }
    if (recent.length) {
      const block = document.createElement("section");
      block.className = "rail";
      block.innerHTML = `
        <div class="rail-head">
          <h2>Недавно сохранили</h2>
          <span class="muted" style="font-size:13px">${recentSource ? escapeHtml(recentSource) + " · " : ""}${recent.length}</span>
        </div>
        ${recentListHtml(recent.slice(0, 12))}`;
      host.appendChild(block);
      wireCardMenus(block);
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
      queue: "Сохранённые",
      in_progress: "Начатые",
      watched: "Просмотренные",
      archived: "Архив",
    }[status] || "Библиотека";
    const statusHint = {
      queue: "Только длинные (6 мин – 10 ч). Короткие, клипы и 10+ часов — вкладками ниже.",
      in_progress: "Открыл на YouTube или отметил «Начал». Из сохранённых уже убрано.",
      watched: "Уже посмотрел — в сохранённых этих роликов больше нет.",
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
        <button type="button" class="chip ${status === "queue" ? "active" : ""}" data-status="queue">Сохранённые</button>
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
      <div id="queue-grid">
        ${items.length ? recentListHtml(items) : `<div class="empty">Пока пусто. ${status === "queue" ? `<a href="/queue?status=in_progress" data-nav>Начатые</a> · <a href="/channels" data-nav>каналы</a>` : `<a href="/queue?status=queue" data-nav>К сохранённым</a>`}</div>`}
      </div>`;
    wireNav();
    wireCardMenus(app);
    const paint = (list) => {
      $("#queue-grid").innerHTML = list.length
        ? recentListHtml(list)
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
          <button class="btn" id="save-urls">Сохранить</button>
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
          <input type="search" id="search-q" value="${escapeHtml(q0)}" placeholder="Что хотите посмотреть?" />
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

  async function offerSimilarTag(videoId, tagId, tagName) {
    let overlay = $("#tag-similar-sheet");
    if (overlay) overlay.remove();
    let items = [];
    try {
      const sim = await api(`/api/videos/${encodeURIComponent(videoId)}/similar?limit=12`);
      items = (sim.items || []).filter((it) => it.video_id !== videoId).slice(0, 8);
    } catch (_) {}
    if (!items.length) return;
    overlay = document.createElement("div");
    overlay.id = "tag-similar-sheet";
    overlay.className = "sheet-overlay";
    overlay.innerHTML = `
      <div class="sheet-card" role="dialog" aria-label="Похожие для тега">
        <div class="sheet-head">
          <h2>Ещё с тегом «${escapeHtml(tagName)}»?</h2>
          <button type="button" class="btn ghost" id="tag-sim-close">Закрыть</button>
        </div>
        <p class="hint">Вы отметили одно видео. Отметьте похожие — после нескольких примеров Kyro научится предлагать этот тег точнее.</p>
        <div class="tag-sim-rail rail-track drag-scroll">
          ${items.map((it) => `
            <label class="tag-sim-card">
              <input type="checkbox" data-sim-vid="${escapeHtml(it.video_id)}" />
              <img src="${escapeHtml(it.thumb_url || "")}" alt="" loading="lazy" />
              <span class="tag-sim-title">${escapeHtml(it.title || "")}</span>
            </label>`).join("")}
        </div>
        <div class="btn-row" style="margin-top:14px">
          <button type="button" class="btn" id="tag-sim-apply">Повесить тег</button>
          <button type="button" class="btn ghost" id="tag-sim-skip">Позже</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    $("#tag-sim-close").onclick = close;
    $("#tag-sim-skip").onclick = close;
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    enableDragScroll(overlay);
    $("#tag-sim-apply").onclick = async () => {
      const picked = [...overlay.querySelectorAll("[data-sim-vid]:checked")].map((el) => el.getAttribute("data-sim-vid"));
      if (!picked.length) return toast("Выберите хотя бы одно видео");
      let ok = 0;
      for (const vid of picked) {
        try {
          await api(`/api/videos/${encodeURIComponent(vid)}/tags`, {
            method: "POST",
            body: JSON.stringify({ tag_id: tagId, name: tagName }),
          });
          ok += 1;
        } catch (_) {}
      }
      toast(ok ? `Тег на ${ok} видео` : "Не удалось повесить");
      close();
    };
  }

  async function renderVideo(videoId) {
    const data = await api(`/api/videos/${encodeURIComponent(videoId)}`);
    const item = data.item;
    const tagsPromise = api("/api/tags").catch(() => ({ tags: [] }));
    const listsPromise = api("/api/lists").catch(() => ({ lists: [] }));

    const unavailable = item.is_unavailable || /^(private|deleted) video$/i.test(item.title || "");
    const noteVal = item.note || "";
    app.innerHTML = `
      ${topbar("queue")}
      <div class="video-page">
        <div>
          <div class="video-hero">
            <img src="${escapeHtml(item.thumb_url)}" alt="" />
            <span class="hero-play" aria-hidden="true"></span>
          </div>
          ${unavailable ? `<div class="warn-box">YouTube скрыл этот ролик (private/deleted). В лайках осталась заглушка — открыть на YouTube, скорее всего, не получится. Можно убрать из библиотеки.</div>` : ""}
          <h1 style="font-family:var(--display);letter-spacing:-0.03em;margin:16px 0 8px;font-size:1.6rem">${escapeHtml(item.title)}</h1>
          <div class="muted">${escapeHtml(item.channel_title || "")}${item.duration_label ? " · " + escapeHtml(item.duration_label) : ""}
            ${item.channel_title && !unavailable ? ` · <a href="/queue?kind=video&channel=${encodeURIComponent(item.channel_title)}" data-nav>все с канала</a>` : ""}
          </div>
          <div class="tags-block" style="margin-top:12px">
            <div class="tags-block-head">
              <span class="muted" style="font-size:13px">Теги</span>
              <button type="button" class="btn ghost tags-edit-btn" id="tags-edit-toggle" title="Редактировать теги" aria-label="Редактировать теги">✎</button>
            </div>
            <div id="assigned-tags" class="tags-row" data-editing="0">
              ${tagPillsHtml(item.user_tags || [], { removable: false, videoId })}
            </div>
            <div id="tags-edit-panel" class="tags-edit-panel hidden">
              <div id="tag-picker" class="tags-cloud"></div>
              <div class="field" style="margin-top:12px">
                <label>Новый тег</label>
                <div class="btn-row">
                  <input id="new-tag" placeholder="название" style="flex:1" />
                  <button class="btn secondary" id="add-tag">Создать и повесить</button>
                </div>
              </div>
              <button class="btn ghost" id="ai-tag" style="margin-top:8px;width:100%">Подсказать тему (AI)</button>
              <pre id="ai-out" class="muted" style="white-space:pre-wrap;font-size:12px;margin-top:8px"></pre>
            </div>
          </div>
          <p class="muted" style="margin-top:14px;line-height:1.5;white-space:pre-wrap">${escapeHtml((item.description || "").slice(0, 600))}</p>
          <div class="field lexicon-field" style="margin-top:16px">
            <label>Как Вы это назовёте (своя лексика)</label>
            <textarea id="user-note" rows="2" placeholder="Например: стрёмная хрень / уют на вечер">${escapeHtml(noteVal)}</textarea>
            <button type="button" class="btn secondary" id="save-note" style="margin-top:8px">Сохранить описание</button>
          </div>
        </div>
        <div class="panel">
          <div class="muted" style="margin:0 0 10px;font-size:13px">Статус: <b>${
            item.status === "watched" ? "просмотрено" :
            item.status === "in_progress" ? "начато" :
            item.status === "archived" ? "архив" : "сохранено"
          }</b></div>
          <div class="btn-row" style="flex-direction:column;align-items:stretch">
            <button class="btn" id="open-yt">Смотреть на YouTube</button>
            <button class="btn secondary" id="mark-started"${item.status === "in_progress" ? " disabled" : ""}>${item.status === "in_progress" ? "Уже в начатых" : "Отметить начатым"}</button>
            <button class="btn secondary" id="mark-watched"${item.status === "watched" ? " disabled" : ""}>${item.status === "watched" ? "Уже в просмотренных" : "Отметить просмотренным"}</button>
            <button class="btn ghost" id="back-queue">Вернуть в сохранённые</button>
            <button class="btn ghost" id="delete-item">Убрать из библиотеки</button>
          </div>
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
        <div class="rail-head"><h2>Похожие из ваших</h2>
          <span class="muted" style="font-size:13px">по описанию и вайбу</span>
        </div>
        <div class="rail-track drag-scroll" id="similar-rail">
          <div class="empty">Загружаю похожие…</div>
        </div>
      </section>
      <section class="rail" style="margin-top:18px">
        <div class="rail-head"><h2>Похожие на YouTube</h2>
          <span class="muted" style="font-size:13px" id="yt-related-hint">подгружаю…</span>
        </div>
        <div class="rail-track drag-scroll" id="yt-related-rail">
          <div class="empty">Загружаю…</div>
        </div>
      </section>
      <div id="note-sheet" class="note-sheet hidden"></div>`;
    wireNav();
    enableDragScroll(app);
    wireCardMenus(app);

    let allTags = await tagsPromise;
    if (!(allTags.tags || []).length) {
      try { allTags = await api("/api/tags/seed-defaults", { method: "POST", body: "{}" }); } catch (_) {}
    }
    const assignedIds = new Set((item.user_tags || []).map((t) => t.id));
    const pickHtml = (allTags.tags || []).map((t) => {
      const on = assignedIds.has(t.id);
      const label = `${t.emoji ? t.emoji + " " : ""}${t.name}`;
      return `<button type="button" class="tag-pill tag-pill-btn ${on ? "tag-pill-on" : ""}" data-toggle-tag="${t.id}" data-tag-name="${escapeHtml(t.name)}">${escapeHtml(label)}${on ? " ✓" : ""}</button>`;
    }).join("");
    const picker = $("#tag-picker");
    if (picker) picker.innerHTML = pickHtml || `<span class="muted">Сначала создайте теги</span>`;

    const lists = await listsPromise;
    const sel = $("#list-select");
    if (sel) {
      sel.innerHTML = (lists.lists || []).map((l) =>
        `<option value="${l.id}">${escapeHtml(l.title)}</option>`
      ).join("") || `<option value="">Нет списков</option>`;
    }

    // Lazy rails — don't block first paint
    (async () => {
      const host = $("#similar-rail");
      try {
        const similar = await api(`/api/videos/${encodeURIComponent(videoId)}/similar`);
        if (!host) return;
        host.innerHTML = similar.items?.length
          ? similar.items.map(cardHtml).join("")
          : `<div class="empty">Добавьте ещё видео — появятся похожие по смыслу</div>`;
        wireCardMenus(host);
        wireNav();
      } catch (_) {
        if (host) host.innerHTML = `<div class="empty">Не удалось загрузить</div>`;
      }
    })();
    (async () => {
      const host = $("#yt-related-rail");
      const hint = $("#yt-related-hint");
      try {
        const ytRelated = await api(`/api/videos/${encodeURIComponent(videoId)}/yt-related`);
        if (hint) {
          hint.textContent = ytRelated.query
            ? String(ytRelated.query).replace(/^"|"$/g, "")
            : "по теме · без шорцов";
        }
        if (!host) return;
        host.innerHTML = (ytRelated.items || []).length
          ? ytRelated.items.map((it) => `
              <div class="card yt-discover-card" data-video-id="${escapeHtml(it.video_id)}">
                <a class="card-main" href="${escapeHtml(it.watch_url)}" target="_blank" rel="noopener">
                  <div class="card-thumb">
                    <img src="${escapeHtml(it.thumb_url)}" alt="" loading="lazy" />
                    ${it.duration_label ? `<span class="badge">${escapeHtml(it.duration_label)}</span>` : ""}
                  </div>
                  <div class="card-body">
                    <h3 class="card-title">${escapeHtml(it.title)}</h3>
                    <div class="card-meta">${escapeHtml(it.channel_title || "")}</div>
                  </div>
                </a>
                <div class="card-actions">
                  <a class="btn play-btn" href="${escapeHtml(it.watch_url)}" target="_blank" rel="noopener">▶</a>
                  <button type="button" class="btn secondary" data-save-yt="${escapeHtml(it.video_id)}">Сохранить</button>
                </div>
              </div>`).join("")
          : `<div class="empty">${
              ytRelated.error === "no_youtube_search_auth"
                ? "Нет доступа к YouTube Search — нужен YOUTUBE_API_KEY на сервере"
                : (ytRelated.note || "По теме ничего не нашлось")
            }</div>`;
        host.querySelectorAll("[data-save-yt]").forEach((btn) => {
          btn.onclick = async () => {
            const vid = btn.getAttribute("data-save-yt");
            try {
              await api("/api/videos/save", {
                method: "POST",
                body: JSON.stringify({ url: `https://www.youtube.com/watch?v=${vid}` }),
              });
              toast("Сохранено");
              btn.textContent = "Уже есть";
              btn.disabled = true;
            } catch (e) {
              toast(e.message);
            }
          };
        });
      } catch (_) {
        if (host) host.innerHTML = `<div class="empty">Не удалось загрузить</div>`;
        if (hint) hint.textContent = "";
      }
    })();

    const setEditing = (on) => {
      const row = $("#assigned-tags");
      const panel = $("#tags-edit-panel");
      const toggle = $("#tags-edit-toggle");
      if (row) row.setAttribute("data-editing", on ? "1" : "0");
      if (panel) panel.classList.toggle("hidden", !on);
      if (toggle) toggle.classList.toggle("active", !!on);
      if (row) {
        row.innerHTML = tagPillsHtml(item.user_tags || [], { removable: !!on, videoId });
        wireUntag();
      }
    };

    const refreshTags = (nextItem) => {
      Object.assign(item, { user_tags: nextItem.user_tags || [] });
      const editing = $("#assigned-tags")?.getAttribute("data-editing") === "1";
      const box = $("#assigned-tags");
      if (box) box.innerHTML = tagPillsHtml(item.user_tags || [], { removable: editing, videoId });
      wireUntag();
      const ids = new Set((item.user_tags || []).map((t) => t.id));
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
          e.stopPropagation();
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

    const editToggle = $("#tags-edit-toggle");
    if (editToggle) {
      editToggle.onclick = () => {
        const on = $("#assigned-tags")?.getAttribute("data-editing") !== "1";
        setEditing(on);
      };
    }

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
            offerSimilarTag(videoId, tagId || r.tag?.id, name);
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
        if (r.moved_to_started) toast("Ушло в «Начатые»");
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
      toast("В «Начатые»");
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
    $("#back-queue").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "queue" }),
      });
      toast("Снова в сохранённых");
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
      if (!name) return toast("Напишите тег");
      try {
        await api("/api/tags", { method: "POST", body: JSON.stringify({ name }) });
        const r = await api(`/api/videos/${encodeURIComponent(videoId)}/tags`, {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        toast(`Тег «${name}»`);
        refreshTags(r.item || { user_tags: r.user_tags || [] });
        const tag = (r.item?.user_tags || r.user_tags || []).find((t) => (t.name || "").toLowerCase() === name.toLowerCase());
        if (tag) offerSimilarTag(videoId, tag.id, tag.name);
        setEditing(true);
      } catch (e) {
        toast(e.message);
      }
    };
    $("#ai-tag").onclick = async () => {
      const btn = $("#ai-tag");
      btn.classList.add("busy");
      const box = mountProgress($("#ai-out"), {
        title: "Смотрю ролик",
        detail: "Подбираю тему",
      });
      try {
        const r = await runBusySteps(box, [
          { title: "Читаю название и описание", detail: "контекст ролика" },
          { title: "Спрашиваю модель", detail: "только по смыслу" },
          { title: "Готовлю предложения", detail: "без автоприменения" },
        ], api(`/api/videos/${encodeURIComponent(videoId)}/suggest-themes`, {
          method: "POST",
          body: JSON.stringify({ apply: false }),
        }));
        const suggested = r.suggestion?.tags || [];
        finishProgress(box, {
          ok: true,
          title: suggested.length ? "Предложения" : "Без уверенных тегов",
          detail: suggested.join(", ") || (r.suggestion?.reason || "ничего не подходит"),
        });
        if (suggested.length) {
          const pickerEl = $("#tag-picker");
          if (pickerEl) {
            const wrap = document.createElement("div");
            wrap.className = "ai-suggest-row";
            wrap.innerHTML = `<div class="muted" style="font-size:12px;margin:8px 0 4px">Предложено — нажмите, чтобы повесить:</div>` +
              suggested.map((name) =>
                `<button type="button" class="tag-pill tag-pill-btn" data-apply-suggest="${escapeHtml(name)}">${escapeHtml(name)}</button>`
              ).join("");
            pickerEl.prepend(wrap);
            wrap.querySelectorAll("[data-apply-suggest]").forEach((b) => {
              b.onclick = async () => {
                const name = b.getAttribute("data-apply-suggest");
                try {
                  const rr = await api(`/api/videos/${encodeURIComponent(videoId)}/tags`, {
                    method: "POST",
                    body: JSON.stringify({ name }),
                  });
                  refreshTags(rr.item || { user_tags: rr.user_tags || [] });
                  toast(`Тег: ${name}`);
                  const tag = (rr.item?.user_tags || []).find((t) => (t.name || "").toLowerCase() === name.toLowerCase());
                  if (tag) offerSimilarTag(videoId, tag.id, tag.name);
                } catch (e) {
                  toast(e.message);
                }
              };
            });
          }
        } else {
          toast("Не нашлось обоснованных тегов");
        }
      } catch (e) {
        finishProgress(box, { ok: false, title: "Не вышло", detail: e.message });
        toast(e.message);
      } finally {
        btn.classList.remove("busy");
      }
    };
    $("#add-to-list").onclick = async () => {
      const listId = sel.value;
      if (!listId) return toast("Сначала создайте список");
      await api(`/api/lists/${listId}/items`, {
        method: "POST",
        body: JSON.stringify({ video_id: videoId }),
      });
      toast("В списке");
    };
  }

  function isVideoPath(path) {
    return /^\/v\//.test((path || "").split("?")[0]);
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  async function transitionOut({ toVideo = false, fromVideo = false } = {}) {
    if (prefersReducedMotion() || !app || !app.children.length) return;
    app.classList.remove("page-enter", "page-enter-video", "page-exit", "page-exit-video");
    const heavy = toVideo || fromVideo;
    app.classList.add(heavy ? "page-exit-video" : "page-exit");
    await new Promise((r) => setTimeout(r, heavy ? 380 : 240));
  }

  function transitionIn({ video = false } = {}) {
    if (!app) return;
    app.classList.remove("page-exit", "page-exit-video", "page-enter", "page-enter-video");
    if (prefersReducedMotion()) return;
    // reflow so enter animation restarts after innerHTML swap
    void app.offsetWidth;
    app.classList.add(video ? "page-enter-video" : "page-enter");
    const done = () => {
      app.classList.remove("page-enter", "page-enter-video");
      app.removeEventListener("animationend", done);
    };
    app.addEventListener("animationend", done);
  }

  async function navigate(path, replace = false) {
    const nextPath = path.split("?")[0];
    const toVideo = isVideoPath(nextPath);
    const fromVideo = isVideoPath(location.pathname);
    await transitionOut({ toVideo, fromVideo });
    if (replace) history.replaceState({}, "", path);
    else if (location.pathname + location.search !== path) history.pushState({}, "", path);
    await route();
    transitionIn({ video: isVideoPath(location.pathname) });
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
    if (path === "/faq") return renderFaq();
    if (path === "/login") return renderLogin();
    const m = path.match(/^\/v\/([^/]+)/);
    if (m) return renderVideo(decodeURIComponent(m[1]));
    return renderHome();
  }

  window.addEventListener("popstate", async () => {
    const video = isVideoPath(location.pathname);
    await transitionOut({ fromVideo: true, toVideo: video });
    await route();
    transitionIn({ video });
  });
  document.querySelectorAll("#bottom-nav button").forEach((b) => {
    b.onclick = () => navigate(b.getAttribute("data-route"));
  });

  route();
})();
