const TELEGRAM_BOT_URL = "https://t.me/soiqweqq_bot";

const chatWindow = document.getElementById("chatWindow");
const chatHeader = document.getElementById("chatHeader");
const chatBody = document.getElementById("chatBody");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const floatingChat = document.querySelector(".floating-chat");
const emojiToggle = document.querySelector(".emoji-toggle");
const emojiPanel = document.getElementById("emojiPanel");
const statusText = document.querySelector(".status-text");
const statusDot = document.querySelector(".status-dot");
let idleStatusTimer = null;
let onlineStatusTimer = null;
let currentBotStatus = "offline";

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



function clearOnlineStatusTimer() {
  clearTimeout(onlineStatusTimer);
  onlineStatusTimer = null;
}

function scheduleOnlineStatus() {
  clearOnlineStatusTimer();
  const delay = 6000 + Math.random() * 4000;
  onlineStatusTimer = setTimeout(() => {
    if (currentBotStatus !== "dnd") {
      setBotStatus("online");
      resetAfkTimer();
    }
  }, delay);
}

function setBotStatus(status) {
  currentBotStatus = status;

  const labels = {
    online: "онлайн",
    offline: "не в сети",
    afk: "afk",
    dnd: "dnd"
  };

  if (statusText) statusText.textContent = labels[status] || status;

  if (statusDot) {
    statusDot.classList.remove("status-online", "status-offline", "status-afk", "status-dnd");
    statusDot.classList.add(`status-${status}`);
  }
}

function resetAfkTimer() {
  clearTimeout(idleStatusTimer);
  idleStatusTimer = setTimeout(() => {
    if (currentBotStatus !== "offline" && currentBotStatus !== "dnd") {
      setBotStatus("afk");
    }
  }, 180000);
}

function isFarewell(text) {
  return /(^|\s)(пока|спокойной|до свидания|бай|увидимся|я пошла|я ушла|отбой|ладно,? пока)(\s|$|[.!?])/i.test(text || "");
}

function looksLikeDnd(answer) {
  return /(не трогай|не беспокой|отстань|злюсь|раздраж|агрессив|устала|разбит|плохо|не хочу говорить|оставь меня|dnd)/i.test(answer || "");
}

function handleLocalStatusCommand(text) {
  const cmd = (text || "").trim().toLowerCase();
  if (!["/dnd", "/afk", "/online", "/offline"].includes(cmd)) return false;

  addMessage("user", text);

  if (cmd === "/dnd") {
    clearOnlineStatusTimer();
    setBotStatus("dnd");
    addMessage("bot", "режим dnd. не беспокоить. звучит почти как мечта, если не учитывать людей за стеной.");
  } else if (cmd === "/afk") {
    clearOnlineStatusTimer();
    setBotStatus("afk");
    addMessage("bot", "afk. отошла в цифровой угол делать вид, что меня здесь нет.");
  } else if (cmd === "/online") {
    clearOnlineStatusTimer();
    setBotStatus("online");
    addMessage("bot", "я здесь. сомнительное достижение, но ладно.");
    resetAfkTimer();
  } else if (cmd === "/offline") {
    clearOnlineStatusTimer();
    setBotStatus("offline");
    addMessage("bot", "не в сети. официальная версия. удобно, правда?");
  }

  return true;
}

setBotStatus("offline");

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
  if (handleLocalStatusCommand(text)) return;

  addMessage("user", text);
  scheduleOnlineStatus();

  const fetchPromise = fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message: text, session_id: sessionId}),
  });

  let typing = null;
  let typingTimer = null;
  const typingFrames = ["печатает.", "печатает..", "печатает...", "печатает.."]; 

  const startTyping = () => {
    typing = addMessage("bot", "печатает.", true);
    let typingIndex = 0;
    typingTimer = setInterval(() => {
      if (typing?.bubble) {
        typing.bubble.textContent = typingFrames[typingIndex % typingFrames.length];
        typingIndex++;
      }
    }, 420);
  };

  try {
    await sleep(900 + Math.random() * 2100);
    startTyping();

    if (Math.random() < 0.38) {
      await sleep(700 + Math.random() * 900);
      if (typingTimer) clearInterval(typingTimer);
      typing?.item?.remove();
      typing = null;
      await sleep(500 + Math.random() * 1200);
      startTyping();
    }

    const response = await fetchPromise;
    const data = await response.json();

    await sleep(data.typing_pause_ms || (700 + Math.random() * 1300));

    if (typingTimer) clearInterval(typingTimer);
    typing.item.classList.remove("typing");
    const answerText = data.answer || "я снова что-то сломала. неожиданно, правда.";
    await typeText(typing.bubble, answerText, data.typing_speed || 16);

    if (isFarewell(text)) {
      clearOnlineStatusTimer();
      setTimeout(() => setBotStatus("offline"), 900);
    } else if (looksLikeDnd(answerText)) {
      clearOnlineStatusTimer();
      setBotStatus("dnd");
    } else if (currentBotStatus === "online") {
      resetAfkTimer();
    }
  } catch (error) {
    if (typingTimer) clearInterval(typingTimer);
    if (!typing) typing = addMessage("bot", "", false);
    typing.item.classList.remove("typing");
    typing.bubble.textContent = "сайт не достучался до сервера. где-то опять умер провод.";
    clearOnlineStatusTimer();
    setBotStatus("offline");
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

makeDraggable(chatWindow, chatHeader);
makeResizable(chatWindow, document.querySelector(".chat-resize-handle"));

function createAshParticle() {
  const ashLayer = document.getElementById("ashLayer");
  const hero = document.querySelector(".hero");
  if (!ashLayer || !hero) return;

  const heroRect = hero.getBoundingClientRect();
  const particle = document.createElement("span");
  particle.className = "ash-particle";

  const startX = heroRect.width * 0.635 + (Math.random() * 10 - 5);
  const startY = heroRect.height * 0.235 + (Math.random() * 8 - 4);
  const driftX = -24 + Math.random() * 48;
  const driftY = 120 + Math.random() * 170;
  const size = 2 + Math.random() * 2.8;
  const duration = 3.8 + Math.random() * 3.1;

  particle.style.left = `${startX}px`;
  particle.style.top = `${startY}px`;
  particle.style.width = `${size}px`;
  particle.style.height = `${size}px`;
  particle.style.setProperty("--ash-x", `${driftX}px`);
  particle.style.setProperty("--ash-y", `${driftY}px`);
  particle.style.animationDuration = `${duration}s`;

  ashLayer.appendChild(particle);
  setTimeout(() => particle.remove(), duration * 1000 + 150);
}

function triggerSignalHit() {
  const hero = document.querySelector(".hero");
  if (!hero) return;

  hero.classList.add("signal-hit");
  setTimeout(() => hero.classList.remove("signal-hit"), 360);
}

function startSignalFX() {
  if (!document.querySelector(".hero")) return;

  const schedule = () => {
    const next = 6500 + Math.random() * 8500;
    setTimeout(() => {
      triggerSignalHit();
      if (Math.random() < 0.35) setTimeout(triggerSignalHit, 620 + Math.random() * 900);
      schedule();
    }, next);
  };

  schedule();
}


function initGarlandTouch() {
  const pendants = document.querySelectorAll(".pendant");
  if (!pendants.length) return;

  const swingClasses = ["swing-a", "swing-b", "swing-c", "swing-d"];

  pendants.forEach((pendant) => {
    let lock = false;
    pendant.addEventListener("pointerenter", () => {
      if (lock) return;
      lock = true;
      pendant.classList.remove("touched", ...swingClasses);
      void pendant.getBoundingClientRect();
      const swing = swingClasses[Math.floor(Math.random() * swingClasses.length)];
      pendant.classList.add("touched", swing);
      setTimeout(() => {
        pendant.classList.remove("touched", swing);
        lock = false;
      }, 2200);
    });
  });
}

function startAmbientFX() {
  if (!document.querySelector(".hero")) return;
  setInterval(() => {
    if (Math.random() > 0.28) createAshParticle();
  }, 1600);
}

initGarlandTouch();
startAmbientFX();
startSignalFX();

if (document.body.classList.contains("chat-page")) {
  floatingChat && (floatingChat.style.display = "none");
}

if (floatingChat && chatWindow && chatWindow.classList.contains("hidden")) {
  floatingChat.style.display = "block";
}
