const chips = document.querySelectorAll(".chip");
const refreshBtn = document.getElementById("refresh-btn");
const shareSiteBtn = document.getElementById("share-site-btn");
const shareCopyBtn = document.getElementById("share-copy-btn");
const shareXBtn = document.getElementById("share-x-btn");
const shareLineBtn = document.getElementById("share-line-btn");
const shareUrlEl = document.getElementById("share-url");
const appConfig = window.APP_CONFIG || { baseUrl: window.location.origin, openArticleId: null, openArticle: null };

let currentArticleId = null;
let currentShareTitle = "";
const modal = document.getElementById("article-modal");
const modalLoading = document.getElementById("modal-loading");
const modalContent = document.getElementById("modal-content");
const modalImageWrap = document.getElementById("modal-image-wrap");
const modalImage = document.getElementById("modal-image");
const modalTitle = document.getElementById("modal-title");
const modalBody = document.getElementById("modal-body");
const modalBulletsPanel = document.getElementById("modal-bullets-panel");
const modalBullets = document.getElementById("modal-bullets");
const modalSource = document.getElementById("modal-source");
const modalDate = document.getElementById("modal-date");
const modalTitleOriginal = document.getElementById("modal-title-original");
const modalBodyOriginal = document.getElementById("modal-body-original");
const modalSourceLink = document.getElementById("modal-source-link");

function formatPublishedDate(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function parseArticlePreview(raw) {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try {
    return JSON.parse(raw);
  } catch (error) {
    return null;
  }
}

function buildPreviewPayload(preview) {
  const summaryJa = preview.summary_ja || "";
  const summaryOriginal = preview.summary_original || "";
  return {
    id: preview.id,
    title_ja: preview.title_ja || "",
    title_original: preview.title_original || "",
    summary_ja: summaryJa,
    body_ja: summaryJa,
    body_original: summaryOriginal,
    bullet_summary: [],
    source: preview.source || "",
    url: preview.url || "#",
    published_at: preview.published_at || "",
    image_url: preview.image_url || null,
    partial: true,
  };
}

function showPartialNotice() {
  if (modalBody.querySelector(".partial-notice")) return;
  modalBody.insertAdjacentHTML(
    "afterbegin",
    '<p class="partial-notice fade-line" style="--delay:0ms">通信状況により要約のみ表示しています。原文サイトで全文をご確認ください。</p>'
  );
}

function getSiteUrl() {
  return appConfig.baseUrl || window.location.origin;
}

function getArticleShareUrl(articleId) {
  return `${getSiteUrl()}/article/${encodeURIComponent(articleId)}`;
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function showShareFeedback(button, message) {
  if (!button) return;
  const original = button.textContent;
  button.textContent = message;
  setTimeout(() => {
    button.textContent = original;
  }, 1800);
}

function updateShareLinks(articleId, title) {
  const shareUrl = getArticleShareUrl(articleId);
  const encodedUrl = encodeURIComponent(shareUrl);
  const encodedText = encodeURIComponent(title);

  if (shareUrlEl) {
    shareUrlEl.textContent = shareUrl;
  }
  if (shareXBtn) {
    shareXBtn.href = `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedText}`;
  }
  if (shareLineBtn) {
    shareLineBtn.href = `https://social-plugins.line.me/lineit/share?url=${encodedUrl}`;
  }
}

function updateArticleUrl(articleId, replace = false) {
  const nextUrl = articleId ? getArticleShareUrl(articleId) : getSiteUrl();
  const state = { articleId: articleId || null };
  if (replace) {
    history.replaceState(state, "", nextUrl);
  } else {
    history.pushState(state, "", nextUrl);
  }
}

const filterRules = {
  all: () => true,
  ai: (text) => /ai|人工知能|artificial intelligence/i.test(text),
  "m&a": (text) => /merger|acquisition|m&a|買収|合併|takeover/i.test(text),
  ipo: (text) => /ipo|上場|goes public/i.test(text),
  regulation: (text) => /regulation|antitrust|規制|独占|tariff|関税/i.test(text),
  markets: (text) => /market|fed|interest rate|inflation|earnings|マーケット|金利|インフレ/i.test(text),
};

function applyFilter(filter) {
  const matcher = filterRules[filter] || filterRules.all;

  document.querySelectorAll(".news-card").forEach((card) => {
    const tags = card.dataset.tags || "";
    card.classList.toggle("hidden", !matcher(tags));
  });
}

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    chips.forEach((item) => item.classList.remove("active"));
    chip.classList.add("active");
    applyFilter(chip.dataset.filter);
  });
});

const LINE_DELAY_MS = 65;

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function splitIntoLines(text) {
  const lines = [];
  for (const paragraph of text.split(/\n{2,}/)) {
    const trimmed = paragraph.trim();
    if (!trimmed) continue;
    lines.push(...trimmed.split(/\n/).map((line) => line.trim()).filter(Boolean));
  }
  return lines;
}

function fadeLineHtml(content, index) {
  return `<p class="fade-line" style="--delay:${index * LINE_DELAY_MS}ms">${content}</p>`;
}

function formatBody(text, startIndex = 0) {
  return splitIntoLines(text)
    .map((line, offset) => fadeLineHtml(escapeHtml(line), startIndex + offset))
    .join("");
}

function setFadeElement(element, delayMs = 0) {
  element.classList.add("fade-line");
  element.style.setProperty("--delay", `${delayMs}ms`);
}

function resetFadeElements(root) {
  root.querySelectorAll(".fade-line").forEach((element) => {
    element.classList.remove("fade-line");
    element.style.removeProperty("--delay");
  });
}

function renderBullets(bullets, startIndex = 0) {
  if (!bullets || bullets.length === 0) {
    modalBullets.innerHTML = "";
    modalBulletsPanel.hidden = true;
    return startIndex;
  }

  const label = modalBulletsPanel.querySelector(".bullets-label");
  if (label) {
    setFadeElement(label, startIndex);
  }

  modalBullets.innerHTML = bullets
    .map((item, offset) => {
      const index = startIndex + 1 + offset;
      return `<li class="fade-line" style="--delay:${index * LINE_DELAY_MS}ms">${escapeHtml(item)}</li>`;
    })
    .join("");
  modalBulletsPanel.hidden = false;
  return startIndex + 1 + bullets.length;
}

function openModal() {
  modal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeModal({ updateUrl = true } = {}) {
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  modalContent.hidden = true;
  modalLoading.hidden = false;
  modalBulletsPanel.hidden = true;
  resetFadeElements(modalContent);
  modalTitle.classList.remove("fade-line");
  modalTitle.style.removeProperty("--delay");
  modalImageWrap.classList.remove("fade-line");
  modalImageWrap.style.removeProperty("--delay");
  currentArticleId = null;
  currentShareTitle = "";

  if (updateUrl && window.location.pathname.startsWith("/article/")) {
    updateArticleUrl(null);
  }
}

async function fetchArticleBody(articleId, { quick = false } = {}) {
  const query = quick ? "?quick=1" : "";
  const url = `/api/articles/${encodeURIComponent(articleId)}/body${query}`;
  let lastError = null;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), quick ? 15000 : 45000);

    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      lastError = error;
      if (attempt < 2) {
        await new Promise((resolve) => setTimeout(resolve, 1200 * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

function renderArticleModal(data, articleId, { updateUrl = true, showPartial = false } = {}) {
  let lineIndex = 0;

  setFadeElement(modalSource, lineIndex);
  setFadeElement(modalDate, lineIndex);
  modalSource.textContent = data.source || "";
  modalDate.textContent = formatPublishedDate(data.published_at);
  lineIndex += 1;

  if (data.image_url) {
    modalImage.src = data.image_url;
    modalImageWrap.hidden = false;
    setFadeElement(modalImageWrap, lineIndex);
    lineIndex += 1;
  } else {
    modalImage.removeAttribute("src");
    modalImageWrap.hidden = true;
  }

  modalTitle.textContent = data.title_ja || "";
  currentShareTitle = data.title_ja || "";
  setFadeElement(modalTitle, lineIndex);
  lineIndex += 1;

  lineIndex = renderBullets(data.bullet_summary, lineIndex);

  const bodyText = data.body_ja || data.summary_ja || "";
  modalBody.innerHTML = formatBody(bodyText, lineIndex);
  lineIndex += splitIntoLines(bodyText).length;

  modalTitleOriginal.textContent = data.title_original || "";
  modalBodyOriginal.innerHTML = formatBody(data.body_original || "", lineIndex);
  modalSourceLink.href = data.url || "#";
  updateShareLinks(articleId, data.title_ja || "");

  if (showPartial || data.partial) {
    showPartialNotice();
  }

  if (updateUrl) {
    updateArticleUrl(articleId);
  }

  modalLoading.hidden = true;
  modalContent.hidden = false;
}

async function openArticle(articleId, { updateUrl = true, preview = null } = {}) {
  openModal();
  modalLoading.hidden = false;
  modalContent.hidden = true;
  currentArticleId = articleId;

  const previewData = parseArticlePreview(preview) || parseArticlePreview(appConfig.openArticle);
  const hasPreview = Boolean(previewData && previewData.id === articleId);

  if (hasPreview) {
    renderArticleModal(buildPreviewPayload(previewData), articleId, { updateUrl, showPartial: true });
  }

  try {
    const data = await fetchArticleBody(articleId);
    renderArticleModal(data, articleId, {
      updateUrl: !hasPreview && updateUrl,
      showPartial: Boolean(data.partial),
    });
  } catch (error) {
    if (hasPreview) {
      showPartialNotice();
      return;
    }

    closeModal({ updateUrl: false });
    alert("記事の取得に失敗しました。もう一度お試しください。");
  }
}

document.querySelectorAll(".clickable-card[data-article-id]").forEach((element) => {
  element.addEventListener("click", (event) => {
    if (event.defaultPrevented) return;
    openArticle(element.dataset.articleId, { preview: element.dataset.article });
  });

  element.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openArticle(element.dataset.articleId, { preview: element.dataset.article });
    }
  });
});

document.querySelectorAll("[data-close-modal]").forEach((element) => {
  element.addEventListener("click", () => closeModal());
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !modal.hidden) {
    closeModal();
  }
});

window.addEventListener("popstate", (event) => {
  const articleId = event.state?.articleId;
  if (articleId) {
    const card = document.querySelector(`.clickable-card[data-article-id="${articleId}"]`);
    openArticle(articleId, {
      updateUrl: false,
      preview: card?.dataset.article || null,
    });
    return;
  }

  if (!modal.hidden) {
    closeModal({ updateUrl: false });
  }
});

shareSiteBtn?.addEventListener("click", async () => {
  try {
    await copyText(getSiteUrl());
    showShareFeedback(shareSiteBtn, "コピーしました");
  } catch (error) {
    alert("リンクのコピーに失敗しました。");
  }
});

shareCopyBtn?.addEventListener("click", async () => {
  if (!currentArticleId) return;

  try {
    await copyText(getArticleShareUrl(currentArticleId));
    showShareFeedback(shareCopyBtn, "コピーしました");
  } catch (error) {
    alert("リンクのコピーに失敗しました。");
  }
});

if (appConfig.openArticleId) {
  openArticle(appConfig.openArticleId, {
    updateUrl: false,
    preview: appConfig.openArticle,
  });
}

async function waitForNews() {
  const articleCount = Number(document.getElementById("article-count")?.textContent || "0");
  if (articleCount > 0) return;

  for (let attempt = 0; attempt < 30; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 4000));
    try {
      const response = await fetch("/api/news");
      if (!response.ok) continue;
      const data = await response.json();
      if (data.count > 0) {
        window.location.reload();
        return;
      }
    } catch (error) {
      // keep polling while cache warms in background
    }
  }
}

waitForNews();

refreshBtn?.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "更新中...";

  try {
    await fetch("/api/refresh", { method: "POST" });
    window.location.reload();
  } catch (error) {
    refreshBtn.textContent = "更新";
    refreshBtn.disabled = false;
    alert("更新に失敗しました。もう一度お試しください。");
  }
});
