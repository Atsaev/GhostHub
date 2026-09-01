// htmx: подменяем контент при ошибках лимитов (400/413)
htmx.config.responseHandling.unshift(
  { code: "400", swap: true },
  { code: "413", swap: true },
);

// перезагрузка страницы, когда комната истекла (sse-событие "expired")
document.addEventListener("htmx:sseMessage", (event) => {
  if (event.detail.type === "expired") {
    window.location.reload();
  }
});

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
