const $ = (selector) => document.querySelector(selector);
let pdfjsLib;
let activeQuestion = "";
let activeAnswer = "";
let activeSource = null;
let activeChatId = null;
let activeMenuChat = null;
let activeMenuWrap = null;
let deleteTargetChat = null;
let toastTimeout = null;
let pdfZoom = 1;

function setEvidenceVisible(visible) {
  const shell = $("#app-shell");
  const panel = $("#evidence-panel");
  shell.classList.toggle("evidence-hidden", !visible);
  panel.hidden = !visible;
}

function showToast(message) {
  const toast = $("#app-toast");
  const text = $("#toast-text");
  if (!toast || !text) return;
  text.textContent = message;
  toast.hidden = false;
  if (toastTimeout) clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.hidden = true;
  }, 2800);
}

function pdfUrlFor(source) {
  if (source.pdf_url) return source.pdf_url;
  return `/api/manuals/${encodeURIComponent(source.manual_id)}/pdf/#page=${encodeURIComponent(source.page_number)}`;
}

async function getPdfJs() {
  if (pdfjsLib) return pdfjsLib;
  try {
    pdfjsLib = await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs");
    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs";
    return pdfjsLib;
  } catch (error) {
    console.warn("PDF.js could not be loaded", error);
    return null;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatInline(text) {
  if (!text) return "";
  let escaped = escapeHtml(text);

  // Bold **text**
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Inline code `code`
  escaped = escaped.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');

  // Inline citations: [S1], [S1, S2], [S1, S3]
  escaped = escaped.replace(/\[(S\d+(?:\s*,\s*S\d+)*)\]/gi, (match, rawInner) => {
    const parts = rawInner.split(",").map((p) => p.trim());
    const badges = parts.map((p) => {
      if (/^S\d+$/i.test(p)) {
        const id = p.toUpperCase();
        return `<button type="button" class="inline-citation-badge" data-source-id="${id}" title="Jump to citation ${id}">[${id}]</button>`;
      }
      return `[${p}]`;
    });
    return badges.join(" ");
  });

  return escaped;
}

function formatMarkdown(rawText, sources = []) {
  if (!rawText) return "";
  const lines = rawText.trim().split(/\r?\n/);
  const htmlParts = [];
  let i = 0;
  const n = lines.length;

  while (i < n) {
    const line = lines[i].trim();
    if (!line) {
      i++;
      continue;
    }

    // Markdown Table: header line with pipes, followed by divider line |--|--|
    if (line.startsWith("|") && line.endsWith("|") && i + 1 < n && /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/.test(lines[i + 1])) {
      const headerLine = line;
      i += 2; // skip header and divider
      const headers = headerLine.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const rows = [];
      while (i < n && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        rows.push(cells);
        i++;
      }
      const tableHtml = ['<div class="chat-table-wrap table-responsive"><table class="chat-table table table-sm table-bordered">'];
      tableHtml.push("<thead><tr>");
      headers.forEach((h) => tableHtml.push(`<th>${formatInline(h)}</th>`));
      tableHtml.push("</tr></thead><tbody>");
      rows.forEach((r) => {
        tableHtml.push("<tr>");
        r.forEach((c) => tableHtml.push(`<td>${formatInline(c)}</td>`));
        tableHtml.push("</tr>");
      });
      tableHtml.push("</tbody></table></div>");
      htmlParts.push(tableHtml.join(""));
      continue;
    }

    // Headings #, ##, ###
    const h3Match = line.match(/^###\s+(.*)$/);
    if (h3Match) {
      htmlParts.push(`<h5 class="chat-heading chat-h3">${formatInline(h3Match[1])}</h5>`);
      i++;
      continue;
    }
    const h2Match = line.match(/^##\s+(.*)$/);
    if (h2Match) {
      htmlParts.push(`<h4 class="chat-heading chat-h2">${formatInline(h2Match[1])}</h4>`);
      i++;
      continue;
    }
    const h1Match = line.match(/^#\s+(.*)$/);
    if (h1Match) {
      htmlParts.push(`<h3 class="chat-heading chat-h1">${formatInline(h1Match[1])}</h3>`);
      i++;
      continue;
    }

    // Safety Warnings & Cautions & Callouts
    const warnMatch = line.match(/^(?:⚠️\s*|Warning:\s*|Caution:\s*|Danger:\s*|Important:\s*)+(.*)$/i);
    if (warnMatch) {
      const content = warnMatch[1].trim() || line;
      htmlParts.push(`
        <div class="chat-callout chat-callout-warning">
          <span class="callout-icon">⚠️</span>
          <div class="chat-callout-body"><strong>Warning / Caution:</strong> ${formatInline(content)}</div>
        </div>
      `);
      i++;
      continue;
    }

    const noteMatch = line.match(/^(?:Note:\s*|Notice:\s*)+(.*)$/i);
    if (noteMatch) {
      const content = noteMatch[1].trim() || line;
      htmlParts.push(`
        <div class="chat-callout chat-callout-note">
          <span class="callout-icon">ℹ️</span>
          <div class="chat-callout-body"><strong>Note:</strong> ${formatInline(content)}</div>
        </div>
      `);
      i++;
      continue;
    }

    // Numbered Steps
    const stepMatch = line.match(/^(\d+)[\.\)]\s+(.*)$/);
    if (stepMatch) {
      const stepItems = [];
      while (i < n) {
        const currLine = lines[i].trim();
        const currMatch = currLine.match(/^(\d+)[\.\)]\s+(.*)$/);
        if (!currMatch) break;
        stepItems.push({ num: currMatch[1], body: currMatch[2] });
        i++;
      }
      const stepsHtml = ['<div class="chat-step-list">'];
      stepItems.forEach((st) => {
        stepsHtml.push(`
          <div class="chat-step-item">
            <span class="step-num">${st.num}</span>
            <div class="step-body">${formatInline(st.body)}</div>
          </div>
        `);
      });
      stepsHtml.push("</div>");
      htmlParts.push(stepsHtml.join(""));
      continue;
    }

    // Bullets - , * , •
    const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
    if (bulletMatch) {
      const bulletItems = [];
      while (i < n) {
        const currLine = lines[i].trim();
        const currMatch = currLine.match(/^[-*•]\s+(.*)$/);
        if (!currMatch) break;
        bulletItems.push(currMatch[1]);
        i++;
      }
      const bHtml = ['<ul class="chat-bullet-list">'];
      bulletItems.forEach((b) => bHtml.push(`<li>${formatInline(b)}</li>`));
      bHtml.push("</ul>");
      htmlParts.push(bHtml.join(""));
      continue;
    }

    // Regular Paragraph
    const pLines = [];
    while (i < n) {
      const currLine = lines[i].trim();
      if (!currLine) break;
      if (
        currLine.startsWith("#") ||
        (currLine.startsWith("|") && currLine.endsWith("|")) ||
        /^(?:⚠️|Warning:|Caution:|Danger:|Important:|Note:|Notice:)/i.test(currLine) ||
        /^\d+[\.\)]\s+/.test(currLine) ||
        /^[-*•]\s+/.test(currLine)
      ) {
        break;
      }
      pLines.push(currLine);
      i++;
    }
    if (pLines.length) {
      htmlParts.push(`<p class="chat-p">${formatInline(pLines.join(" "))}</p>`);
    }
  }

  return htmlParts.join("");
}

/* AI Generation Loading State */
let loadingInterval = null;
const LOADING_STATUSES = [
  "Searching the manuals...",
  "Finding relevant specifications...",
  "Checking technical procedures...",
  "Verifying document citations...",
  "Cross-referencing operation guidelines...",
  "Connecting the dots...",
  "Preparing grounded answer...",
];

function showLoadingIndicator() {
  hideLoadingIndicator();
  const conversation = $("#conversation");
  if (!conversation) return;

  const wrapper = document.createElement("div");
  wrapper.id = "ai-loading-indicator";
  wrapper.className = "message assistant ai-loading-message";
  wrapper.innerHTML = `
    <div class="message-label">Assistant</div>
    <div class="message-bubble ai-loading-bubble">
      <div class="ai-loading-row">
        <div class="ai-bouncing-dots" aria-label="Thinking">
          <span class="ai-dot"></span>
          <span class="ai-dot"></span>
          <span class="ai-dot"></span>
        </div>
        <span class="ai-loading-status" id="ai-loading-status">${LOADING_STATUSES[0]}</span>
      </div>
    </div>
  `;
  conversation.append(wrapper);
  conversation.scrollTop = conversation.scrollHeight;

  let statusIndex = 0;
  loadingInterval = setInterval(() => {
    const statusEl = $("#ai-loading-status");
    if (!statusEl) return;
    statusEl.classList.add("fade-switch");
    setTimeout(() => {
      statusIndex = (statusIndex + 1) % LOADING_STATUSES.length;
      statusEl.textContent = LOADING_STATUSES[statusIndex];
      statusEl.classList.remove("fade-switch");
    }, 200);
  }, 2200);
}

function hideLoadingIndicator() {
  if (loadingInterval) {
    clearInterval(loadingInterval);
    loadingInterval = null;
  }
  const indicator = $("#ai-loading-indicator");
  if (indicator) {
    indicator.remove();
  }
}

function attachCitationInteractions(bubble, sources, question, answer) {
  bubble.querySelectorAll(".inline-citation-badge").forEach((badge) => {
    badge.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const sourceId = badge.dataset.sourceId;
      setEvidenceVisible(true);
      renderCitations(sources, question, answer, false);
      const sourceIndex = sources.findIndex((s, idx) =>
        (s.source_id || `S${idx + 1}`).toUpperCase() === sourceId.toUpperCase()
      );
      if (sourceIndex >= 0) {
        const card = document.querySelectorAll(".citation-card")[sourceIndex];
        if (card) {
          selectCitation(sources[sourceIndex], card, question, answer);
          card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      }
    });
  });
}

function animateAssistantText(bubble, text, onComplete) {
  const tokens = String(text || "").match(/\S+\s*/g) || [];
  let index = 0;
  bubble.textContent = "";
  const reveal = () => {
    const end = Math.min(index + 2, tokens.length);
    while (index < end) bubble.textContent += tokens[index++];
    const conversation = $("#conversation");
    if (conversation) conversation.scrollTop = conversation.scrollHeight;
    if (index < tokens.length) window.setTimeout(reveal, 24);
    else onComplete();
  };
  reveal();
}

function addMessage(kind, text, status = "", sources = [], question = "", animate = false) {
  const conversation = $("#conversation");
  $("#welcome")?.remove();
  const wrapper = document.createElement("div");
  wrapper.className = `message ${kind}`;
  const content = document.createElement("div");
  content.className = "message-content";
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = kind === "user" ? "You" : "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (kind === "user") {
    bubble.textContent = text;
  } else if (!animate) {
    bubble.innerHTML = formatMarkdown(text, sources);
    attachCitationInteractions(bubble, sources, question, text);
  }

  content.append(label, bubble);

  if (status) {
    const note = document.createElement("div");
    note.className = status.includes("Insufficient") ? "chat-callout chat-callout-insufficient" : "status-note";
    if (status.includes("Insufficient")) {
      note.innerHTML = `<span class="callout-icon">ℹ️</span><div class="chat-callout-body"><strong>Notice:</strong> ${escapeHtml(status)}</div>`;
    } else {
      note.textContent = status;
    }
    content.append(note);
  }

  let sourceRow = null;
  if (kind === "assistant" && sources && sources.length) {
    sourceRow = document.createElement("div");
    sourceRow.className = "message-sources";
    sourceRow.hidden = animate;
    sources.forEach((source, index) => {
      const sourceButton = document.createElement("button");
      sourceButton.type = "button";
      sourceButton.className = "message-source";
      sourceButton.textContent = `[${source.source_id || `S${index + 1}`}] ${source.document_name} · p.${source.page_number}`;
      sourceButton.addEventListener("click", () => {
        setEvidenceVisible(true);
        renderCitations(sources, question, text, false);
        const card = document.querySelectorAll(".citation-card")[index];
        if (card) {
          selectCitation(sources[index], card, question, text);
          card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      });
      sourceRow.append(sourceButton);
    });
    content.append(sourceRow);
  }

  wrapper.append(content);
  conversation.append(wrapper);
  conversation.scrollTop = conversation.scrollHeight;
  if (kind === "assistant" && animate) {
    animateAssistantText(bubble, text, () => {
      bubble.innerHTML = formatMarkdown(text, sources);
      attachCitationInteractions(bubble, sources, question, text);
      if (sourceRow) sourceRow.hidden = false;
    });
  }
}

function resetToNewChat() {
  activeChatId = null;
  $("#conversation").innerHTML = '<div id="welcome" class="welcome-card"><div class="welcome-icon">✦</div><h2>Ask about your machines</h2><p>Get grounded answers from the selected machine’s operation and maintenance manuals.</p><div class="suggestions"><button type="button" data-question="What does E17 mean?">What does E17 mean?</button><button type="button" data-question="What is the normal operating pressure range?">Normal operating pressure?</button><button type="button" data-question="How often is the filter checked?">How often is the filter checked?</button></div></div>';
  document.querySelectorAll("[data-question]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("#question").value = btn.dataset.question;
      $("#question").focus();
    });
  });
  renderCitations([]);
  setEvidenceVisible(false);
  document.querySelectorAll(".history-item-wrap").forEach((w) => w.classList.remove("active"));
  $("#question").focus();
}

function renderHistory(items) {
  const list = $("#history-list");
  list.replaceChildren();
  if (!items.length) {
    list.innerHTML = '<div class="empty-history">Your questions will appear here.</div>';
    return;
  }
  items.forEach((item) => {
    const wrap = document.createElement("div");
    wrap.className = "history-item-wrap";
    wrap.dataset.id = item.id;
    if (activeChatId === item.id) wrap.classList.add("active");

    const itemBtn = document.createElement("button");
    itemBtn.className = "history-item";
    itemBtn.type = "button";

    const textCol = document.createElement("div");
    textCol.className = "history-text-col";
    const qSpan = document.createElement("span");
    qSpan.className = "history-question";
    qSpan.textContent = item.title || item.question;
    const mSpan = document.createElement("span");
    mSpan.className = "history-meta";
    mSpan.textContent = `${item.machine_id} · ${item.status}`;
    textCol.append(qSpan, mSpan);

    const actions = document.createElement("div");
    actions.className = "history-actions";

    if (item.is_pinned) {
      const pin = document.createElement("span");
      pin.className = "pin-badge";
      pin.title = "Pinned";
      pin.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"></line><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.89A2 2 0 0 1 15 10.77V6a3 3 0 0 0-6 0v4.77a2 2 0 0 1-1.11 1.79l-1.78.89A2 2 0 0 0 5 15.24V17z"></path></svg>';
      actions.append(pin);
    }

    const optionsBtn = document.createElement("button");
    optionsBtn.className = "chat-options-trigger";
    optionsBtn.type = "button";
    optionsBtn.title = "Options";
    optionsBtn.setAttribute("aria-label", "Chat options");
    optionsBtn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><circle cx="5" cy="12" r="2"></circle><circle cx="12" cy="12" r="2"></circle><circle cx="19" cy="12" r="2"></circle></svg>';
    actions.append(optionsBtn);

    itemBtn.append(textCol, actions);

    // Inline Rename Box
    const renameBox = document.createElement("div");
    renameBox.className = "history-rename-box";
    renameBox.hidden = true;
    const renameInput = document.createElement("input");
    renameInput.type = "text";
    renameInput.className = "rename-input";
    renameInput.maxLength = 150;
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "rename-save-btn";
    saveBtn.title = "Save (Enter)";
    saveBtn.textContent = "✓";
    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "rename-cancel-btn";
    cancelBtn.title = "Cancel (Esc)";
    cancelBtn.textContent = "✕";
    renameBox.append(renameInput, saveBtn, cancelBtn);

    wrap.append(itemBtn, renameBox);

    itemBtn.addEventListener("click", () => {
      loadHistoryItem(item);
      document.querySelectorAll(".history-item-wrap").forEach((w) => w.classList.remove("active"));
      wrap.classList.add("active");
    });

    optionsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openChatOptionsMenu(e, item, wrap);
    });

    // Rename events
    const finishRename = async () => {
      const newTitle = renameInput.value.trim();
      if (!newTitle) {
        cancelRename();
        return;
      }
      if (newTitle === (item.title || item.question)) {
        cancelRename();
        return;
      }
      try {
        const resp = await fetch(`/api/assistant/history/${item.id}/rename/`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
          credentials: "same-origin",
          body: JSON.stringify({ title: newTitle }),
        });
        if (!resp.ok) throw new Error("Rename failed");
        const res = await resp.json();
        item.title = res.title;
        qSpan.textContent = res.title;
        cancelRename();
        showToast("Chat renamed");
      } catch (err) {
        showToast("Failed to rename chat");
        cancelRename();
      }
    };

    const cancelRename = () => {
      renameBox.hidden = true;
      itemBtn.hidden = false;
      wrap.classList.remove("renaming");
    };

    saveBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      finishRename();
    });

    cancelBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      cancelRename();
    });

    renameInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        finishRename();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelRename();
      }
    });

    list.append(wrap);
  });
}

function setMachine(machineId, machineName) {
  const hiddenInput = $("#machine-id");
  const label = $("#machine-selector-label");
  if (hiddenInput) hiddenInput.value = machineId;
  const targetOption = document.querySelector(`.askb-menu-option[data-machine-id="${machineId}"]`);
  const displayName = machineName || targetOption?.dataset?.machineName || machineId.replace(/^M-/, "");
  if (label) label.textContent = displayName;
  document.querySelectorAll(".askb-menu-option").forEach((opt) => {
    const isMatch = opt.dataset.machineId === machineId;
    opt.classList.toggle("selected", isMatch);
    opt.setAttribute("aria-checked", String(isMatch));
  });
}

function loadHistoryItem(item) {
  activeChatId = item.id;
  setMachine(item.machine_id);
  $("#conversation").replaceChildren();
  addMessage("user", item.question);
  addMessage(
    "assistant",
    item.answer,
    item.status === "INSUFFICIENT" ? "Insufficient evidence in the selected manuals." : "",
    item.citations || [],
    item.question
  );
  setEvidenceVisible(true);
  renderCitations(item.citations || [], item.question, item.answer);
}

async function loadHistory(query = "") {
  try {
    const response = await fetch(`/api/assistant/history/${query ? `?q=${encodeURIComponent(query)}` : ""}`, {
      credentials: "same-origin",
    });
    if (response.ok) {
      const data = await response.json();
      renderHistory(data.history || []);
    }
  } catch (err) {
    console.warn("Could not load history", err);
  }
}

/* Chat Options Menu Logic */
function openChatOptionsMenu(event, item, wrap) {
  closeChatOptionsMenu();
  activeMenuChat = item;
  activeMenuWrap = wrap;
  wrap.classList.add("menu-active");

  const menu = $("#chat-options-menu");
  const pinLabel = $("#menu-pin-label");
  if (pinLabel) {
    pinLabel.textContent = item.is_pinned ? "Unpin" : "Pin";
  }

  menu.hidden = false;
  const triggerRect = event.currentTarget.getBoundingClientRect();
  const menuWidth = 196;
  const menuHeight = menu.offsetHeight || 220;

  let left = triggerRect.right - menuWidth;
  if (left < 10) left = triggerRect.left;
  if (left + menuWidth > window.innerWidth - 10) left = window.innerWidth - menuWidth - 10;

  let top = triggerRect.bottom + 6;
  if (top + menuHeight > window.innerHeight - 10) {
    top = triggerRect.top - menuHeight - 6;
  }

  menu.style.left = `${Math.max(10, left)}px`;
  menu.style.top = `${Math.max(10, top)}px`;
}

function closeChatOptionsMenu() {
  const menu = $("#chat-options-menu");
  if (menu) menu.hidden = true;
  if (activeMenuWrap) {
    activeMenuWrap.classList.remove("menu-active");
    activeMenuWrap = null;
  }
}

// Menu item action handlers
document.querySelectorAll(".chat-menu-item").forEach((btn) => {
  btn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const action = btn.dataset.action;
    const item = activeMenuChat;
    const wrap = activeMenuWrap;
    closeChatOptionsMenu();
    if (!item) return;

    if (action === "rename") {
      if (!wrap) return;
      const itemBtn = wrap.querySelector(".history-item");
      const renameBox = wrap.querySelector(".history-rename-box");
      const renameInput = wrap.querySelector(".rename-input");
      if (itemBtn && renameBox && renameInput) {
        itemBtn.hidden = true;
        renameBox.hidden = false;
        wrap.classList.add("renaming");
        renameInput.value = item.title || item.question;
        renameInput.focus();
        renameInput.select();
      }
    } else if (action === "pin") {
      try {
        const resp = await fetch(`/api/assistant/history/${item.id}/pin/`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
          credentials: "same-origin",
        });
        if (resp.ok) {
          const res = await resp.json();
          item.is_pinned = res.is_pinned;
          showToast(item.is_pinned ? "Chat pinned" : "Chat unpinned");
          await loadHistory();
        }
      } catch (err) {
        showToast("Failed to pin chat");
      }
    } else if (action === "delete") {
      deleteTargetChat = item;
      const modal = $("#delete-modal-backdrop");
      const nameEl = $("#delete-chat-name");
      if (modal && nameEl) {
        nameEl.textContent = `"${(item.title || item.question).slice(0, 40)}"`;
        modal.hidden = false;
      }
    }
  });
});

// Delete Modal Confirmation
$("#delete-cancel-btn")?.addEventListener("click", () => {
  $("#delete-modal-backdrop").hidden = true;
  deleteTargetChat = null;
});

$("#delete-modal-backdrop")?.addEventListener("click", (e) => {
  if (e.target.id === "delete-modal-backdrop") {
    $("#delete-modal-backdrop").hidden = true;
    deleteTargetChat = null;
  }
});

$("#delete-confirm-btn")?.addEventListener("click", async () => {
  if (!deleteTargetChat) return;
  const item = deleteTargetChat;
  $("#delete-modal-backdrop").hidden = true;
  deleteTargetChat = null;
  try {
    const resp = await fetch(`/api/assistant/history/${item.id}/delete/`, {
      method: "DELETE",
      headers: { "X-CSRFToken": getCookie("csrftoken") },
      credentials: "same-origin",
    });
    if (resp.ok) {
      showToast("Chat deleted");
      if (activeChatId === item.id) {
        resetToNewChat();
      }
      await loadHistory();
    } else {
      showToast("Failed to delete chat");
    }
  } catch (err) {
    showToast("Error deleting chat");
  }
});

// Close context menu on outside click or escape
document.addEventListener("click", (e) => {
  if (!e.target.closest("#chat-options-menu") && !e.target.closest(".chat-options-trigger")) {
    closeChatOptionsMenu();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeChatOptionsMenu();
    const modal = $("#delete-modal-backdrop");
    if (modal && !modal.hidden) modal.hidden = true;
  }
});

/* Left Sidebar Open/Close Bar Logic (Instead of sliding) */
function toggleSidebar(forceState) {
  const shell = $("#app-shell");
  const isCurrentlyCollapsed = shell.classList.contains("sidebar-collapsed");
  const newState = forceState !== undefined ? forceState : !isCurrentlyCollapsed;
  shell.classList.toggle("sidebar-collapsed", newState);
  try {
    localStorage.setItem("mechora_sidebar_collapsed", String(newState));
  } catch (err) {}
}

$("#sidebar-close-btn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleSidebar(true);
});

// Collapsed rail button handlers (matches reference image interactions)
$("#rail-expand-logo")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleSidebar(false);
});

$("#rail-new-chat")?.addEventListener("click", (e) => {
  e.stopPropagation();
  resetToNewChat();
});

$("#rail-search-btn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleSidebar(false);
  setTimeout(() => $("#history-search")?.focus(), 150);
});

$("#rail-chats-btn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleSidebar(false);
});

$("#rail-manuals-btn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  const panel = $("#evidence-panel");
  setEvidenceVisible(panel.hidden);
});

$("#rail-user-avatar")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleSidebar(false);
});

// Keyboard shortcut Ctrl+B or Cmd+B to toggle sidebar
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && (e.key === "b" || e.key === "B")) {
    e.preventDefault();
    toggleSidebar();
  }
});

// Restore saved sidebar state
try {
  if (localStorage.getItem("mechora_sidebar_collapsed") === "true") {
    $("#app-shell")?.classList.add("sidebar-collapsed");
  }
} catch (err) {}

function renderCitations(sources, question = "", answer = "", autoSelect = true) {
  activeQuestion = question;
  activeAnswer = answer;
  const empty = $("#citation-empty");
  const container = $("#citations");
  container.replaceChildren();
  if (!sources.length) {
    empty.hidden = false;
    container.hidden = true;
    $("#pdf-viewer").hidden = true;
    return;
  }
  empty.hidden = true;
  container.hidden = false;
  sources.forEach((source, index) => {
    const card = document.createElement("article");
    card.className = "citation-card";
    card.innerHTML = '<div class="source-tag"></div><div class="source-title"></div><div class="source-meta"></div><div class="source-passage"></div><a class="source-open" target="_blank" rel="noopener">Open cited page ↗</a>';
    card.querySelector(".source-tag").textContent = `[${source.source_id || `S${index + 1}`}]`;
    card.querySelector(".source-title").textContent = source.document_name;
    card.querySelector(".source-meta").textContent = `Revision ${source.revision} · PDF page ${source.page_number}`;
    card.querySelector(".source-passage").textContent = source.passage;
    card.querySelector(".source-open").href = pdfUrlFor(source);
    card.addEventListener("click", () => selectCitation(source, card, question, answer));
    container.append(card);
    if (index === 0 && autoSelect) selectCitation(source, card, question, answer);
  });
}

async function selectCitation(source, card, question = activeQuestion, answer = activeAnswer) {
  activeSource = source;
  pdfZoom = 1;
  document.querySelectorAll(".citation-card").forEach((item) => item.classList.remove("selected"));
  card.classList.add("selected");
  $("#pdf-viewer").hidden = false;
  $("#viewer-title").textContent = source.document_name;
  $("#viewer-page").textContent = `Page ${source.page_number}`;
  $("#viewer-open").href = pdfUrlFor(source);
  const library = await getPdfJs();
  if (library) {
    try {
      await renderPdfPage(source, library, question, answer);
    } catch (error) {
      console.warn("PDF preview could not be rendered", error);
      $("#viewer-page").textContent = `Page ${source.page_number} · use Open PDF`;
    }
  }
}

async function renderPdfPage(source, library, question = "", answer = "") {
  const pdf = await library.getDocument({ url: pdfUrlFor(source).split("#")[0], withCredentials: true }).promise;
  const page = await pdf.getPage(Number(source.page_number));
  const stage = $(".pdf-stage");
  const pageRotation = ((Number(page.rotate) || 0) % 360 + 360) % 360;
  const correctionRotation = (360 - pageRotation) % 360;
  const unscaledViewport = page.getViewport({ scale: 1, rotation: correctionRotation });
  const availableWidth = Math.max(320, stage.clientWidth - 36);
  const fitScale = Math.min(1.35, Math.max(0.75, availableWidth / unscaledViewport.width));
  const scale = fitScale * pdfZoom;
  $("#pdf-zoom-level").textContent = `${Math.round(pdfZoom * 100)}%`;
  const viewport = page.getViewport({ scale, rotation: correctionRotation });
  const pageWrap = $("#pdf-page-wrap");
  const canvas = $("#pdf-canvas");
  pageWrap.style.width = `${viewport.width}px`;
  pageWrap.style.height = `${viewport.height}px`;
  // Render above CSS resolution so PDF text and tables stay sharp on HiDPI
  // displays. The text/highlight layer remains in CSS pixels and stays aligned.
  const outputScale = Math.min(window.devicePixelRatio || 1, 3);
  canvas.width = Math.ceil(viewport.width * outputScale);
  canvas.height = Math.ceil(viewport.height * outputScale);
  canvas.style.width = `${viewport.width}px`;
  canvas.style.height = `${viewport.height}px`;
  await page.render({
    canvasContext: canvas.getContext("2d"),
    viewport,
    transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0],
  }).promise;
  const textContent = await page.getTextContent();
  const layer = $("#pdf-text-layer");
  layer.replaceChildren();
  const normalize = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const items = textContent.items.map((item) => ({ item, text: normalize(item.str) })).filter((entry) => entry.text);
  let pageText = "";
  const ranges = items.map((entry) => {
    const start = pageText.length;
    pageText += `${entry.text} `;
    return { ...entry, start, end: pageText.length - 1 };
  });
  const findBestPhrase = (target, minimum = 5, maximum = 18) => {
    const words = normalize(target).split(/\s+/).filter((word) => word.length > 1);
    for (let size = Math.min(words.length, maximum); size >= minimum; size -= 1) {
      for (let index = 0; index + size <= words.length; index += 1) {
        const phrase = words.slice(index, index + size).join(" ");
        const start = pageText.indexOf(phrase);
        if (start >= 0) return { start, end: start + phrase.length };
      }
    }
    return { start: -1, end: -1 };
  };
  // Prefer the retrieved passage itself. The generated answer may paraphrase
  // the manual and can otherwise cause an unrelated phrase to be highlighted.
  const passageMatch = findBestPhrase(source.passage, 5, 18);
  const answerMatch = passageMatch.start < 0 ? findBestPhrase(answer, 5, 14) : { start: -1, end: -1 };
  const questionMatch = passageMatch.start < 0 && answerMatch.start < 0
    ? findBestPhrase(question, 5, 12)
    : { start: -1, end: -1 };
  const matchStart = passageMatch.start >= 0 ? passageMatch.start : (answerMatch.start >= 0 ? answerMatch.start : questionMatch.start);
  const matchEnd = passageMatch.start >= 0 ? passageMatch.end : (answerMatch.start >= 0 ? answerMatch.end : questionMatch.end);
  ranges.forEach(({ item, start, end }) => {
    const span = document.createElement("span");
    const transform = library.Util.transform(viewport.transform, item.transform);
    const fontHeight = Math.abs(transform[3]);
    span.textContent = item.str;
    span.style.left = `${transform[4]}px`;
    span.style.top = `${transform[5] - fontHeight}px`;
    span.style.fontSize = `${fontHeight}px`;
    span.style.fontFamily = item.fontName || "sans-serif";
    if (matchStart >= 0 && start < matchEnd && end > matchStart) span.classList.add("citation-highlight");
    layer.append(span);
  });
}

async function submitQuestion(event) {
  event.preventDefault();
  const machineId = $("#machine-id")?.value;
  const questionInput = $("#question");
  const question = questionInput?.value.trim() || "";
  if (!machineId || !question) return;

  const sendBtn = $("#send-button");
  const micBtn = $("#ask-mic-btn");

  // Prevent duplicate submissions while request is being processed
  if (questionInput) questionInput.disabled = true;
  if (sendBtn) sendBtn.disabled = true;
  if (micBtn) micBtn.disabled = true;

  addMessage("user", question);
  if (questionInput) {
    questionInput.value = "";
    updateComposerState();
  }

  showLoadingIndicator();

  try {
    const response = await fetch("/api/assistant/ask/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      credentials: "same-origin",
      body: JSON.stringify({ machine_id: machineId, question }),
    });
    const result = await response.json();
    hideLoadingIndicator();

    if (!response.ok) throw new Error(result.detail || "The assistant request failed.");

    addMessage(
      "assistant",
      result.answer,
      result.status === "INSUFFICIENT" ? "Insufficient evidence in the selected manuals." : "",
      result.sources || [],
      question,
      true
    );
    if (result.sources && result.sources.length) {
      setEvidenceVisible(true);
      renderCitations(result.sources, question, result.answer);
    }
    await loadHistory();
  } catch (error) {
    hideLoadingIndicator();
    addMessage(
      "assistant",
      error.message || "An error occurred while retrieving information from the manuals.",
      "Request failed"
    );
  } finally {
    if (questionInput) {
      questionInput.disabled = false;
      questionInput.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
    if (micBtn) micBtn.disabled = false;
    updateComposerState();
  }
}

function getCookie(name) {
  return document.cookie.split(";").map((v) => v.trim()).find((v) => v.startsWith(`${name}=`))?.split("=")[1] || "";
}

/* AskBar Composer State (Auto-grow, Mic vs Send, Machine Selector) */
const questionInput = $("#question");
const micBtn = $("#ask-mic-btn");
const sendBtn = $("#send-button");

function updateComposerState() {
  if (!questionInput) return;
  // Auto-resize textarea clamped between 24px and 180px
  questionInput.style.height = "auto";
  const newHeight = Math.min(180, Math.max(24, questionInput.scrollHeight));
  questionInput.style.height = `${newHeight}px`;

  // Toggle Mic vs Send button based on text length
  const hasText = questionInput.value.trim().length > 0;
  if (micBtn && sendBtn) {
    micBtn.hidden = hasText;
    sendBtn.hidden = !hasText;
  }
}

questionInput?.addEventListener("input", updateComposerState);
questionInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#ask-form")?.requestSubmit();
  }
});

// Mic button says "Coming soon" as requested
micBtn?.addEventListener("click", (e) => {
  e.preventDefault();
  showToast("Voice input is coming soon!");
});

// Machine selector dropdown
const machineBtn = $("#machine-selector-btn");
const machineMenu = $("#machine-dropdown-menu");

machineBtn?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (!machineMenu) return;
  const isHidden = machineMenu.hidden;
  machineMenu.hidden = !isHidden;
  machineBtn.setAttribute("aria-expanded", String(isHidden));
});

document.querySelectorAll(".askb-menu-option").forEach((opt) => {
  opt.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = opt.dataset.machineId;
    const name = opt.dataset.machineName;
    setMachine(id, name);
    if (machineMenu) machineMenu.hidden = true;
    machineBtn?.setAttribute("aria-expanded", "false");
  });
});

document.addEventListener("click", (e) => {
  if (machineMenu && !e.target.closest(".askb-machine-wrap")) {
    machineMenu.hidden = true;
    machineBtn?.setAttribute("aria-expanded", "false");
  }
});

$("#ask-form")?.addEventListener("submit", submitQuestion);
$("#new-chat")?.addEventListener("click", () => {
  resetToNewChat();
  updateComposerState();
});
$("#history-search")?.addEventListener("input", (event) => loadHistory(event.target.value));
document.querySelectorAll("[data-question]").forEach((button) =>
  button.addEventListener("click", () => {
    if (questionInput) {
      questionInput.value = button.dataset.question;
      updateComposerState();
      questionInput.focus();
    }
  })
);
loadHistory();
updateComposerState();

/* Resizable right evidence panel */
function makeResizable(handle, variable, getWidth) {
  if (!handle) return;
  let dragging = false;
  let frame = null;
  let pendingX = 0;
  const shell = $("#app-shell");
  const applyWidth = () => {
    frame = null;
    if (!dragging) return;
    shell.style.setProperty(variable, `${getWidth(pendingX)}px`);
  };
  const move = (event) => {
    if (!dragging) return;
    pendingX = event.clientX;
    if (frame === null) frame = requestAnimationFrame(applyWidth);
  };
  const stop = () => {
    dragging = false;
    handle.classList.remove("dragging");
    shell.classList.remove("is-resizing");
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
      shell.style.setProperty(variable, `${getWidth(pendingX)}px`);
    }
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", stop);
    document.removeEventListener("pointercancel", stop);
  };
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    dragging = true;
    pendingX = event.clientX;
    handle.classList.add("dragging");
    shell.classList.add("is-resizing");
    handle.setPointerCapture?.(event.pointerId);
    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerup", stop, { once: true });
    document.addEventListener("pointercancel", stop, { once: true });
  });
}

const rightPanelWidth = (x) => {
  const shell = $("#app-shell");
  const sidebarWidth = parseFloat(getComputedStyle(shell).getPropertyValue("--sidebar-w")) || 260;
  const maxWidth = Math.max(320, shell.clientWidth - sidebarWidth - 420);
  return Math.min(Math.max(shell.clientWidth - x, 320), maxWidth);
};
makeResizable($("#evidence-grip"), "--evidence-w", rightPanelWidth);

async function rerenderZoomedPdf() {
  if (!activeSource) return;
  const library = await getPdfJs();
  if (!library) return;
  try {
    await renderPdfPage(activeSource, library, activeQuestion, activeAnswer);
  } catch (error) {
    console.warn("PDF zoom could not be rendered", error);
  }
}

$("#pdf-zoom-out").addEventListener("click", () => {
  pdfZoom = Math.max(0.5, Number((pdfZoom - 0.1).toFixed(2)));
  rerenderZoomedPdf();
});
$("#pdf-zoom-in").addEventListener("click", () => {
  pdfZoom = Math.min(2.5, Number((pdfZoom + 0.1).toFixed(2)));
  rerenderZoomedPdf();
});
$("#pdf-zoom-reset").addEventListener("click", () => {
  pdfZoom = 1;
  rerenderZoomedPdf();
});
