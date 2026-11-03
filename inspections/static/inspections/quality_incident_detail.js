const actions = JSON.parse(document.getElementById("incident-actions-data")?.textContent || "[]");
const viewer = document.getElementById("incident-pdf-viewer");
let pdfjs;

function normalize(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function bestPhrase(target, pageText) {
  const words = normalize(target).split(/\s+/).filter((word) => word.length > 1);
  for (let size = Math.min(words.length, 18); size >= 5; size -= 1) {
    for (let index = 0; index + size <= words.length; index += 1) {
      const phrase = words.slice(index, index + size).join(" ");
      const start = pageText.indexOf(phrase);
      if (start >= 0) return { start, end: start + phrase.length };
    }
  }
  return { start: -1, end: -1 };
}

async function showIncidentCitation(index) {
  const source = actions[index];
  if (!source || !viewer) return;
  document.querySelectorAll(".citation-preview-button").forEach((button) => {
    button.classList.toggle("selected", Number(button.dataset.sourceIndex) === index);
  });
  const error = document.getElementById("incident-pdf-error");
  error.hidden = true;
  try {
    pdfjs ||= await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.mjs";
    const pdf = await pdfjs.getDocument({ url: source.source_link.split("#")[0], withCredentials: true }).promise;
    const page = await pdf.getPage(Number(source.page_number));
    const unscaledViewport = page.getViewport({ scale: 1 });
    const stage = document.querySelector(".incident-pdf-stage");
    const availableWidth = Math.max(420, (stage?.clientWidth || 900) - 48);
    const fitScale = Math.min(1.8, Math.max(0.85, availableWidth / unscaledViewport.width));
    const viewport = page.getViewport({ scale: fitScale });
    const canvas = document.getElementById("incident-pdf-canvas");
    const wrap = document.getElementById("incident-pdf-page-wrap");
    wrap.style.width = `${viewport.width}px`;
    wrap.style.height = `${viewport.height}px`;
    const outputScale = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.ceil(viewport.width * outputScale);
    canvas.height = Math.ceil(viewport.height * outputScale);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    await page.render({ canvasContext: canvas.getContext("2d"), viewport, transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0] }).promise;
    const content = await page.getTextContent();
    const layer = document.getElementById("incident-pdf-text-layer");
    layer.replaceChildren();
    const entries = content.items.map((item) => ({ item, text: normalize(item.str) })).filter((entry) => entry.text);
    let pageText = "";
    const ranges = entries.map((entry) => { const start = pageText.length; pageText += `${entry.text} `; return { ...entry, start, end: pageText.length - 1 }; });
    const match = bestPhrase(source.supporting_passage, pageText);
    ranges.forEach(({ item, start, end }) => {
      const span = document.createElement("span");
      const transform = pdfjs.Util.transform(viewport.transform, item.transform);
      const height = Math.abs(transform[3]);
      span.textContent = item.str;
      span.style.left = `${transform[4]}px`;
      span.style.top = `${transform[5] - height}px`;
      span.style.fontSize = `${height}px`;
      span.style.fontFamily = item.fontName || "sans-serif";
      if (match.start >= 0 && start < match.end && end > match.start) span.classList.add("incident-citation-highlight");
      layer.append(span);
    });
    document.getElementById("incident-pdf-title").textContent = `${source.source_document_id} · Revision ${source.revision}`;
    document.getElementById("incident-pdf-page").textContent = `PDF page ${source.page_number}`;
    document.getElementById("incident-pdf-open").href = source.source_link;
    viewer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (exception) {
    error.textContent = "PDF preview could not be rendered. Use the Open PDF link.";
    error.hidden = false;
  }
}

document.querySelectorAll(".citation-preview-button").forEach((button) => {
  button.addEventListener("click", () => showIncidentCitation(Number(button.dataset.sourceIndex)));
});

if (actions.length) showIncidentCitation(0);
