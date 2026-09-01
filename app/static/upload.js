(function () {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  const fileInput = document.getElementById("file-input");
  const queueEl = document.getElementById("upload-queue");
  const token = dropzone.dataset.token;

  let files = [];

  function addFiles(fileList) {
    for (const file of fileList) {
      files.push({ id: crypto.randomUUID(), file, status: "waiting", progress: 0 });
    }
    renderQueue();
    uploadNext();
  }

  function uploadNext() {
    const item = files.find((f) => f.status === "waiting");
    if (!item) return;
    item.status = "uploading";
    renderQueue();
    uploadItem(item).then(uploadNext);
  }

  function uploadItem(item) {
    return new Promise((resolve) => {
      const form = new FormData();
      form.append("content", "");
      form.append("file", item.file, item.file.name);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `/rooms/${token}/messages`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          item.progress = Math.round((e.loaded / e.total) * 100);
          renderQueue();
        }
      };
      xhr.onload = () => {
        if (xhr.status === 204) {
          item.status = "done";
          renderQueue();
          setTimeout(() => {
            files = files.filter((f) => f.id !== item.id);
            renderQueue();
          }, 1200);
        } else {
          item.status = "error";
          showToast(errorText(xhr));
          renderQueue();
          setTimeout(() => {
            files = files.filter((f) => f.id !== item.id);
            renderQueue();
          }, 6000);
        }
        resolve();
      };
      xhr.onerror = () => {
        item.status = "error";
        showToast("Сеть недоступна, попробуйте ещё раз");
        renderQueue();
        resolve();
      };
      xhr.send(form);
    });
  }

  function renderQueue() {
    queueEl.innerHTML = files
      .map((item) => {
        const status = { waiting: "в очереди", uploading: "…", done: "✓", error: "ошибка" }[item.status];
        const bar =
          item.status === "uploading"
            ? `<div class="upload-bar"><div class="upload-bar-fill" style="width:${item.progress}%"></div></div>`
            : "";
        return `
          <div class="upload-item ${item.status}">
            <div class="upload-row">
              <span class="upload-name">${escapeHtml(item.file.name)}</span>
              <span class="upload-size">${humanSize(item.file.size)}</span>
              <span class="upload-status">${status}</span>
            </div>
            ${bar}
          </div>`;
      })
      .join("");
  }

  function errorText(xhr) {
    try {
      const doc = new DOMParser().parseFromString(xhr.responseText, "text/html");
      const text = doc.body.textContent.trim();
      if (text) return text;
    } catch (e) {
      /* ignore */
    }
    return `Ошибка загрузки (${xhr.status})`;
  }

  function showToast(message) {
    const toast = document.getElementById("toast");
    if (toast) toast.innerHTML = `<div class="toast-error">${escapeHtml(message)}</div>`;
  }

  function humanSize(bytes) {
    const units = ["Б", "КБ", "МБ", "ГБ"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
  }

  fileInput.addEventListener("change", () => {
    addFiles(fileInput.files);
    fileInput.value = "";
  });

  dropzone.addEventListener("click", (event) => {
    if (event.target.closest("#pick-files")) fileInput.click();
  });

  ["dragover", "dragenter"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    }),
  );

  ["dragleave", "drop"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    }),
  );

  dropzone.addEventListener("drop", (event) => {
    addFiles(event.dataTransfer.files);
  });
})();
