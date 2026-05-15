const API_BASE = "";
const STORAGE_KEY = "chatbot_rag_chats";
const USER_KEY = "chatbot_rag_user";

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

const MAX_UPLOAD_MB = 50;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const WELCOME_MESSAGE =
  "Hola. Soy tu asistente documental. Sube documentos o indexa la carpeta data/ y luego preguntame sobre el contenido.";

let currentUser = JSON.parse(localStorage.getItem(USER_KEY) || "null");

function initAuth() {
  if (!currentUser) {
    showLoginScreen();
  } else {
    initializeApp();
  }
}

function showLoginScreen() {
  const loginOverlay = document.createElement("div");
  loginOverlay.id = "authOverlay";
  loginOverlay.className = "auth-overlay";
  loginOverlay.innerHTML = `
    <div class="auth-card">
      <div class="brand-mark">AI</div>
      <h2>Bienvenido de nuevo</h2>
      <p>Inicia sesión para acceder a tu panel de documentos</p>
      <div class="auth-options">
        <button id="googleLogin" class="auth-btn google">
          <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
          Continuar con Google
        </button>
        <button id="guestLogin" class="auth-btn guest">Entrar como invitado</button>
      </div>
    </div>
  `;
  document.body.appendChild(loginOverlay);

  document.querySelector("#googleLogin").onclick = () => handleLogin("Google User", "google");
  document.querySelector("#guestLogin").onclick = () => handleLogin("Invitado", "guest");
}

function handleLogin(name, type) {
  currentUser = { name, type, id: Date.now() };
  localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
  document.querySelector("#authOverlay").remove();
  initializeApp();
}

function initializeApp() {
  renderChats();
  renderMessages();
  checkApi();
  console.log(`App iniciada para: ${currentUser.name}`);
}

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

    const button = document.createElement("button");
    button.type = "button";
    button.className = `chat-tab${chat.id === activeChatId ? " active" : ""}`;
    
    const title = document.createElement("span");
    title.textContent = chat.title || `Chat ${index + 1}`;
    const count = document.createElement("small");
    count.textContent = String(chat.messages.length);
    button.append(title, count);

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "chat-delete-btn";
    // Icono de basura (SVG)
    deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>`;
    
    button.addEventListener("click", () => {
      activeChatId = chat.id;
      renderChats();
      renderMessages();
      questionInput.focus();
    });

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

  if (sources && sources.length > 0) {
    const sourceList = document.createElement("div");
    sourceList.className = "sources-list";
    sourceList.style.fontSize = "0.75rem";
    sourceList.style.marginTop = "0.5rem";
    sourceList.style.color = "var(--text-tertiary)";
    
    const sourceText = sources.map(s => {
      const pageInfo = s.page !== null ? ` (Pág. ${s.page + 1})` : "";
      return `📄 ${s.source}${pageInfo}`;
    }).join(" | ");
    
    sourceList.textContent = "Fuentes: " + sourceText;
    bubble.appendChild(sourceList);
  }

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

  const errorText = await response.text();
  if (response.status >= 500) {
    console.error("Error del servidor:", errorText);
    if (errorText.includes("Timeout") || response.status === 504) {
      throw new Error("El servidor tardó demasiado. Intenta con un archivo más pequeño o revisa la capacidad de tu hosting.");
    }
    throw new Error(
      `Error ${response.status}: El servidor tuvo un problema interno. Verifica que el equipo tenga suficiente memoria RAM para cargar los modelos de IA.`
    );
  }
  throw new Error(`Error ${response.status}: No se pudo completar la solicitud. Verifica la conexión con el servidor.`);
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
    // Usar la API estándar de captura de pantalla (Screen Capture API)
    const stream = await navigator.mediaDevices.getDisplayMedia({ preferCurrentTab: true });
    const video = document.createElement('video');
    video.srcObject = stream;
    await video.play();
    
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    stream.getTracks().forEach(track => track.stop());
    showAlert("Captura realizada con éxito. Ahora puedes subirla si deseas analizar visualmente el contenido.");
  } catch (error) {
    console.error(error);
    showAlert("No se pudo completar la captura de pantalla o el permiso fue denegado.");
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

initAuth();
