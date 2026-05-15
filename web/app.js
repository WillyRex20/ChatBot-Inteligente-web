const API_BASE = "";
const STORAGE_KEY = "chatbot_rag_chats";

const chatForm = document.querySelector("#chatForm");
const questionInput = document.querySelector("#questionInput");
const chatMessages = document.querySelector("#chatMessages");
const fileInput = document.querySelector("#fileInput");
const uploadStatus = document.querySelector("#uploadStatus");
const apiStatus = document.querySelector("#apiStatus");
const sampleBtn = document.querySelector("#sampleBtn");
const screenshotBtn = document.querySelector("#screenshotBtn");
const linkBtn = document.querySelector("#linkBtn");
const voiceBtn = document.querySelector("#voiceBtn");
const alertOverlay = document.querySelector("#alertOverlay");
const alertMessage = document.querySelector("#alertMessage");
const alertClose = document.querySelector("#alertClose");
const chatList = document.querySelector("#chatList");
const newChatButton = document.querySelector("#newChatButton");
const activeChatTitle = document.querySelector("#activeChatTitle");

const MAX_UPLOAD_MB = 500;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const WELCOME_MESSAGE =
  "Hola. Soy tu asistente documental. Sube documentos o indexa la carpeta data/ y luego preguntame sobre el contenido.";

let chats = loadChats();
let activeChatId = chats[0].id;

function createChat(title = "Nuevo chat") {
  return {
    id: `chat_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    title,
    createdAt: Date.now(),
    messages: [{ role: "assistant", text: WELCOME_MESSAGE, sources: [] }],
  };
}

function loadChats() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (Array.isArray(saved) && saved.length) return saved;
  } catch (_error) {
    localStorage.removeItem(STORAGE_KEY);
  }
  return [createChat("Chat principal")];
}

function saveChats() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
}

function getActiveChat() {
  return chats.find((chat) => chat.id === activeChatId) || chats[0];
}

function setStatus(element, text, type = "neutral") {
  element.textContent = text;
  element.dataset.type = type;
}

function showAlert(message) {
  alertMessage.textContent = message;
  alertOverlay.hidden = false;
  alertClose.focus();
}

function hideAlert() {
  alertOverlay.hidden = true;
}

function addMessageToChat(role, text, sources = []) {
  const chat = getActiveChat();
  chat.messages.push({ role, text, sources });

  if (role === "user" && chat.title === "Nuevo chat") {
    chat.title = text.length > 34 ? `${text.slice(0, 34)}...` : text;
  }

  saveChats();
  renderChats();
  renderMessages();
}

function renderChats() {
  chatList.innerHTML = "";

  chats.forEach((chat, index) => {
    const chatContainer = document.createElement("div");
    chatContainer.className = "chat-tab-container";
    chatContainer.style.display = "flex";
    chatContainer.style.alignItems = "center";
    chatContainer.style.gap = "0.25rem";
    chatContainer.style.width = "100%";

    const button = document.createElement("button");
    button.type = "button";
    button.className = `chat-tab${chat.id === activeChatId ? " active" : ""}`;
    button.style.flex = "1";
    button.style.justifyContent = "flex-start";
    const title = document.createElement("span");
    title.textContent = chat.title || `Chat ${index + 1}`;
    const count = document.createElement("small");
    count.textContent = String(chat.messages.length);
    button.append(title, count);
    button.addEventListener("click", () => {
      activeChatId = chat.id;
      renderChats();
      renderMessages();
      questionInput.focus();
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "chat-delete-btn";
    deleteBtn.textContent = "×";
    deleteBtn.style.padding = "0.4rem 0.6rem";
    deleteBtn.style.minWidth = "2rem";
    deleteBtn.style.fontSize = "1.2rem";
    deleteBtn.style.borderRadius = "6px";
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (confirm(`¿Deseas eliminar "${chat.title}"? Esta acción no se puede deshacer.`)) {
        chats = chats.filter((c) => c.id !== chat.id);
        if (activeChatId === chat.id) {
          activeChatId = chats.length > 0 ? chats[0].id : null;
          if (!activeChatId) {
            chats = [createChat("Chat principal")];
            activeChatId = chats[0].id;
          }
        }
        saveChats();
        renderChats();
        renderMessages();
      }
    });

    chatContainer.append(button, deleteBtn);
    chatList.appendChild(chatContainer);
  });
}

function renderMessages() {
  const chat = getActiveChat();
  activeChatTitle.textContent = chat.title;
  chatMessages.innerHTML = "";
  chat.messages.forEach((message) => addMessageElement(message.role, message.text, message.sources || []));
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addMessageElement(role, text, sources = []) {
  const message = document.createElement("article");
  message.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  message.appendChild(bubble);

  // Las fuentes se procesan en backend pero no se muestran en frontend
  // if (sources.length) {
  //   const sourceList = document.createElement("div");
  //   sourceList.className = "sources";
  //   sourceList.textContent = sources
  //     .map((source) => {
  //       const name = source.source ? source.source.split(/[\\/]/).pop() : "Documento";
  //       return source.page !== null && source.page !== undefined ? `${name}, pagina ${source.page + 1}` : name;
  //     })
  //     .join(" | ");
  //   message.appendChild(sourceList);
  // }

  chatMessages.appendChild(message);
}

async function readApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `Error del servidor (${response.status}).`);
    }
    return data;
  }

  await response.text();
  if (response.status >= 500) {
    throw new Error(
      "El servidor tuvo un problema procesando el documento. Reinicia el servidor e intenta otra vez. Si el PDF es escaneado, primero debe pasar por OCR o convertirse a texto seleccionable."
    );
  }
  throw new Error("No se pudo completar la solicitud. Verifica que el servidor este encendido y vuelve a intentarlo.");
}

function validateSelectedFiles(files) {
  const allowed = [".pdf", ".txt", ".docx"];
  const totalSize = [...files].reduce((sum, file) => sum + file.size, 0);

  if (totalSize > MAX_UPLOAD_BYTES) {
    return `Los documentos pesan demasiado. El limite total por carga es ${MAX_UPLOAD_MB} MB. Reduce el tamano o sube menos archivos a la vez.`;
  }

  const invalidFile = [...files].find((file) => {
    const lowerName = file.name.toLowerCase();
    return !allowed.some((extension) => lowerName.endsWith(extension));
  });

  if (invalidFile) {
    return `El archivo "${invalidFile.name}" no es compatible. Solo se permiten PDF, TXT o DOCX.`;
  }

  return "";
}

async function checkApi() {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    if (!response.ok) throw new Error("API no disponible");
    const data = await readApiResponse(response);
    const mode = data.mode === "openai" ? "OpenAI" : "Local";
    setStatus(apiStatus, `API activa · ${mode}`, "success");
  } catch (_error) {
    setStatus(apiStatus, "API sin conexion", "error");
  }
}

alertClose.addEventListener("click", hideAlert);
alertOverlay.addEventListener("click", (event) => {
  if (event.target === alertOverlay) hideAlert();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !alertOverlay.hidden) hideAlert();
});

newChatButton.addEventListener("click", () => {
  const chat = createChat("Nuevo chat");
  chats.unshift(chat);
  activeChatId = chat.id;
  saveChats();
  renderChats();
  renderMessages();
  questionInput.focus();
});

fileInput.addEventListener("change", async (event) => {
  if (!fileInput.files.length) {
    const message = "Selecciona al menos un documento PDF, TXT o DOCX.";
    setStatus(uploadStatus, message, "error");
    showAlert(message);
    return;
  }

  const validationError = validateSelectedFiles(fileInput.files);
  if (validationError) {
    setStatus(uploadStatus, validationError, "error");
    showAlert(validationError);
    fileInput.value = "";
    return;
  }

  const formData = new FormData();
  [...fileInput.files].forEach((file) => formData.append("files", file));

  setStatus(uploadStatus, "Procesando documentos. Si el PDF es grande, puede tardar varios minutos...", "neutral");
  try {
    const response = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await readApiResponse(response);
    setStatus(uploadStatus, data.message, "success");
    addMessageToChat("assistant", `Listo. Se procesaron ${data.files.length} archivo(s). Ya puedes preguntar.`);
  } catch (error) {
    setStatus(uploadStatus, "No se pudo procesar el documento.", "error");
    showAlert(error.message);
  }
  fileInput.value = "";
});

sampleBtn.addEventListener("click", async () => {
  setStatus(uploadStatus, "Indexando documentos de data/...", "neutral");
  try {
    const response = await fetch(`${API_BASE}/api/index-sample`, { method: "POST" });
    const data = await readApiResponse(response);
    setStatus(uploadStatus, data.message, "success");
    addMessageToChat("assistant", `Se indexaron: ${data.files.join(", ")}.`);
  } catch (error) {
    setStatus(uploadStatus, "No se pudo indexar la carpeta data/.", "error");
    showAlert(error.message);
  }
});

screenshotBtn.addEventListener("click", async () => {
  try {
    if (navigator.screenshot) {
      const canvas = await navigator.screenshot.captureScreen();
      const blob = await new Promise((resolve) => canvas.toBlob(resolve));
      const file = new File([blob], `screenshot-${Date.now()}.png`, { type: "image/png" });
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      showAlert("Funcionalidad en desarrollo: captura de pantalla disponible próximamente.");
    }
  } catch (error) {
    showAlert("No se pudo capturar la pantalla. Intenta con el botón de subir archivos.");
  }
});

linkBtn.addEventListener("click", () => {
  const url = prompt("Ingresa la URL del documento o página web:");
  if (url) {
    addMessageToChat("user", `Compartir enlace: ${url}`);
    addMessageToChat("assistant", "Característica en desarrollo: pronto podrás compartir enlaces directamente.");
  }
});

voiceBtn.addEventListener("click", () => {
  if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
    showAlert("Tu navegador no soporta reconocimiento de voz.");
    return;
  }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.lang = "es-ES";
  recognition.start();
  voiceBtn.style.opacity = "0.5";
  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join("");
    questionInput.value = transcript;
    voiceBtn.style.opacity = "1";
  };
  recognition.onerror = (event) => {
    showAlert(`Error de reconocimiento: ${event.error}`);
    voiceBtn.style.opacity = "1";
  };
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  addMessageToChat("user", question);
  questionInput.value = "";
  questionInput.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: activeChatId }),
    });
    const data = await readApiResponse(response);
    addMessageToChat("assistant", data.answer, data.sources || []);
  } catch (error) {
    addMessageToChat("assistant", "No pude responder la pregunta en este momento.");
    showAlert(error.message);
  } finally {
    questionInput.disabled = false;
    questionInput.focus();
  }
});

renderChats();
renderMessages();
checkApi();
