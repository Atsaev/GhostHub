// htmx: подменяем контент при ошибках лимитов (400/413)
htmx.config.responseHandling.unshift(
  { code: "400", swap: true },
  { code: "413", swap: true },
);

// markdown-рендер текстовых сообщений (без raw-html — защита от XSS)
const md = window.markdownit
  ? window.markdownit({
      html: false,
      linkify: true,
      breaks: true,
      highlight(code, lang) {
        if (lang && window.hljs && hljs.getLanguage(lang)) {
          try {
            return hljs.highlight(code, { language: lang }).value;
          } catch (e) {
            /* fallback */
          }
        }
        return "";
      },
    })
  : null;

function renderMarkdown(root) {
  if (!md) return;
  root.querySelectorAll(".msg-text.md").forEach((el) => {
    if (el.dataset.mdRendered) return;
    el.innerHTML = md.render(el.textContent);
    el.dataset.mdRendered = "1";
  });
}

document.addEventListener("DOMContentLoaded", () => renderMarkdown(document));
document.addEventListener("htmx:afterSwap", (event) => renderMarkdown(event.detail.target || document));

// копирование ссылки и показ qr-панели
document.addEventListener("click", (event) => {
  const copyBtn = event.target.closest("[data-copy]");
  if (copyBtn) {
    navigator.clipboard.writeText(copyBtn.dataset.copy);
    const label = copyBtn.dataset.label || copyBtn.textContent;
    copyBtn.textContent = "Скопировано ✓";
    setTimeout(() => { copyBtn.textContent = label; }, 1500);
    return;
  }
  const qrBtn = event.target.closest("[data-toggle-qr]");
  if (qrBtn) {
    const panel = document.getElementById("qr-panel");
    if (panel) panel.classList.toggle("hidden");
  }
});

// автоскрытие toast с ошибкой
const toast = document.getElementById("toast");
if (toast) {
  new MutationObserver(() => {
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => { toast.innerHTML = ""; }, 4000);
  }).observe(toast, { childList: true });
}
