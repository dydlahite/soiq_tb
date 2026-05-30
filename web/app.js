const TELEGRAM_BOT_URL = "https://t.me/soiqweqq_bot";

const chatWindow = document.getElementById("chatWindow");
const chatHeader = document.getElementById("chatHeader");
const chatBody = document.getElementById("chatBody");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const floatingChat = document.querySelector(".floating-chat");
const emojiToggle = document.querySelector(".emoji-toggle");
const emojiPanel = document.getElementById("emojiPanel");

const sessionId = (() => {
  const key = "soiqweqq_web_session";
  let value = localStorage.getItem(key);
  if (!value) {
    value = "web-" + Math.random().toString(16).slice(2) + "-" + Date.now();
    localStorage.setItem(key, value);
  }
  return value;
})();

document.querySelectorAll("[data-telegram-link]").forEach((el) => {
  el.href = TELEGRAM_BOT_URL;
});

function openChat() {
  if (chatWindow) {
    chatWindow.classList.remove("hidden");
    floatingChat && (floatingChat.style.display = "none");
    setTimeout(() => chatInput && chatInput.focus(), 50);
  }
}

function closeChat() {
  if (chatWindow) {
    chatWindow.classList.add("hidden");
    floatingChat && (floatingChat.style.display = "block");
  }
}

function minimizeChat() {
  closeChat();
}

document.querySelectorAll(".open-chat").forEach((button) => {
  button.addEventListener("click", openChat);
});

document.getElementById("closeChat")?.addEventListener("click", closeChat);
document.getElementById("minimizeChat")?.addEventListener("click", minimizeChat);
document.getElementById("openFullChat")?.addEventListener("click", () => window.open("/chat", "_blank"));

function addMessage(role, text, typing = false) {
  if (!chatBody) return null;

  const item = document.createElement("div");
  item.className = `message ${role}${typing ? " typing" : ""}`;

  const bubble = document.createElement("span");
  bubble.textContent = text || "";

  item.appendChild(bubble);
  chatBody.appendChild(item);
  chatBody.scrollTop = chatBody.scrollHeight;

  return { item, bubble };
}

function autoGrowTextarea(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 170) + "px";
}

chatInput?.addEventListener("input", () => autoGrowTextarea(chatInput));

emojiToggle?.addEventListener("click", () => {
  emojiPanel?.classList.toggle("hidden");
});

emojiPanel?.querySelectorAll("button").forEach((button) => {
  button.addEventListener("click", () => {
    if (!chatInput) return;
    const value = button.textContent || "";
    const start = chatInput.selectionStart || chatInput.value.length;
    const end = chatInput.selectionEnd || chatInput.value.length;
    chatInput.value = chatInput.value.slice(0, start) + value + chatInput.value.slice(end);
    chatInput.focus();
    const pos = start + value.length;
    chatInput.selectionStart = pos;
    chatInput.selectionEnd = pos;
    autoGrowTextarea(chatInput);
  });
});

document.addEventListener("click", (event) => {
  if (!emojiPanel || !emojiToggle) return;
  if (emojiPanel.contains(event.target) || emojiToggle.contains(event.target)) return;
  emojiPanel.classList.add("hidden");
});

chatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm?.requestSubmit();
  }
});

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function typeText(bubble, text, speed = 16) {
  bubble.textContent = "";
  const chunks = [...text];

  for (let i = 0; i < chunks.length; i++) {
    bubble.textContent += chunks[i];

    if (i % 3 === 0) {
      chatBody && (chatBody.scrollTop = chatBody.scrollHeight);
      await sleep(speed + Math.random() * 14);
    }
  }
}

async function sendMessage(text) {
  addMessage("user", text);

  const typing = addMessage("bot", "печатает.", true);
  const typingFrames = ["печатает.", "печатает..", "печатает...", "печатает.."];
  let typingIndex = 0;
  const typingTimer = setInterval(() => {
    if (typing?.bubble) {
      typing.bubble.textContent = typingFrames[typingIndex % typingFrames.length];
      typingIndex++;
    }
  }, 420);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text, session_id: sessionId}),
    });

    const data = await response.json();

    await sleep(data.delay_ms || 1200);

    clearInterval(typingTimer);
    typing.item.classList.remove("typing");
    await typeText(typing.bubble, data.answer || "я снова что-то сломала. неожиданно, правда.", data.typing_speed || 16);
  } catch (error) {
    clearInterval(typingTimer);
    typing.item.classList.remove("typing");
    typing.bubble.textContent = "сайт не достучался до сервера. где-то опять умер провод.";
  } finally {
    chatBody && (chatBody.scrollTop = chatBody.scrollHeight);
  }
}

chatForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = (chatInput?.value || "").trim();

  if (!text) return;

  chatInput.value = "";
  autoGrowTextarea(chatInput);
  await sendMessage(text);
});

function makeDraggable(box, handle) {
  if (!box || !handle) return;

  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  handle.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;

    const rect = box.getBoundingClientRect();

    dragging = true;
    startX = event.clientX;
    startY = event.clientY;
    startLeft = rect.left;
    startTop = rect.top;

    box.style.left = rect.left + "px";
    box.style.top = rect.top + "px";
    box.style.right = "auto";
    box.style.bottom = "auto";

    handle.setPointerCapture(event.pointerId);
  });

  handle.addEventListener("pointermove", (event) => {
    if (!dragging) return;

    const nextLeft = Math.min(Math.max(8, startLeft + event.clientX - startX), window.innerWidth - box.offsetWidth - 8);
    const nextTop = Math.min(Math.max(8, startTop + event.clientY - startY), window.innerHeight - box.offsetHeight - 8);

    box.style.left = nextLeft + "px";
    box.style.top = nextTop + "px";
  });

  handle.addEventListener("pointerup", (event) => {
    dragging = false;
    try { handle.releasePointerCapture(event.pointerId); } catch (_) {}
  });
}

makeDraggable(chatWindow, chatHeader);

function makeResizable(box, handle) {
  if (!box || !handle) return;

  let resizing = false;
  let startX = 0;
  let startY = 0;
  let startWidth = 0;
  let startHeight = 0;

  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    event.stopPropagation();

    const rect = box.getBoundingClientRect();

    resizing = true;
    startX = event.clientX;
    startY = event.clientY;
    startWidth = rect.width;
    startHeight = rect.height;

    box.style.left = rect.left + "px";
    box.style.top = rect.top + "px";
    box.style.right = "auto";
    box.style.bottom = "auto";

    handle.setPointerCapture(event.pointerId);
  });

  handle.addEventListener("pointermove", (event) => {
    if (!resizing) return;

    const minWidth = 340;
    const minHeight = 420;
    const maxWidth = window.innerWidth - 24;
    const maxHeight = window.innerHeight - 24;

    const nextWidth = Math.min(Math.max(minWidth, startWidth + event.clientX - startX), maxWidth);
    const nextHeight = Math.min(Math.max(minHeight, startHeight + event.clientY - startY), maxHeight);

    box.style.width = nextWidth + "px";
    box.style.height = nextHeight + "px";
  });

  handle.addEventListener("pointerup", (event) => {
    resizing = false;
    try { handle.releasePointerCapture(event.pointerId); } catch (_) {}
  });
}

makeResizable(chatWindow, document.querySelector(".chat-resize-handle"));


// На отдельной странице чата нет плавающего окна, но есть та же форма.
if (document.body.classList.contains("chat-page")) {
  floatingChat && (floatingChat.style.display = "none");
}

// Кнопка видна, если окно закрыли.
if (floatingChat && chatWindow && chatWindow.classList.contains("hidden")) {
  floatingChat.style.display = "block";
}
