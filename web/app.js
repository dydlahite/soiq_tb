const TELEGRAM_BOT_URL = "https://t.me/soiqweqq_bot";

document.querySelectorAll("[data-telegram-link]").forEach((el) => {
  el.href = TELEGRAM_BOT_URL;
});

const chatWindow = document.getElementById("chatWindow");
const chatHeader = document.getElementById("chatHeader");
const chatBody = document.getElementById("chatBody");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const closeChat = document.getElementById("closeChat");
const minimizeChat = document.getElementById("minimizeChat");
const maximizeChat = document.getElementById("maximizeChat");
const emojiToggle = document.querySelector(".emoji-toggle");
const emojiPanel = document.getElementById("emojiPanel");
const statusDot = document.querySelector(".status-dot");
const statusText = document.querySelector(".status-text");
const headerTyping = document.getElementById("headerTyping");
const trackTitle = document.getElementById("trackTitle");
const trackArtist = document.getElementById("trackArtist");
const trackProgress = document.getElementById("trackProgress");

let queue = [];
let sending = false;
let dragState = null;

const sessionId = (() => {
  const key = "soiqweqq_web_session";
  let value = localStorage.getItem(key);
  if (!value) {
    value = `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(key, value);
  }
  return value;
})();

function openChat() {
  chatWindow?.classList.remove("hidden");
  chatInput?.focus();
}

function closeChatWindow() {
  chatWindow?.classList.add("hidden");
  emojiPanel?.classList.add("hidden");
  setOffline();
  hideTyping();
}

function setOnline() {
  statusDot?.classList.add("status-online");
  statusDot?.classList.remove("status-offline");
  if (statusText) statusText.textContent = "онлайн";
}

function setOffline() {
  statusDot?.classList.remove("status-online");
  statusDot?.classList.add("status-offline");
  if (statusText) statusText.textContent = "не в сети";
}

function showTyping() {
  headerTyping?.classList.remove("hidden");
  setOnline();
}

function hideTyping() {
  headerTyping?.classList.add("hidden");
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

document.querySelectorAll(".open-chat").forEach((button) => {
  button.addEventListener("click", openChat);
});

closeChat?.addEventListener("click", closeChatWindow);
minimizeChat?.addEventListener("click", closeChatWindow);

maximizeChat?.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  if (!chatWindow) return;
  chatWindow.classList.toggle("maximized");
  chatWindow.style.left = "";
  chatWindow.style.right = "";
  chatWindow.style.top = "";
  chatWindow.style.bottom = "";
});

emojiToggle?.addEventListener("click", () => {
  emojiPanel?.classList.toggle("hidden");
});

emojiPanel?.querySelectorAll("button").forEach((button) => {
  button.addEventListener("click", () => {
    chatInput.value += button.textContent;
    chatInput.focus();
    resizeInput();
  });
});

function messageTime() {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Asia/Krasnoyarsk",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function normalizeInitialTimes() {
  document.querySelectorAll(".message-time").forEach((time) => {
    if (!time.textContent || time.textContent === "--:--") time.textContent = messageTime();
  });
}

function addMessage(text, role = "bot") {
  const item = document.createElement("div");
  item.className = `message ${role}`;

  const span = document.createElement("span");
  span.textContent = text;
  item.appendChild(span);

  const time = document.createElement("small");
  time.className = "message-time";
  time.textContent = messageTime();
  item.appendChild(time);

  chatBody.appendChild(item);
  chatBody.scrollTop = chatBody.scrollHeight;
}

async function processQueue() {
  if (sending || !queue.length) return;
  sending = true;

  while (queue.length) {
    const text = queue.shift();
    setOnline();
    await wait(500 + Math.random() * 700);
    showTyping();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          client_time: new Date().toISOString(),
        }),
      });

      const data = await response.json();
      await wait(data.pre_typing_delay_ms || 900);
      hideTyping();

      if (data?.ok) {
        const parts = String(data.answer || "")
          .split(/\n{2,}/)
          .map((x) => x.trim())
          .filter(Boolean)
          .slice(0, 4);

        for (const part of (parts.length ? parts : [data.answer])) {
          addMessage(part, "bot");
          await wait(350 + Math.random() * 550);
        }
        setOnline();
      } else {
        addMessage(data?.answer || "что-то пошло не так. мда.", "bot");
      }
    } catch (error) {
      hideTyping();
      addMessage("сайт опять подавился проводами. попробуй еще раз.", "bot");
    }
  }

  sending = false;
}

function sendMessage(text) {
  addMessage(text, "user");
  queue.push(text);
  processQueue();
}

chatForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const rawText = chatInput.value.replace(/\r\n/g, "\n");
  if (!rawText.trim()) return;
  chatInput.value = "";
  resizeInput();
  sendMessage(rawText);
});

function resizeInput() {
  if (!chatInput) return;
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 138)}px`;
}

chatInput?.addEventListener("input", resizeInput);

chatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm?.requestSubmit();
  }
});

async function loadTrackInfo() {
  try {
    const response = await fetch("/api/track", { cache: "no-store" });
    const data = await response.json();
    if (data?.ok) {
      if (trackTitle) trackTitle.textContent = data.title || "Неизвестно";
      if (trackArtist) trackArtist.textContent = data.artist || "Неизвестен";
      if (trackProgress) trackProgress.style.width = `${Math.max(0, Math.min(1, data.progress ?? .82)) * 100}%`;
    }
  } catch (_) {}
}

function enableChatDrag() {
  if (!chatWindow || !chatHeader || chatWindow.classList.contains("standalone")) return;

  chatHeader.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    if (window.matchMedia("(max-width: 820px)").matches) return;
    if (chatWindow.classList.contains("maximized")) return;

    const rect = chatWindow.getBoundingClientRect();
    dragState = {
      dx: event.clientX - rect.left,
      dy: event.clientY - rect.top,
      width: rect.width,
      height: rect.height,
    };
    chatHeader.setPointerCapture(event.pointerId);
    chatHeader.style.cursor = "grabbing";
  });

  chatHeader.addEventListener("pointermove", (event) => {
    if (!dragState) return;

    const maxLeft = window.innerWidth - dragState.width - 10;
    const maxTop = window.innerHeight - dragState.height - 10;
    const left = Math.max(10, Math.min(maxLeft, event.clientX - dragState.dx));
    const top = Math.max(10, Math.min(maxTop, event.clientY - dragState.dy));

    chatWindow.style.left = `${left}px`;
    chatWindow.style.top = `${top}px`;
    chatWindow.style.right = "auto";
    chatWindow.style.bottom = "auto";
  });

  const endDrag = () => {
    dragState = null;
    chatHeader.style.cursor = "grab";
  };

  chatHeader.addEventListener("pointerup", endDrag);
  chatHeader.addEventListener("pointercancel", endDrag);
}

loadTrackInfo();
setInterval(loadTrackInfo, 60000);
normalizeInitialTimes();
resizeInput();
enableChatDrag();
