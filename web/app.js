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
    const res = await fetch(path, { ...opts, headers });
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

  function cardHtml(item) {
    const dur = item.duration_label ? `<span class="badge">${escapeHtml(item.duration_label)}</span>` : "";
    const pills = (item.user_tags || []).slice(0, 3).map((t) =>
      `<span class="tag-pill tag-pill-sm">${escapeHtml((t.emoji || "") + " " + t.name)}</span>`
    ).join("");
    return `
      <a class="card" href="/v/${encodeURIComponent(item.video_id)}" data-nav>
        <div class="card-thumb">
          <img src="${escapeHtml(item.thumb_url)}" alt="" loading="lazy" />
          ${dur}
        </div>
        <div class="card-body">
          <h3 class="card-title">${escapeHtml(item.title)}</h3>
          <div class="card-meta">${escapeHtml(item.channel_title || "YouTube")}</div>
          ${pills ? `<div class="card-tags">${pills}</div>` : ""}
        </div>
      </a>`;
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
        <nav class="nav">
          <button class="nav-btn ${active === "home" ? "active" : ""}" data-route="/home">Главная</button>
          <button class="nav-btn ${active === "queue" ? "active" : ""}" data-route="/queue">Очередь</button>
          <button class="nav-btn ${active === "channels" ? "active" : ""}" data-route="/channels">Каналы</button>
          <button class="nav-btn ${active === "organize" ? "active" : ""}" data-route="/organize">Разложить</button>
          <button class="nav-btn ${active === "settings" ? "active" : ""}" data-route="/settings">Настройки</button>
          <button class="nav-btn" id="logout-btn" title="${escapeHtml(name)}">Выйти</button>
        </nav>
      </header>
      <button type="button" class="fab-add" id="fab-add" title="Добавить видео">+</button>`;
  }

  function enableDragScroll(root = document) {
    root.querySelectorAll(".rail-track, .folder-rail, .drag-scroll").forEach((el) => {
      if (el.dataset.dragScroll === "1") return;
      el.dataset.dragScroll = "1";
      let down = false;
      let startX = 0;
      let startScroll = 0;
      let moved = false;
      el.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        if (e.target.closest("a, button, select, input, .folder-tile")) return;
        down = true;
        moved = false;
        startX = e.pageX;
        startScroll = el.scrollLeft;
        el.classList.add("is-dragging");
      });
      window.addEventListener("mouseup", () => {
        down = false;
        el.classList.remove("is-dragging");
      });
      window.addEventListener("mousemove", (e) => {
        if (!down) return;
        const dx = e.pageX - startX;
        if (Math.abs(dx) > 4) moved = true;
        el.scrollLeft = startScroll - dx;
      });
      el.addEventListener("click", (e) => {
        if (moved) {
          e.preventDefault();
          e.stopPropagation();
          moved = false;
        }
      }, true);
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
  }

  async function ensureAuth() {
    if (!token()) return false;
    try {
      const data = await api("/api/me");
      me = data.user;
      return true;
    } catch (_) {
      setToken("");
      me = null;
      return false;
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

  async function runYoutubeSync({ autoGoHome = false } = {}) {
    const btn = $("#sync-yt");
    const out = $("#sync-out");
    if (!out) return null;
    if (btn) {
      btn.classList.add("busy");
      btn.disabled = true;
    }
    const box = mountProgress(out, {
      title: "Забираю твой YouTube",
      detail: "Лайки → плейлисты → подписки",
    });
    try {
      const started = await api("/api/youtube/sync", { method: "POST", body: "{}" });
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
      toast(`В библиотеке: +${s.liked_new || 0} лайков, ${s.playlists || 0} плейлистов, ${s.subscriptions || 0} подписок`);
      if (autoGoHome) {
        setTimeout(() => navigate("/home"), 700);
      }
      return s;
    } catch (e) {
      finishProgress(box, { ok: false, title: "Синк не вышел", detail: e.message });
      toast(e.message);
      return null;
    } finally {
      if (btn) {
        btn.classList.remove("busy");
        btn.disabled = false;
      }
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
    await ensureAuth();
    toast("Google подключён — тяну YouTube");
    navigate("/onboard?autosync=1", true);
  }

  async function renderOnboard() {
    const meData = await api("/api/me");
    const wantAutosync =
      new URL(location.href).searchParams.get("autosync") === "1" ||
      (meData.youtube_connected && !(meData.library_count > 0));
    app.innerHTML = `
      ${topbar("settings")}
      <section class="hero">
        <h1>Настройки</h1>
        <p>Синк с YouTube, Takeout и аккаунт. Системный «Смотреть позже» Google API не отдаёт — копируй в обычный плейлист.</p>
      </section>
      <div class="panel" style="margin-bottom:16px">
        <h2>YouTube</h2>
        <p class="hint">
          <b>Качаем:</b> лайки + обычные плейлисты + подписки.<br>
          <b>Не качается:</b> официальный Watch Later (<code>list=WL</code>).<br>
          Копия WL в свой плейлист → «Обновить из YouTube».
        </p>
        <p class="muted">Статус: ${meData.youtube_connected ? "Google подключён" : "нужен вход через Google"} · в библиотеке сейчас: ${meData.library_count || 0}</p>
        <div class="btn-row">
          <button class="btn" id="sync-yt" ${meData.youtube_connected ? "" : "disabled"}>Обновить из YouTube</button>
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
        <h2>3. Разложить по папкам</h2>
        <p class="hint">Категоризация библиотеки — на отдельном экране.</p>
        <div class="btn-row">
          <a class="btn" href="/organize" data-nav>Открыть «Разложить»</a>
        </div>
      </div>`;
    wireNav();
    $("#sync-yt").onclick = () => runYoutubeSync({ autoGoHome: false });
    if (wantAutosync && meData.youtube_connected) {
      runYoutubeSync({ autoGoHome: true });
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
      <div class="folder-tile" draggable="true" data-video-id="${escapeHtml(it.video_id)}" data-from-folder="${folderIdx}">
        <div class="folder-tile-media">
          <img src="${escapeHtml(it.thumb_url || "")}" alt="" loading="lazy" draggable="false" />
          ${it.duration_label ? `<span class="badge">${escapeHtml(it.duration_label)}</span>` : ""}
        </div>
        <div class="folder-tile-title">${escapeHtml(it.title || "Без названия")}</div>
        <div class="folder-tile-meta">${escapeHtml(it.channel_title || "")}</div>
        <div class="folder-tile-actions">
          <a class="btn ghost" href="/v/${encodeURIComponent(it.video_id)}" data-nav style="min-height:32px;padding:6px 10px;font-size:12px">Открыть</a>
          <select class="folder-assign" data-assign-video="${escapeHtml(it.video_id)}" data-from-folder="${folderIdx}" title="Ещё в категорию">
            <option value="">+ ещё в…</option>
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
    const ruleHint = folder.persist && folder.rule
      ? `<span class="folder-rule">правило сохранится</span>`
      : `<span class="folder-rule muted">черновик</span>`;
    return `
      <div class="folder-card" data-folder-idx="${idx}" data-drop-folder="${idx}">
        <div class="folder-head">
          <div class="folder-head-text">
            <b>${escapeHtml(folder.title || "Папка")}</b>
            <div class="muted">${escapeHtml(folder.reason || "")}</div>
          </div>
          <div class="folder-head-meta">
            ${ruleHint}
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
        <h1>Твои папки</h1>
        <p>Один раз разложил — сохранил. Дальше живёшь с этими категориями: перетащи ролик или нажми «Сохранить». С нуля — только кнопкой ниже.</p>
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
    $("#apply-proposal").onclick = async () => {
      if (!lastProposal) return;
      const btn = $("#apply-proposal");
      btn.classList.add("busy");
      const box = mountProgress($("#proposal-box"), {
        title: "Сохраняю",
        detail: "Папки + правила для новых видео",
      });
      try {
        const data = await runBusySteps(box, [
          { title: "Обновляю папки", detail: "списки" },
          { title: "Раскладываю видео", detail: "по папкам" },
          { title: "Пишу правила", detail: "для будущих шаров" },
        ], api("/api/organize/apply", {
          method: "POST",
          body: JSON.stringify({
            proposal: lastProposal,
            proposal_id: lastProposal.proposal_id,
          }),
        }));
        finishProgress(box, {
          ok: true,
          title: "Сохранено",
          detail: `Папок: ${(data.lists || []).length} · правил: ${data.rules_saved || 0}`,
        });
        toast(`Сохранено: ${(data.lists || []).length} папок`);
        await paintRules();
        setTimeout(() => navigate("/home"), 500);
      } catch (e) {
        finishProgress(box, { ok: false, title: "Не сохранилось", detail: e.message });
        toast(e.message);
      } finally {
        btn.classList.remove("busy");
      }
    };

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
      api("/api/organize/structure").catch(() => ({ has_structure: false, folders: [] })),
    ]);
    const folders = structure.folders || [];
    const has = !!structure.has_structure && folders.length;

    app.innerHTML = `
      ${topbar("home")}
      <section class="hero">
        <h1>${has ? "Твои категории" : "Сначала разложи видео"}</h1>
        <p>${has
          ? "То, что сохранил в «Разложить». Листай карусели мышкой, открывай ролик."
          : "Главная — это результат группировки. Зайди в «Разложить», собери папки и нажми «Сохранить»."}</p>
        <div class="stats">
          <div class="stat">Папок: <b>${folders.length}</b></div>
          <div class="stat">Очередь: <b>${shell.counts?.queue ?? "—"}</b></div>
          <div class="stat">Начатые: <b>${shell.counts?.started || 0}</b></div>
        </div>
        <div class="btn-row" style="margin-top:14px">
          <a class="btn" href="/organize" data-nav>${has ? "Править раскладку" : "Разложить"}</a>
          <a class="btn secondary" href="/queue?status=queue&kind=video" data-nav>Очередь</a>
          <a class="btn ghost" href="/channels" data-nav>Каналы</a>
        </div>
      </section>
      <div id="rails"></div>`;
    wireNav();
    const host = $("#rails");
    if (!has) {
      host.innerHTML = `
        <div class="panel">
          <div class="empty">Пока пусто на главной — сохрани раскладку один раз, и категории появятся здесь.</div>
        </div>`;
      return;
    }
    for (const folder of folders) {
      const block = document.createElement("section");
      block.className = "rail";
      const items = folder.items || [];
      block.innerHTML = `
        <div class="rail-head">
          <h2>${escapeHtml(folder.title)}</h2>
          <span class="muted" style="font-size:13px">${folder.count || items.length} видео</span>
        </div>
        <div class="rail-track drag-scroll">
          ${items.length
            ? items.map((it) => cardHtml({
                ...it,
                watch_url: it.watch_url || `https://www.youtube.com/watch?v=${it.video_id}`,
              })).join("")
            : `<div class="empty" style="min-width:260px">Пусто</div>`}
        </div>`;
      host.appendChild(block);
    }
    enableDragScroll(host);
    wireNav();
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
      queue: "Только длинные (6 мин – 10 ч). Короткие, клипы и 10+ часов — вкладками ниже. Папки — «Разложить».",
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
        ${!channel && status === "queue" ? `<div class="btn-row" style="margin-top:12px"><a class="btn" href="/organize" data-nav>Разложить по папкам</a></div>` : ""}
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
        <a class="chip" href="/organize" data-nav>Разложить →</a>
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
    const paint = (list) => {
      $("#queue-grid").innerHTML = list.length
        ? list.map(cardHtml).join("")
        : `<div class="empty">Ничего не нашлось</div>`;
      wireNav();
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
        <p class="hint">Ссылка или пачка ссылок — через пробел, запятую или с новой строки.</p>
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
    $("#add-close").onclick = close;
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    $("#urls-file").onchange = async (ev) => {
      const f = ev.target.files?.[0];
      if (!f) return;
      const text = await f.text();
      $("#yt-urls").value = (($("#yt-urls").value || "") + "\n" + text).trim();
    };
    $("#save-urls").onclick = async () => {
      const urls = parseUrlBlob($("#yt-urls").value);
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

  async function renderVideo(videoId) {
    const data = await api(`/api/videos/${encodeURIComponent(videoId)}`);
    const item = data.item;
    let allTags = { tags: [] };
    try { allTags = await api("/api/tags"); } catch (_) {}
    if (!(allTags.tags || []).length) {
      try { allTags = await api("/api/tags/seed-defaults", { method: "POST", body: "{}" }); } catch (_) {}
    }
    let similar = { items: [] };
    try {
      similar = await api(`/api/videos/${encodeURIComponent(videoId)}/similar`);
    } catch (_) {}
    const assignedIds = new Set((item.user_tags || []).map((t) => t.id));
    const pickHtml = (allTags.tags || []).map((t) => {
      const on = assignedIds.has(t.id);
      const label = `${t.emoji ? t.emoji + " " : ""}${t.name}`;
      return `<button type="button" class="tag-pill tag-pill-btn ${on ? "tag-pill-on" : ""}" data-toggle-tag="${t.id}" data-tag-name="${escapeHtml(t.name)}">${escapeHtml(label)}${on ? " ✓" : ""}</button>`;
    }).join("");

    const unavailable = item.is_unavailable || /^(private|deleted) video$/i.test(item.title || "");
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
        <div class="rail-head"><h2>Похожие из твоих</h2></div>
        <div class="rail-track">
          ${similar.items?.length ? similar.items.map(cardHtml).join("") : `<div class="empty">Добавь ещё видео — появятся похожие по каналу и вайбу</div>`}
        </div>
      </section>`;
    wireNav();
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
    $("#mark-watched").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "watched" }),
      });
      toast("Просмотрено — в общем плане больше нет");
      renderVideo(videoId);
    };
    $("#back-queue").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "queue" }),
      });
      toast("Снова в очереди");
      renderVideo(videoId);
    };
    $("#delete-item").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, { method: "DELETE" });
      toast("Убрано");
      navigate("/queue");
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
