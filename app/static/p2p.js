(function () {
  const rtcHook = document.getElementById("rtc-hook");
  if (!rtcHook) return;

  const token = rtcHook.dataset.token;
  const selfId = rtcHook.dataset.deviceId;
  const stunUrl = rtcHook.dataset.stun;
  const panel = document.getElementById("p2p-panel");
  const fileInput = document.getElementById("p2p-file");
  const modal = document.getElementById("rtc-modal");
  const modalText = document.getElementById("rtc-modal-text");

  const CHUNK = 64 * 1024;
  const ACCEPT_TIMEOUT = 30000;
  const CONNECT_TIMEOUT = 20000;

  const peers = new Map(); // remote device_id -> peer
  let pendingOffer = null;
  let pendingTarget = null;

  function sendSignal(to, kind, data) {
    const form = new FormData();
    form.append("to", to);
    form.append("data", data);
    return fetch(`/rooms/${token}/rtc/${kind}`, { method: "POST", body: form });
  }

  function sendAccept(to, accept) {
    const form = new FormData();
    form.append("to", to);
    form.append("accept", accept ? "true" : "false");
    return fetch(`/rooms/${token}/rtc/accept`, { method: "POST", body: form });
  }

  // ---------- сигналы с сервера (sse-расширение шлёт события sse:rtc-*) ----------

  ["rtc-offer", "rtc-answer", "rtc-ice", "rtc-accept"].forEach((name) => {
    rtcHook.addEventListener(`sse:${name}`, (event) => {
      let msg;
      try {
        msg = JSON.parse(event.detail.data);
      } catch (err) {
        return;
      }
      handleSignal(name, msg);
    });
  });

  function handleSignal(name, msg) {
    if (name === "rtc-offer") {
      if (msg.from === selfId) return;
      showAcceptModal(msg);
    } else if (name === "rtc-answer") {
      const peer = peers.get(msg.from);
      if (!peer || peer.role !== "sender" || !peer.awaitingAnswer) return;
      peer.awaitingAnswer = false;
      peer.pc
        .setRemoteDescription({ type: "answer", sdp: msg.data })
        .catch(() => finishPeer(peer, "Ошибка соединения"));
    } else if (name === "rtc-ice") {
      const peer = peers.get(msg.from);
      if (!peer) return;
      try {
        peer.pc.addIceCandidate(JSON.parse(msg.data));
      } catch (err) {
        /* ignore */
      }
    } else if (name === "rtc-accept") {
      const peer = peers.get(msg.from);
      if (!peer || peer.role !== "sender") return;
      clearTimeout(peer.acceptTimer);
      if (msg.accept) {
        peer.status = "connecting";
        renderPanel();
      } else {
        finishPeer(peer, "Получатель отклонил");
      }
    }
  }

  // ---------- согласие получателя ----------

  function showAcceptModal(msg) {
    pendingOffer = msg;
    modalText.textContent = "Устройство хочет передать вам файл. Принять?";
    modal.classList.remove("hidden");
  }

  document.getElementById("rtc-accept").addEventListener("click", async () => {
    modal.classList.add("hidden");
    if (!pendingOffer) return;
    const from = pendingOffer.from;
    await sendAccept(from, true);
    pendingOffer = null;

    const peer = {
      pc: null,
      dc: null,
      role: "receiver",
      remote: from,
      status: "connecting",
      file: null,
      progress: 0,
      chunks: [],
      received: 0,
    };
    peers.set(from, peer);
    const pc = new RTCPeerConnection({ iceServers: [{ urls: stunUrl }] });
    peer.pc = pc;
    pc.ondatachannel = (e) => {
      peer.dc = e.channel;
      setupReceiverChannel(peer);
    };
    pc.onicecandidate = (e) => {
      if (e.candidate) sendSignal(from, "ice", JSON.stringify(e.candidate));
    };
    try {
      await pc.setRemoteDescription({ type: "offer", sdp: pendingOffer.data });
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      await sendSignal(from, "answer", pc.localDescription.sdp);
    } catch (err) {
      finishPeer(peer, "Ошибка соединения");
      return;
    }
    peer.openTimer = setTimeout(() => {
      if (!peer.dc || peer.dc.readyState !== "open") {
        finishPeer(peer, "Не удалось установить соединение");
      }
    }, CONNECT_TIMEOUT);
    renderPanel();
  });

  document.getElementById("rtc-decline").addEventListener("click", async () => {
    modal.classList.add("hidden");
    if (pendingOffer) await sendAccept(pendingOffer.from, false);
    pendingOffer = null;
  });

  // ---------- отправитель ----------

  function startTransfer(remoteId, file) {
    if (remoteId === selfId) return;
    if (peers.has(remoteId)) {
      showToast("Уже есть активная передача этому устройству");
      return;
    }
    const pc = new RTCPeerConnection({ iceServers: [{ urls: stunUrl }] });
    const dc = pc.createDataChannel("ghosthub");
    const peer = {
      pc,
      dc,
      role: "sender",
      remote: remoteId,
      status: "awaiting",
      file,
      progress: 0,
      awaitingAnswer: true,
    };
    peers.set(remoteId, peer);
    pc.onicecandidate = (e) => {
      if (e.candidate) sendSignal(remoteId, "ice", JSON.stringify(e.candidate));
    };
    dc.onopen = () => {
      peer.status = "sending";
      renderPanel();
      sendFile(peer);
    };
    dc.onclose = () => finishPeer(peer, "Соединение закрыто");
    dc.onerror = () => finishPeer(peer, "Ошибка соединения");
    pc.createOffer()
      .then((offer) => pc.setLocalDescription(offer))
      .then(() => sendSignal(remoteId, "offer", pc.localDescription.sdp))
      .catch(() => finishPeer(peer, "Не удалось начать передачу"));
    peer.acceptTimer = setTimeout(
      () => finishPeer(peer, "Устройство не ответило"),
      ACCEPT_TIMEOUT,
    );
    renderPanel();
  }

  function sendFile(peer) {
    const dc = peer.dc;
    const file = peer.file;
    dc.send(
      JSON.stringify({
        type: "meta",
        name: file.name,
        size: file.size,
        mime: file.type || "application/octet-stream",
      }),
    );
    let offset = 0;

    function next() {
      if (dc.bufferedAmount > 4 * CHUNK) {
        setTimeout(next, 50);
        return;
      }
      const slice = file.slice(offset, offset + CHUNK);
      const reader = new FileReader();
      reader.onload = () => {
        dc.send(reader.result);
        offset += CHUNK;
        peer.progress = file.size ? Math.round((offset / file.size) * 100) : 100;
        renderPanel();
        if (offset < file.size) {
          next();
        } else {
          dc.send(JSON.stringify({ type: "end" }));
          finishPeer(peer, "✓ Отправлено напрямую");
        }
      };
      reader.readAsArrayBuffer(slice);
    }

    next();
  }

  // ---------- получатель ----------

  function setupReceiverChannel(peer) {
    peer.dc.binaryType = "arraybuffer";
    peer.dc.onmessage = (e) => {
      if (typeof e.data === "string") {
        const msg = JSON.parse(e.data);
        if (msg.type === "meta") {
          peer.file = { name: msg.name, size: msg.size, mime: msg.mime };
          peer.chunks = [];
          peer.received = 0;
          renderPanel();
        } else if (msg.type === "end") {
          saveReceived(peer);
          finishPeer(peer, "✓ Получено, сохранение запущено");
        }
      } else {
        peer.chunks.push(e.data);
        peer.received += e.data.byteLength;
        peer.progress = peer.file
          ? Math.round((peer.received / peer.file.size) * 100)
          : 0;
        renderPanel();
      }
    };
  }

  function saveReceived(peer) {
    const blob = new Blob(peer.chunks, { type: peer.file.mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = peer.file.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  // ---------- fallback через сервер ----------

  function fallbackUpload(peer) {
    peer.status = "uploading";
    peer.message = "";
    renderPanel();
    const form = new FormData();
    form.append("content", "");
    form.append("file", peer.file, peer.file.name);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/rooms/${token}/messages`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        peer.progress = Math.round((e.loaded / e.total) * 100);
        renderPanel();
      }
    };
    xhr.onload = () =>
      finishPeer(
        peer,
        xhr.status === 204 ? "✓ Отправлено через сервер" : "Ошибка загрузки",
      );
    xhr.onerror = () => finishPeer(peer, "Сеть недоступна");
    xhr.send(form);
  }

  // ---------- общее ----------

  function finishPeer(peer, message) {
    clearTimeout(peer.acceptTimer);
    clearTimeout(peer.openTimer);
    try {
      peer.pc.close();
    } catch (e) {
      /* ignore */
    }
    try {
      peer.dc.close();
    } catch (e) {
      /* ignore */
    }
    peer.status = "closed";
    peer.message = message;
    renderPanel();
    setTimeout(() => {
      peers.delete(peer.remote);
      renderPanel();
    }, 6000);
  }

  function renderPanel() {
    if (!panel) return;
    panel.innerHTML = [...peers.values()].map(renderPeer).join("");
  }

  function renderPeer(peer) {
    const label = peer.file ? escapeHtml(peer.file.name) : peer.remote.slice(0, 6);
    const status = {
      awaiting: "ожидание согласия…",
      connecting: "установка соединения…",
      sending: "",
      receiving: "",
      uploading: "загрузка через сервер…",
      closed: peer.message || "завершено",
    }[peer.status] || peer.status;

    const bar =
      (peer.status === "sending" ||
        peer.status === "receiving" ||
        peer.status === "uploading") &&
      peer.file
        ? `<div class="p2p-bar"><div class="p2p-bar-fill" style="width:${peer.progress}%"></div></div>`
        : "";

    const fallback =
      peer.role === "sender" && peer.status !== "closed"
        ? `<button class="btn ghost p2p-fallback" type="button" data-fallback="${peer.remote}">Отправить через сервер</button>`
        : "";

    return `
      <div class="p2p-card ${peer.status}">
        <div class="p2p-row">
          <span class="p2p-label">${label}</span>
          ${status ? `<span class="p2p-status">${status}</span>` : ""}
        </div>
        ${bar}
        ${fallback}
      </div>`;
  }

  function showToast(message) {
    const toast = document.getElementById("toast");
    if (toast) toast.innerHTML = `<div class="toast-error">${escapeHtml(message)}</div>`;
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
  }

  // ---------- события ленты: клик/драг-н-дроп по устройству ----------

  const messagesEl = document.getElementById("messages");

  // скрываем кнопки передачи на собственных сообщениях
  // (серверный рендер уже без них, но sse-фрагменты общие для всех;
  // htmx:afterSwap при sse-свапе приходит без detail, поэтому без проверок)
  function hideOwnTargets(root) {
    root.querySelectorAll(".msg[data-device]").forEach((msg) => {
      if (msg.dataset.device !== selfId) return;
      msg.querySelectorAll("[data-send-to]").forEach((el) => el.classList.add("hidden"));
    });
  }
  hideOwnTargets(document);
  document.addEventListener("htmx:afterSwap", () => hideOwnTargets(document));

  messagesEl.addEventListener("click", (event) => {
    const target = event.target.closest("[data-send-to]");
    if (!target) return;
    pendingTarget = target.dataset.sendTo;
    fileInput.value = "";
    fileInput.click();
  });

  messagesEl.addEventListener("drop", (event) => {
    const target = event.target.closest("[data-send-to]");
    if (!target) return;
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length) startTransfer(target.dataset.sendTo, files[0]);
  });

  messagesEl.addEventListener("dragover", (event) => {
    if (event.target.closest("[data-send-to]")) {
      event.preventDefault();
    }
  });

  fileInput.addEventListener("change", () => {
    if (pendingTarget && fileInput.files.length) {
      startTransfer(pendingTarget, fileInput.files[0]);
    }
    fileInput.value = "";
    pendingTarget = null;
  });

  panel.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-fallback]");
    if (!btn) return;
    const peer = peers.get(btn.dataset.fallback);
    if (peer && peer.role === "sender" && peer.status !== "closed") {
      clearTimeout(peer.acceptTimer);
      clearTimeout(peer.openTimer);
      try {
        peer.pc.close();
      } catch (e) {
        /* ignore */
      }
      try {
        peer.dc.close();
      } catch (e) {
        /* ignore */
      }
      fallbackUpload(peer);
    }
  });
})();
