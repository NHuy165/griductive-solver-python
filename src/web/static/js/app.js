/* Griductive web client — public state only. */
(() => {
  "use strict";

  const LEVELS = Array.isArray(window.__LEVELS__) ? window.__LEVELS__ : [];

  const el = {};
  let state = window.__INITIAL_STATE__ || null;
  let selectedIndex = null;
  let activeClueId = null;
  let hintIndex = null;
  let highlightCells = new Set();
  let highlightOwner = null;
  let recentFlips = new Set();
  let busy = false;
  let toastTimer = null;
  let toastHideTimer = null;
  let boardStatusTimer = null;
  let winTimer = null;
  let flashToken = 0;

  // ------------------------------------------------------------------
  // Small helpers
  // ------------------------------------------------------------------

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function sizeOf(data) {
    return Math.round(Math.sqrt(Number(data.map_size || 0)));
  }

  function sleep(ms) {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  async function api(path, payload = {}) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
      data = {};
    }

    if (!response.ok) {
      const error = new Error(
        data.error || data.message || "Không thể kết nối tới máy chủ."
      );
      error.data = data;
      throw error;
    }

    return data;
  }

  // ------------------------------------------------------------------
  // Bootstrap
  // ------------------------------------------------------------------

  function cacheElements() {
    const ids = [
      "level-select",
      "load-btn",
      "restart-btn",
      "help-btn",
      "stat-revealed",
      "stat-remaining",
      "stat-steps",
      "board",
      "board-status",
      "hint-btn",
      "auto-btn",
      "clue-count",
      "clue-list",
      "stats-grid",
      "auto-summary",
      "trace-count",
      "trace-list",
      "toast",
      "toast-text",
      "help-modal",
    ];

    ids.forEach((id) => {
      el[id.replace(/-([a-z])/g, (_m, letter) => letter.toUpperCase())] =
        document.getElementById(id);
    });
  }

  function populateLevels() {
    el.levelSelect.innerHTML = LEVELS.map((level) => {
      const label = `Màn ${level.number} · ${level.title} (${level.size}×${level.size})`;
      return `<option value="${escapeHtml(level.id)}">${escapeHtml(label)}</option>`;
    }).join("");

    if (state) {
      el.levelSelect.value = state.level.id;
    }
  }

  function bindEvents() {
    document.querySelectorAll(".tab-btn[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        switchTab(button.getAttribute("data-tab"));
      });
    });

    el.loadBtn.addEventListener("click", loadLevel);
    el.restartBtn.addEventListener("click", restartLevel);
    el.helpBtn.addEventListener("click", openHelp);
    el.hintBtn.addEventListener("click", requestHint);
    el.autoBtn.addEventListener("click", runAutoSolve);

    el.board.addEventListener("click", (event) => {
      const verdictButton = event.target.closest("[data-verdict]");
      if (verdictButton) {
        submitVerdict(verdictButton.getAttribute("data-verdict"));
        return;
      }

      const cell = event.target.closest(".cell");
      if (cell && !cell.classList.contains("cell--verdict")) {
        handleCellClick(Number(cell.getAttribute("data-index")));
      }
    });

    document.addEventListener(
      "click",
      (event) => {
        if (selectedIndex === null || busy) {
          return;
        }
        const panel = el.board.querySelector(".cell.selected");
        if (panel && panel.contains(event.target)) {
          return;
        }
        clearSelection();
      },
      true
    );

    el.board.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      const cell = event.target.closest(".cell");
      if (cell && event.target === cell) {
        event.preventDefault();
        handleCellClick(Number(cell.getAttribute("data-index")));
      }
    });

    el.clueList.addEventListener("click", (event) => {
      const target = event.target.closest("[data-clue-id]");
      if (target) {
        activateClue(target.getAttribute("data-clue-id"));
      }
    });

    el.helpModal.addEventListener("click", (event) => {
      if (event.target.closest("[data-close-modal]")) {
        closeHelp();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") {
        return;
      }

      const win = document.querySelector(".win-overlay");
      if (win) {
        closeWin();
        return;
      }

      if (!el.helpModal.hidden) {
        closeHelp();
        return;
      }

      if (selectedIndex !== null || activeClueId || hintIndex !== null) {
        clearSelection();
      }
    });
  }

  function init() {
    cacheElements();

    if (!state) {
      document.body.innerHTML =
        '<main class="content"><p style="padding:40px;font-weight:700">Không tải được trạng thái màn chơi. Hãy khởi động lại máy chủ.</p></main>';
      return;
    }

    populateLevels();
    bindEvents();
    render();
    refreshModalLock();
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------

  function render(data = state) {
    if (!data) {
      return;
    }

    if (
      selectedIndex !== null &&
      !data.people.some(
        (person) => person.index === selectedIndex && !person.revealed
      )
    ) {
      selectedIndex = null;
    }

    renderHeader(data);
    renderBoard(data);
    renderClues(data);
    renderStats(data);
    renderTrace(data);
    updateControls(data);
  }

  function renderHeader(data) {
    const size = sizeOf(data);
    const flipped = data.flipped.length;

    el.statRevealed.textContent = String(flipped);
    el.statRemaining.textContent = String(data.remaining);
    el.statSteps.textContent = String(data.trace.length);

    el.board.style.setProperty("--n", String(size));
    el.board.dataset.size = String(size);
    document.title = `${data.level.title} · Griductive`;
  }

  function renderBoard(data) {
    el.board.innerHTML = data.people
      .map((person) => cellMarkup(person, data))
      .join("");
  }

  function cellMarkup(person, data) {
    const classes = ["cell"];

    if (person.revealed) {
      classes.push(
        "revealed",
        person.status === "CRIMINAL" ? "status-criminal" : "status-innocent"
      );
    } else {
      classes.push("face-down");
    }

    if (selectedIndex === person.index && !person.revealed) {
      classes.push("selected");
    }
    if (hintIndex === person.index) {
      classes.push("hinted");
    }
    if (highlightCells.has(person.index)) {
      classes.push("highlighted");
    }
    if (highlightOwner === person.index) {
      classes.push("highlight-owner");
    }
    if (recentFlips.has(person.index)) {
      classes.push("just-flipped");
    }

    const coord = escapeHtml(person.coord);
    const name = escapeHtml(person.name);
    const job = escapeHtml(person.occupation);

    if (!person.revealed && selectedIndex === person.index) {
      classes.push("cell--verdict");
      const disabled = busy ? " disabled" : "";
      return `
        <div class="${classes.join(" ")}" data-index="${person.index}" role="group"
             aria-label="Chọn phán đoán cho ${escapeHtml(person.name)} (${escapeHtml(person.coord)})">
          <button class="cell-verdict cell-verdict--criminal" type="button" data-verdict="CRIMINAL"${disabled}>
            TỘI PHẠM
          </button>
          <button class="cell-verdict cell-verdict--innocent" type="button" data-verdict="INNOCENT"${disabled}>
            VÔ TỘI
          </button>
        </div>
      `;
    }

    const statusLabel = person.revealed
      ? person.status === "CRIMINAL"
        ? "● Tội phạm"
        : "◆ Vô tội"
      : "■ Chưa lật";

    let aria = `${person.coord}, ${person.name}, ${person.occupation}, ${statusLabel}`;
    if (person.revealed && person.clue) {
      aria += `. Manh mối ${person.clue.id}: ${person.clue.text}`;
    }

    const disabled = busy ? ' aria-disabled="true"' : "";
    const tabindex = busy ? "-1" : "0";
    const pressed = selectedIndex === person.index ? ' aria-pressed="true"' : "";

    const head = `
      <div class="cell-head">
        <span class="cell-coord">${coord}</span>
        <span class="cell-state">${statusLabel}</span>
      </div>
    `;

    const identity = `
      <div class="cell-identity">
        <span class="cell-name">${name}</span>
        <span class="cell-job">${job}</span>
      </div>
    `;

    if (!person.revealed) {
      return `
        <div class="${classes.join(" ")}" role="button" tabindex="${tabindex}"${disabled}${pressed}
             data-index="${person.index}" aria-label="${escapeHtml(aria)}">
          ${head}
          ${identity}
        </div>
      `;
    }

    const clue = person.clue;
    const clueMarkup = clue
      ? `
        <div class="cell-clue">
          <span class="cell-clue-text">${escapeHtml(clue.text)}</span>
        </div>
      `
      : "";

    return `
      <div class="${classes.join(" ")}" role="button" tabindex="${tabindex}"${disabled}${pressed}
           data-index="${person.index}" aria-label="${escapeHtml(aria)}"
           title="Nhấn để xem vùng manh mối">
        ${head}
        ${identity}
        ${clueMarkup}
      </div>
    `;
  }

  function switchTab(tabName) {
    document.querySelectorAll(".tab-btn[data-tab]").forEach((button) => {
      const active = button.getAttribute("data-tab") === tabName;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });

    const panes = {
      clues: document.getElementById("pane-clues"),
      trace: document.getElementById("pane-trace"),
      stats: document.getElementById("pane-stats"),
    };

    Object.entries(panes).forEach(([name, pane]) => {
      if (pane) {
        const active = name === tabName;
        pane.hidden = !active;
        pane.classList.toggle("is-active", active);
      }
    });
  }

  function renderClues(data) {
    el.clueCount.textContent = String(data.revealed_clues.length);

    if (data.revealed_clues.length === 0) {
      el.clueList.innerHTML = `
        <div class="clue-empty">
          Chưa có manh mối nào. Hãy lật lá bài đầu tiên hoặc dùng Gợi ý.
        </div>
      `;
      return;
    }

    el.clueList.innerHTML = data.revealed_clues
      .map((clue) => {
        const active = clue.id === activeClueId;
        return `
          <button class="clue-item${active ? " is-active" : ""}"
                  type="button" data-clue-id="${escapeHtml(clue.id)}" aria-pressed="${active}">
            <span class="clue-text">${escapeHtml(clue.text)}</span>
          </button>
        `;
      })
      .join("");
  }

  function renderStats(data) {
    const auto = data.last_auto;
    const rows = [
      ["Mệnh đề KB", data.stats.kb_clauses],
      ["Clause ban đầu", data.stats.initial_clauses],
      ["Clause toàn bộ", data.stats.full_clauses],
      ["Biến phụ", data.stats.auxiliary],
      ["SAT gần nhất", auto ? auto.sat_calls : "—"],
      ["Thời gian auto", auto ? `${Number(auto.time_ms).toFixed(2)} ms` : "—"],
    ];

    el.statsGrid.innerHTML = rows
      .map(
        ([label, value]) => `
          <div class="stat-row">
            <b>${escapeHtml(value)}</b>
            <small>${escapeHtml(label)}</small>
          </div>
        `
      )
      .join("");

    if (auto) {
      el.autoSummary.hidden = false;
      el.autoSummary.innerHTML = `
        <b>Tự động giải</b>
        ${auto.waves} đợt · ${auto.sat_calls} SAT · ${auto.decisions} quyết định ·
        ${auto.backtracks} quay lui · ${Number(auto.time_ms).toFixed(2)} ms<br>
        ${escapeHtml(autoMessage(auto))}
      `;
    } else {
      el.autoSummary.hidden = true;
      el.autoSummary.innerHTML = "";
    }
  }

  function autoMessage(auto) {
    if (auto.status === "SUCCESS") {
      return "Agent đã kết luận được toàn bộ bàn chơi.";
    }
    if (auto.status === "STUCK") {
      return "Agent dừng lại vì chưa đủ dữ kiện công khai.";
    }
    return "Cơ sở tri thức đã mâu thuẫn trong quá trình suy luận.";
  }

  function renderTrace(data) {
    el.traceCount.textContent = String(data.trace.length);

    if (data.trace.length === 0) {
      el.traceList.innerHTML = `
        <div class="trace-empty">
          Chưa có bước suy luận nào. Nhật ký sẽ ghi lại mỗi lần bạn lật bài hoặc để agent chạy.
        </div>
      `;
      return;
    }

    el.traceList.innerHTML = [...data.trace]
      .reverse()
      .map((step) => {
        const criminal = step.verdict === "CRIMINAL";
        const verdictClass = criminal
          ? "trace-verdict--criminal"
          : "trace-verdict--innocent";
        const verdictLabel = criminal ? "● TỘI PHẠM" : "◆ VÔ TỘI";
        const stepNum = String(step.step).padStart(2, "0");
        return `
          <div class="trace-item${step.kind === "auto" ? " trace-item--auto" : ""}">
            <span class="trace-step">#${stepNum}</span>
            <div class="trace-body">
              <div class="trace-title">
                ${escapeHtml(step.coord)} · ${escapeHtml(step.name)} →
                <span class="${verdictClass}">${verdictLabel}</span>
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function updateControls(data) {
    const locked = busy || data.solved;

    el.loadBtn.disabled = busy;
    el.restartBtn.disabled = busy;
    el.levelSelect.disabled = busy;
    el.hintBtn.disabled = locked;
    el.autoBtn.disabled = locked;
  }

  // ------------------------------------------------------------------
  // Player actions
  // ------------------------------------------------------------------

  function handleCellClick(index) {
    if (busy || !state) {
      return;
    }

    const person = state.people.find((item) => item.index === index);
    if (!person) {
      return;
    }

    if (person.revealed) {
      if (person.clue) {
        activateClue(person.clue.id);
      }
      return;
    }

    if (selectedIndex === index) {
      clearSelection();
      return;
    }

    selectedIndex = index;
    hintIndex = null;
    activeClueId = null;
    highlightCells = new Set();
    highlightOwner = null;
    render();
  }

  function activateClue(clueId) {
    if (!clueId || !state) {
      return;
    }

    const clue = state.revealed_clues.find((item) => item.id === clueId);
    if (!clue) {
      return;
    }

    if (activeClueId === clueId) {
      activeClueId = null;
      highlightCells = new Set();
      highlightOwner = null;
    } else {
      activeClueId = clueId;
      highlightCells = new Set(clue.region);
      highlightOwner = clue.owner;
      switchTab("clues");
    }

    render();
  }

  function clearSelection() {
    selectedIndex = null;
    activeClueId = null;
    hintIndex = null;
    highlightCells = new Set();
    highlightOwner = null;
    render();
  }

  function setBusy(mode) {
    busy = Boolean(mode);
    render();
  }

  async function loadLevel() {
    if (busy || !state) {
      return;
    }

    const levelId = el.levelSelect.value;
    if (!levelId) {
      return;
    }

    setBusy("load");
    showBoardStatus("Đang mở màn chơi…", true);

    try {
      const data = await api("/api/load", { level_id: levelId });
      closeWin();
      adoptState(data.state);
      showToast("success", data.message);
    } catch (error) {
      showToast("error", error.message);
    } finally {
      setBusy(null);
      hideBoardStatus(350);
    }
  }

  async function restartLevel() {
    if (busy || !state) {
      return;
    }

    setBusy("restart");
    showBoardStatus("Đang đưa màn chơi về trạng thái ban đầu…", true);

    try {
      const data = await api("/api/restart");
      closeWin();
      adoptState(data.state);
      showToast("info", data.message);
    } catch (error) {
      showToast("error", error.message);
    } finally {
      setBusy(null);
      hideBoardStatus(350);
    }
  }

  async function submitVerdict(verdict) {
    if (busy || !state || selectedIndex === null) {
      return;
    }

    const index = selectedIndex;
    setBusy("verdict");
    showBoardStatus("Đang kiểm tra phán đoán…", true);

    try {
      const data = await api("/api/verdict", { index, verdict });
      state = data.state;

      if (data.result === "CORRECT") {
        selectedIndex = null;
        hintIndex = null;
        activeClueId = null;
        highlightCells = new Set();
        highlightOwner = null;
        flashCells([index]);
        render();
        showToast("success", data.message);

        if (state.solved) {
          scheduleWin();
        }
      } else {
        showToast(
          data.result === "CONTRADICTED" ? "error" : "info",
          `${data.result} — ${data.message}`
        );
        setTimeout(() => shakeCell(index), 0);
      }
    } catch (error) {
      render();
      showToast("error", error.message);
    } finally {
      setBusy(null);
      hideBoardStatus(500);
    }
  }

  async function requestHint() {
    if (busy || !state) {
      return;
    }

    setBusy("hint");
    showBoardStatus("Đang tìm kết luận kế tiếp từ manh mối công khai…", true);

    try {
      const data = await api("/api/hint");
      state = data.state;

      if (data.hint) {
        selectedIndex = data.hint.index;
        hintIndex = data.hint.index;
        activeClueId =
          data.hint.clue_ids.length === 1 ? data.hint.clue_ids[0] : null;
        highlightCells = new Set();
        const ids = new Set(data.hint.clue_ids);
        state.revealed_clues
          .filter((clue) => ids.has(clue.id))
          .forEach((clue) => {
            clue.region.forEach((cellIndex) => highlightCells.add(cellIndex));
          });
        highlightOwner = null;
        render();
      } else {
        selectedIndex = null;
        hintIndex = null;
        activeClueId = null;
        highlightCells = new Set();
        highlightOwner = null;
        render();
      }

      showToast("info", data.message);
    } catch (error) {
      render();
      showToast("error", error.message);
    } finally {
      setBusy(null);
      hideBoardStatus(350);
    }
  }

  async function runAutoSolve() {
    if (busy || !state) {
      return;
    }

    selectedIndex = null;
    hintIndex = null;
    activeClueId = null;
    highlightCells = new Set();
    highlightOwner = null;
    setBusy("auto");

    try {
      const data = await api("/api/auto-solve", {});
      let display = state;
      const totalWaves = data.steps.length;

      for (const step of data.steps) {
        display = mergeWave(display, step);
        flashCells(step.new_people.map((person) => person.index));
        render(display);
        showBoardStatus(
          `Đợt ${step.wave}/${totalWaves} · ${step.new_people.length} lá bài vừa lật`,
          true
        );
        await sleep(680);
      }

      state = data.state;
      render();
      showToast(
        data.summary.status === "SUCCESS" ? "success" : "info",
        data.message
      );

      if (state.solved) {
        scheduleWin();
      }
    } catch (error) {
      render();
      showToast("error", error.message);
    } finally {
      setBusy(null);
      hideBoardStatus(700);
    }
  }

  function mergeWave(current, step) {
    const newByIndex = new Map(
      step.new_people.map((person) => [person.index, person])
    );
    const people = current.people.map(
      (person) => newByIndex.get(person.index) || person
    );
    const clues = [...current.revealed_clues];
    step.new_people.forEach((person) => {
      if (person.clue) {
        clues.push(person.clue);
      }
    });
    clues.sort((left, right) => left.owner - right.owner);

    const flipped = Array.from(
      new Set([...current.flipped, ...step.new_people.map((person) => person.index)])
    ).sort((left, right) => left - right);

    return {
      ...current,
      people,
      flipped,
      remaining: current.map_size - flipped.length,
      solved: flipped.length === current.map_size,
      kb_clauses: step.kb_clauses_after,
      revealed_clues: clues,
      stats: { ...current.stats, kb_clauses: step.kb_clauses_after },
    };
  }

  function adoptState(next) {
    clearTimeout(winTimer);
    winTimer = null;
    state = next;
    selectedIndex = null;
    activeClueId = null;
    hintIndex = null;
    highlightCells = new Set();
    highlightOwner = null;
    recentFlips = new Set();
    flashToken += 1;
    el.levelSelect.value = state.level.id;
    render();
  }

  function scheduleWin() {
    clearTimeout(winTimer);
    winTimer = setTimeout(() => {
      winTimer = null;
      if (state && state.solved) {
        showWin();
      }
    }, 780);
  }

  // ------------------------------------------------------------------
  // Visual feedback
  // ------------------------------------------------------------------

  function flashCells(indices) {
    recentFlips = new Set(indices);
    const token = ++flashToken;
    setTimeout(() => {
      if (token !== flashToken) {
        return;
      }
      recentFlips = new Set();
      document
        .querySelectorAll(".cell.just-flipped")
        .forEach((cell) => cell.classList.remove("just-flipped"));
    }, 950);
  }

  function shakeCell(index) {
    const cell = el.board.querySelector(`.cell[data-index="${index}"]`);
    if (!cell) {
      return;
    }
    cell.classList.add("shake");
    setTimeout(() => cell.classList.remove("shake"), 500);
  }

  function showBoardStatus(message, spinner = false) {
    clearTimeout(boardStatusTimer);
    el.boardStatus.innerHTML = spinner
      ? '<span class="spinner"></span><span></span>'
      : "<span></span>";
    const label = el.boardStatus.querySelector("span:last-child");
    if (label) {
      label.textContent = message;
    }
    el.boardStatus.hidden = false;
  }

  function hideBoardStatus(delay = 0) {
    clearTimeout(boardStatusTimer);
    if (delay > 0) {
      boardStatusTimer = setTimeout(() => {
        el.boardStatus.hidden = true;
      }, delay);
      return;
    }
    el.boardStatus.hidden = true;
  }

  function showToast(type, message) {
    clearTimeout(toastTimer);
    clearTimeout(toastHideTimer);

    el.toast.hidden = false;
    el.toast.className = `toast toast--${type}`;
    el.toastText.textContent = message;

    requestAnimationFrame(() => {
      el.toast.classList.add("is-visible");
    });

    const visibleFor = Math.min(
      7000,
      Math.max(3400, String(message).length * 42)
    );
    toastTimer = setTimeout(() => {
      el.toast.classList.remove("is-visible");
      toastHideTimer = setTimeout(() => {
        el.toast.hidden = true;
      }, 240);
    }, visibleFor);
  }

  // ------------------------------------------------------------------
  // Help and victory modals
  // ------------------------------------------------------------------

  function openHelp() {
    el.helpModal.hidden = false;
    refreshModalLock();
    const closeButton = el.helpModal.querySelector(".modal-head [data-close-modal]");
    if (closeButton) {
      closeButton.focus();
    }
  }

  function closeHelp() {
    el.helpModal.hidden = true;
    refreshModalLock();
    el.helpBtn.focus();
  }

  function refreshModalLock() {
    const helpOpen = !el.helpModal.hidden;
    const winOpen = Boolean(document.querySelector(".win-overlay"));
    document.body.classList.toggle("modal-open", helpOpen || winOpen);
  }

  function showWin() {
    if (document.querySelector(".win-overlay")) {
      return;
    }

    const stats = state.stats;
    const auto = state.last_auto;
    const timeStat = auto ? `${Number(auto.time_ms).toFixed(2)} ms` : "—";
    const overlay = document.createElement("div");
    overlay.className = "modal win-overlay";
    overlay.innerHTML = `
      <div class="modal-backdrop" data-close-win></div>
      <div class="modal-panel win-panel" role="dialog" aria-modal="true" aria-labelledby="win-title">
        <span class="modal-stamp">HOÀN TẤT MÀN ${state.level.number} // CHỨNG MINH THÀNH CÔNG</span>
        <h2 class="win-title" id="win-title">KẾT LUẬN TOÀN BỘ</h2>
        <p class="win-sub">
          Bạn đã suy luận chính xác toàn bộ ${state.map_size} nhân vật của màn
          “${escapeHtml(state.level.title)}” hoàn toàn từ manh mối công khai, không cần đoán mò.
        </p>
        <dl class="win-stats">
          <div class="win-stat"><dt>TỔNG BƯỚC</dt><dd>${state.trace.length}</dd></div>
          <div class="win-stat"><dt>MỆNH ĐỀ KB</dt><dd>${stats.kb_clauses}</dd></div>
          <div class="win-stat"><dt>CLAUSE TOÀN BỘ</dt><dd>${stats.full_clauses}</dd></div>
          <div class="win-stat"><dt>THỜI GIAN AUTO</dt><dd>${escapeHtml(timeStat)}</dd></div>
        </dl>
        <div class="win-actions">
          <button class="btn btn--primary" type="button" data-win-restart>Chơi lại</button>
          <button class="btn btn--quiet" type="button" data-close-win>Xem bàn chơi</button>
        </div>
      </div>
    `;

    document.body.append(overlay);
    refreshModalLock();

    overlay.addEventListener("click", (event) => {
      if (event.target.closest("[data-win-restart]")) {
        closeWin();
        restartLevel();
        return;
      }
      if (event.target.closest("[data-close-win]")) {
        closeWin();
      }
    });

    const closeButton = overlay.querySelector("[data-win-restart]");
    if (closeButton) {
      closeButton.focus();
    }
  }

  function closeWin() {
    clearTimeout(winTimer);
    winTimer = null;

    const overlay = document.querySelector(".win-overlay");
    if (overlay) {
      overlay.remove();
      refreshModalLock();
      el.restartBtn.focus();
    }
  }

  // ------------------------------------------------------------------

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
