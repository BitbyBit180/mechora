const $ = (selector) => document.querySelector(selector);
let pdfjsLib;
let activeQuestion = "";
let activeAnswer = "";
let activeSource = null;
let pdfZoom = 1;

function setEvidenceVisible(visible) {
  const shell = $("#app-shell");
  const panel = $("#evidence-panel");
  shell.classList.toggle("evidence-hidden", !visible);
  panel.hidden = !visible;
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

function addMessage(kind, text, status = "", sources = [], question = "") {
  const conversation = $("#conversation");
  $("#welcome")?.remove();
  const wrapper = document.createElement("div");
  wrapper.className = `message ${kind}`;
  const content = document.createElement("div");
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = kind === "user" ? "You" : "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;
  content.append(label, bubble);
  if (status) {
    const note = document.createElement("div");
    note.className = "status-note";
    note.textContent = status;
    content.append(note);
  }
  if (kind === "assistant" && sources.length) {
    const sourceRow = document.createElement("div");
    sourceRow.className = "message-sources";
    sources.forEach((source, index) => {
      const sourceButton = document.createElement("button");
      sourceButton.type = "button";
      sourceButton.className = "message-source";
      sourceButton.textContent = `[${source.source_id || `S${index + 1}`}] ${source.document_name} · p.${source.page_number}`;
      sourceButton.addEventListener("click", () => {
        setEvidenceVisible(true);
        renderCitations(sources, question, text, false);
        const cards = document.querySelectorAll(".citation-card");
        const card = cards[index];
        if (card) selectCitation(sources[index], card, question, text);
      });
      sourceRow.append(sourceButton);
    });
    content.append(sourceRow);
  }
  wrapper.append(content);
  conversation.append(wrapper);
  conversation.scrollTop = conversation.scrollHeight;
}

function renderHistory(items) {
  const list = $("#history-list");
  list.replaceChildren();
  if (!items.length) {
    list.innerHTML = '<div class="empty-history">Your questions will appear here.</div>';
    return;
  }
  items.forEach((item) => {
    const button = document.createElement("button");
    button.className = "history-item";
    button.type = "button";
    button.innerHTML = '<span class="history-question"></span><span class="history-meta"></span>';
    button.querySelector(".history-question").textContent = item.question;
    button.querySelector(".history-meta").textContent = `${item.machine_id} · ${item.status}`;
    button.addEventListener("click", () => loadHistoryItem(item));
    list.append(button);
  });
}

function loadHistoryItem(item) {
  $("#machine-id").value = item.machine_id;
  $("#conversation").replaceChildren();
  addMessage("user", item.question);
  addMessage("assistant", item.answer, item.status === "INSUFFICIENT" ? "Insufficient evidence in the selected manuals." : "", item.citations || [], item.question);
  setEvidenceVisible(true);
  renderCitations(item.citations || [], item.question, item.answer);
}

async function loadHistory(query = "") {
  const response = await fetch(`/api/assistant/history/${query ? `?q=${encodeURIComponent(query)}` : ""}`, { credentials: "same-origin" });
  if (response.ok) renderHistory((await response.json()).history);
}

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
  // Some supplied PDFs expose an inverted page rotation through PDF.js even
  // though their stored PDF metadata reports zero rotation. Cancel the
  // effective PDF.js rotation per page so every source renders upright.
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
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
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
  const findBestPhrase = (target) => {
    const words = normalize(target).split(/\s+/).filter((word) => word.length > 1);
    for (let size = Math.min(words.length, 14); size >= 3; size -= 1) {
      for (let index = 0; index + size <= words.length; index += 1) {
        const phrase = words.slice(index, index + size).join(" ");
        const start = pageText.indexOf(phrase);
        if (start >= 0) return { start, end: start + phrase.length };
      }
    }
    return { start: -1, end: -1 };
  };
  const answerMatch = findBestPhrase(answer);
  const questionMatch = answerMatch.start < 0 ? findBestPhrase(question) : { start: -1, end: -1 };
  const matchStart = answerMatch.start >= 0 ? answerMatch.start : questionMatch.start;
  const matchEnd = answerMatch.start >= 0 ? answerMatch.end : questionMatch.end;
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
  const machineId = $("#machine-id").value;
  const question = $("#question").value.trim();
  if (!machineId || !question) return;
  const button = $("#send-button");
  button.disabled = true;
  addMessage("user", question);
  $("#question").value = "";
  try {
    const response = await fetch("/api/assistant/ask/", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") }, credentials: "same-origin", body: JSON.stringify({ machine_id: machineId, question }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The assistant request failed.");
    addMessage("assistant", result.answer, result.status === "INSUFFICIENT" ? "Insufficient evidence in the selected manuals." : "", result.sources || [], question);
    setEvidenceVisible(true);
    renderCitations(result.sources || [], question, result.answer);
    await loadHistory();
  } catch (error) {
    addMessage("assistant", error.message, "Request failed");
  } finally {
    button.disabled = false;
  }
}

function getCookie(name) {
  return document.cookie.split(";").map((value) => value.trim()).find((value) => value.startsWith(`${name}=`))?.split("=")[1] || "";
}

$("#ask-form").addEventListener("submit", submitQuestion);
$("#new-chat").addEventListener("click", () => { $("#conversation").innerHTML = '<div id="welcome" class="welcome-card"><div class="welcome-icon">✦</div><h2>Ask about your machines</h2><p>Get grounded answers from the selected machine’s operation and maintenance manuals.</p></div>'; renderCitations([]); setEvidenceVisible(false); $("#question").focus(); });
$("#history-search").addEventListener("input", (event) => loadHistory(event.target.value));
document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => { $("#question").value = button.dataset.question; $("#question").focus(); }));
loadHistory();

function makeResizable(handle, variable, getWidth) {
  let dragging = false;
  const shell = $("#app-shell");
  const move = (event) => {
    if (!dragging) return;
    const width = getWidth(event.clientX);
    shell.style.setProperty(variable, `${width}px`);
  };
  const stop = () => {
    dragging = false;
    handle.classList.remove("dragging");
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", stop);
  };
  handle.addEventListener("pointerdown", (event) => {
    dragging = true;
    handle.classList.add("dragging");
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", stop, { once: true });
  });
}

makeResizable($("#left-resizer"), "--sidebar-width", (x) => Math.min(Math.max(x, 190), 380));
const rightPanelWidth = (x) => {
  const shell = $("#app-shell");
  const sidebarWidth = parseFloat(getComputedStyle(shell).getPropertyValue("--sidebar-width")) || 248;
  const maxWidth = Math.max(320, shell.clientWidth - sidebarWidth - 7 - 420);
  return Math.min(Math.max(shell.clientWidth - x, 320), maxWidth);
};
makeResizable($("#evidence-grip"), "--evidence-width", rightPanelWidth);

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
