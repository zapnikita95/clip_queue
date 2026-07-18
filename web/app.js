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

  function cardHtml(item) {
    const dur = item.duration_label ? `<span class="badge">${escapeHtml(item.duration_label)}</span>` : "";
    return `
      <a class="card" href="/v/${encodeURIComponent(item.video_id)}" data-nav>
        <div class="card-thumb">
          <img src="${escapeHtml(item.thumb_url)}" alt="" loading="lazy" />
          ${dur}
        </div>
        <div class="card-body">
          <h3 class="card-title">${escapeHtml(item.title)}</h3>
          <div class="card-meta">${escapeHtml(item.channel_title || "YouTube")}</div>
        </div>
      </a>`;
  }

  function topbar(active) {
    const name = me?.name || me?.email || "";
    return `
      <header class="topbar">
        <a class="brand" href="/home" data-nav>
          <div class="brand-mark" aria-hidden="true"></div>
          <div>
            <div class="brand-name">Clip Queue</div>
            <div class="brand-sub">очередь из твоих интересов</div>
          </div>
        </a>
        <nav class="nav">
          <button class="nav-btn ${active === "home" ? "active" : ""}" data-route="/home">Главная</button>
          <button class="nav-btn ${active === "queue" ? "active" : ""}" data-route="/queue">Очередь</button>
          <button class="nav-btn ${active === "add" ? "active" : ""}" data-route="/add">Добавить</button>
          <button class="nav-btn ${active === "lists" ? "active" : ""}" data-route="/lists">Списки</button>
          <button class="nav-btn ${active === "onboard" ? "active" : ""}" data-route="/onboard">YouTube</button>
          <button class="nav-btn" id="logout-btn" title="${escapeHtml(name)}">Выйти</button>
        </nav>
      </header>`;
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
    document.querySelectorAll("#bottom-nav button").forEach((b) => {
      const r = b.getAttribute("data-route");
      b.classList.toggle("active", location.pathname === r || (r === "/home" && location.pathname === "/"));
    });
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
          <p class="hint">Войди через Google — подтянем лайки, плейлисты и подписки с YouTube. Дальше разложим по папкам.</p>
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
          <p class="sister">Сестра <a href="https://movie-planner.ru" target="_blank" rel="noopener">Movie Planner</a>. Watch Later/историю Google API не отдаёт — для истории есть Takeout на экране онбординга.</p>
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

  async function renderAuthCallback() {
    const t = new URL(location.href).searchParams.get("token");
    if (!t) {
      toast("Нет токена");
      return navigate("/login", true);
    }
    setToken(t);
    await ensureAuth();
    toast("Google подключён");
    navigate("/onboard", true);
  }

  async function renderOnboard() {
    const meData = await api("/api/me");
    app.innerHTML = `
      ${topbar("onboard")}
      <section class="hero">
        <h1>Подтянуть YouTube</h1>
        <p>Сначала синк того, что Google отдаёт официально. Потом — опционально Takeout. В конце предложим структуру папок.</p>
      </section>
      <div class="panel" style="margin-bottom:16px">
        <h2>1. Синк через Google</h2>
        <p class="hint">Лайки, твои плейлисты, подписки. <b>Watch Later и история через API недоступны</b> — это ограничение Google, не бага.</p>
        <p class="muted">YouTube: ${meData.youtube_connected ? "подключён" : "не подключён — войди через Google"}</p>
        <div class="btn-row">
          <button class="btn" id="sync-yt" ${meData.youtube_connected ? "" : "disabled"}>Синхронизировать</button>
          ${!meData.youtube_connected && meData.google_oauth_configured
            ? `<a class="btn secondary" href="/api/auth/google/start">Подключить Google</a>` : ""}
        </div>
        <pre id="sync-out" class="muted" style="white-space:pre-wrap;margin-top:12px;font-size:13px"></pre>
      </div>
      <div class="panel" style="margin-bottom:16px">
        <h2>2. История из Google Takeout</h2>
        <p class="hint">takeout.google.com → YouTube → history → watch-history.json. Залей файл — получим то, что реально смотрел.</p>
        <input type="file" id="takeout-file" accept=".json,application/json" />
        <pre id="takeout-out" class="muted" style="white-space:pre-wrap;margin-top:12px;font-size:13px"></pre>
      </div>
      <div class="panel">
        <h2>3. Предложить структуру</h2>
        <p class="hint">Разложим видео по папкам: темы, каналы, короткие/длинные, очередь vs уже смотрел.</p>
        <div class="btn-row">
          <button class="btn" id="propose">Собрать предложение</button>
          <button class="btn secondary hidden" id="apply-proposal">Создать папки</button>
          <a class="btn ghost" href="/home" data-nav>На главную</a>
        </div>
        <div id="proposal-box" style="margin-top:16px"></div>
      </div>`;
    wireNav();
    let lastProposal = null;
    $("#sync-yt").onclick = async () => {
      $("#sync-out").textContent = "Синхронизация…";
      try {
        const data = await api("/api/youtube/sync", { method: "POST", body: "{}" });
        $("#sync-out").textContent = JSON.stringify(data.stats, null, 2);
        toast("Синк готов");
      } catch (e) {
        $("#sync-out").textContent = e.message;
        toast(e.message);
      }
    };
    $("#takeout-file").onchange = async (ev) => {
      const file = ev.target.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const json = JSON.parse(text);
        $("#takeout-out").textContent = "Импорт…";
        const data = await api("/api/youtube/takeout", {
          method: "POST",
          body: JSON.stringify(json),
        });
        $("#takeout-out").textContent = JSON.stringify(data.stats, null, 2);
        toast("Takeout загружен");
      } catch (e) {
        $("#takeout-out").textContent = e.message;
        toast(e.message);
      }
    };
    $("#propose").onclick = async () => {
      $("#proposal-box").innerHTML = `<p class="muted">Думаем…</p>`;
      try {
        const data = await api("/api/organize/propose", { method: "POST", body: "{}" });
        lastProposal = data.proposal;
        const folders = (lastProposal.folders || []).map((f) => `
          <div style="border:1px solid var(--border);border-radius:12px;padding:12px;margin-bottom:10px">
            <b>${escapeHtml(f.title)}</b>
            <div class="muted" style="font-size:13px;margin:4px 0">${escapeHtml(f.reason || "")}</div>
            <div class="muted" style="font-size:12px">${(f.video_ids || []).length} видео · engine: ${escapeHtml(lastProposal.engine)}</div>
          </div>`).join("");
        $("#proposal-box").innerHTML = `
          <p>${escapeHtml(lastProposal.summary || "")}</p>
          ${(lastProposal.limitations || []).map((x) => `<div class="muted" style="font-size:12px">• ${escapeHtml(x)}</div>`).join("")}
          <div style="margin-top:14px">${folders || "<div class='empty'>Мало данных — сначала синк/takeout</div>"}</div>`;
        $("#apply-proposal").classList.remove("hidden");
      } catch (e) {
        $("#proposal-box").innerHTML = `<p class="muted">${escapeHtml(e.message)}</p>`;
      }
    };
    $("#apply-proposal").onclick = async () => {
      if (!lastProposal) return;
      try {
        const data = await api("/api/organize/apply", {
          method: "POST",
          body: JSON.stringify({
            proposal: lastProposal,
            proposal_id: lastProposal.proposal_id,
          }),
        });
        toast(`Создано списков: ${(data.lists || []).length}`);
        navigate("/lists");
      } catch (e) {
        toast(e.message);
      }
    };
  }

  async function renderHome() {
    const shell = await api("/api/home/shell");
    const railDefs = shell.rails || [];
    app.innerHTML = `
      ${topbar("home")}
      <section class="hero">
        <h1>Что посмотреть из своего</h1>
        <p>Не поиск нового — панель твоих сохранений, каналов и вайба.</p>
        <div class="stats">
          <div class="stat">В очереди: <b>${shell.counts.queue}</b></div>
          <div class="stat">Посмотрено: <b>${shell.counts.watched}</b></div>
          <div class="stat">Списков: <b>${shell.counts.lists}</b></div>
        </div>
      </section>
      <div id="rails"></div>`;
    wireNav();
    const host = $("#rails");
    for (const rail of railDefs) {
      const block = document.createElement("section");
      block.className = "rail";
      block.innerHTML = `
        <div class="rail-head"><h2>${escapeHtml(rail.title)}</h2></div>
        <div class="rail-track"><div class="muted" style="padding:12px">Загрузка…</div></div>`;
      host.appendChild(block);
      try {
        const data = await api(`/api/home/rails/${rail.id}?limit=12`);
        const track = block.querySelector(".rail-track");
        const title = data.title || rail.title;
        block.querySelector("h2").textContent = title;
        if (!data.items?.length) {
          track.innerHTML = `<div class="empty" style="min-width:260px">Пока пусто</div>`;
        } else {
          track.innerHTML = data.items.map(cardHtml).join("");
        }
      } catch (e) {
        block.querySelector(".rail-track").innerHTML = `<div class="muted">${escapeHtml(e.message)}</div>`;
      }
    }
    wireNav();
  }

  async function renderQueue() {
    const data = await api("/api/library?status=queue&limit=100");
    app.innerHTML = `
      ${topbar("queue")}
      <section class="hero">
        <h1>Очередь</h1>
        <p>Всё, что хотел посмотреть и не потерять.</p>
      </section>
      <div class="field" style="max-width:420px">
        <input id="q-filter" placeholder="Фильтр по названию или каналу" />
      </div>
      <div class="grid" id="queue-grid">
        ${data.items?.length ? data.items.map(cardHtml).join("") : `<div class="empty">Очередь пуста — <a href="/add" data-nav>добавь видео</a></div>`}
      </div>`;
    wireNav();
    const items = data.items || [];
    $("#q-filter").oninput = (e) => {
      const q = e.target.value.trim().toLowerCase();
      const filtered = !q
        ? items
        : items.filter((i) => `${i.title} ${i.channel_title}`.toLowerCase().includes(q));
      $("#queue-grid").innerHTML = filtered.length
        ? filtered.map(cardHtml).join("")
        : `<div class="empty">Ничего не нашлось</div>`;
      wireNav();
    };
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

  async function renderAdd() {
    const shared = shareParams();
    const initial = pickUrlFromShare(shared);
    app.innerHTML = `
      ${topbar("add")}
      <section class="hero">
        <h1>Добавить видео</h1>
        <p>Вставь ссылку с YouTube. На телефоне можно «Поделиться» → Clip Queue (PWA).</p>
      </section>
      <div class="panel">
        <div class="field">
          <label>Ссылка YouTube</label>
          <input id="yt-url" placeholder="https://youtu.be/… или youtube.com/watch?v=…" value="${escapeHtml(initial)}" />
        </div>
        <div class="btn-row">
          <button class="btn secondary" id="resolve-btn">Превью</button>
          <button class="btn" id="save-btn">В очередь</button>
        </div>
        <div id="preview" class="hidden" style="margin-top:18px"></div>
      </div>`;
    wireNav();
    let previewMeta = null;
    const showPreview = (meta) => {
      previewMeta = meta;
      const box = $("#preview");
      box.classList.remove("hidden");
      box.innerHTML = `
        <div class="preview">
          <img src="${escapeHtml(meta.thumb_url)}" alt="" />
          <div>
            <h3 style="margin:0 0 6px">${escapeHtml(meta.title)}</h3>
            <div class="muted">${escapeHtml(meta.channel_title || "")}${meta.duration_sec != null ? " · " + (meta.duration_label || "") : ""}</div>
            <div class="field" style="margin-top:12px">
              <label>Тег (необязательно)</label>
              <input id="tag-name" placeholder="например: готовка" />
            </div>
          </div>
        </div>`;
    };
    $("#resolve-btn").onclick = async () => {
      try {
        const data = await api("/api/videos/resolve", {
          method: "POST",
          body: JSON.stringify({ url: $("#yt-url").value.trim() }),
        });
        showPreview(data.video);
      } catch (e) {
        toast(e.message);
      }
    };
    $("#save-btn").onclick = async () => {
      try {
        const tag = $("#tag-name")?.value?.trim();
        const body = {
          url: $("#yt-url").value.trim(),
          source: shared.url || shared.text ? "share" : "paste",
        };
        if (tag) body.tags = [tag];
        const data = await api("/api/videos/save", {
          method: "POST",
          body: JSON.stringify(body),
        });
        toast("В очереди");
        navigate(`/v/${data.item.video_id}`);
      } catch (e) {
        toast(e.message);
      }
    };
    if (initial) {
      try {
        const data = await api("/api/videos/resolve", {
          method: "POST",
          body: JSON.stringify({ url: initial }),
        });
        showPreview(data.video);
      } catch (_) {}
    }
  }

  async function renderLists() {
    const data = await api("/api/lists");
    app.innerHTML = `
      ${topbar("lists")}
      <section class="hero">
        <h1>Списки</h1>
        <p>Собери подборки из уже сохранённого.</p>
      </section>
      <div class="panel" style="margin-bottom:18px">
        <div class="field">
          <label>Новый список</label>
          <input id="list-title" placeholder="Вечерняя готовка" />
        </div>
        <button class="btn" id="create-list">Создать</button>
      </div>
      <div class="grid" id="lists-grid">
        ${(data.lists || []).map((l) => `
          <button class="card" style="text-align:left;cursor:pointer;padding:16px" data-list="${l.id}">
            <h3 class="card-title" style="min-height:auto">${escapeHtml(l.title)}</h3>
            <div class="card-meta">${l.count} видео</div>
          </button>`).join("") || `<div class="empty">Списков пока нет</div>`}
      </div>
      <div id="list-detail" class="hidden" style="margin-top:22px"></div>`;
    wireNav();
    $("#create-list").onclick = async () => {
      try {
        await api("/api/lists", {
          method: "POST",
          body: JSON.stringify({ title: $("#list-title").value.trim() }),
        });
        renderLists();
      } catch (e) {
        toast(e.message);
      }
    };
    document.querySelectorAll("[data-list]").forEach((btn) => {
      btn.onclick = async () => {
        const id = btn.getAttribute("data-list");
        const d = await api(`/api/lists/${id}`);
        const box = $("#list-detail");
        box.classList.remove("hidden");
        box.innerHTML = `
          <h2 style="margin:0 0 12px">${escapeHtml(d.list.title)}</h2>
          <div class="grid">${d.items?.length ? d.items.map(cardHtml).join("") : `<div class="empty">Пусто — добавь видео из карточки</div>`}</div>`;
        wireNav();
      };
    });
  }

  async function renderVideo(videoId) {
    const data = await api(`/api/videos/${encodeURIComponent(videoId)}`);
    const item = data.item;
    let similar = { items: [] };
    try {
      similar = await api(`/api/videos/${encodeURIComponent(videoId)}/similar`);
    } catch (_) {}
    const tags = (item.user_tags || []).map((t) =>
      `<span class="tag-pill">${escapeHtml((t.emoji || "") + " " + t.name)}</span>`
    ).join("");
    app.innerHTML = `
      ${topbar("queue")}
      <div class="video-page">
        <div>
          <div class="video-hero">
            <img src="${escapeHtml(item.thumb_url)}" alt="" />
          </div>
          <h1 style="font-family:var(--display);letter-spacing:-0.03em;margin:16px 0 8px;font-size:1.6rem">${escapeHtml(item.title)}</h1>
          <div class="muted">${escapeHtml(item.channel_title || "")}${item.duration_label ? " · " + escapeHtml(item.duration_label) : ""}</div>
          <div style="margin-top:12px">${tags}</div>
          <p class="muted" style="margin-top:14px;line-height:1.5;white-space:pre-wrap">${escapeHtml((item.description || "").slice(0, 600))}</p>
        </div>
        <div class="panel">
          <div class="btn-row" style="flex-direction:column;align-items:stretch">
            <button class="btn" id="open-yt">Открыть на YouTube</button>
            <button class="btn secondary" id="mark-watched">${item.status === "watched" ? "Уже в просмотренных" : "Отметить просмотренным"}</button>
            <button class="btn ghost" id="back-queue">Вернуть в очередь</button>
            <button class="btn ghost" id="delete-item">Убрать из библиотеки</button>
          </div>
          <div class="field" style="margin-top:16px">
            <label>Тег</label>
            <input id="new-tag" placeholder="вайб / тема" />
          </div>
          <button class="btn secondary" id="add-tag">Повесить тег</button>
          <div class="field" style="margin-top:16px">
            <label>В список (id)</label>
            <div class="btn-row">
              <select id="list-select" style="flex:1;border-radius:12px;padding:10px;background:var(--bg-elev-2);color:var(--text);border:1px solid var(--border)"></select>
              <button class="btn secondary" id="add-to-list">Добавить</button>
            </div>
          </div>
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

    $("#open-yt").onclick = async () => {
      try {
        const r = await api(`/api/videos/${encodeURIComponent(videoId)}/open`, {
          method: "POST",
          body: "{}",
        });
        window.open(r.watch_url || item.watch_url, "_blank", "noopener");
      } catch (_) {
        window.open(item.watch_url, "_blank", "noopener");
      }
    };
    $("#mark-watched").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "watched" }),
      });
      toast("Отмечено");
      renderVideo(videoId);
    };
    $("#back-queue").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "queue" }),
      });
      toast("В очереди");
      renderVideo(videoId);
    };
    $("#delete-item").onclick = async () => {
      await api(`/api/library/${encodeURIComponent(videoId)}`, { method: "DELETE" });
      toast("Убрано");
      navigate("/queue");
    };
    $("#add-tag").onclick = async () => {
      const name = $("#new-tag").value.trim();
      if (!name) return;
      await api(`/api/videos/${encodeURIComponent(videoId)}/tags`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      renderVideo(videoId);
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
    if (path === "/add") return renderAdd();
    if (path === "/lists") return renderLists();
    if (path === "/onboard") return renderOnboard();
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
