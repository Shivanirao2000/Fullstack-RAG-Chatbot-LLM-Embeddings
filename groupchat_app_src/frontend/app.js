const $ = (id) => document.getElementById(id);

const authPanel = $("auth");
const chatPanel = $("chat");
const messagesDiv = $("messages");
const usernameInput = $("username");
const passwordInput = $("password");
const authMsg = $("authMsg");

const signupBtn = $("signupBtn");
const loginBtn = $("loginBtn");
const logoutBtn = $("logoutBtn");
const chatInput = $("chatInput");
const sendBtn = $("sendBtn");

const uploadForm = $("upload-form");
const uploadStatus = $("uploadStatus");

const API = location.origin + "/api";
let token = localStorage.getItem("token") || "";
let ws;

function showAuth() {
  authPanel.classList.remove("hidden");
  chatPanel.classList.add("hidden");
}

function showChat() {
  authPanel.classList.add("hidden");
  chatPanel.classList.remove("hidden");
}

async function callAPI(path, method, body) {
  const headers = {};
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API + path, {
    method,
    headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) throw new Error((await res.json()).detail || ("HTTP " + res.status));
  return res.json();
}

function addMessage(m) {
  const el = document.createElement("div");
  el.className = "message" + (m.is_bot ? " bot" : "");
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${m.username || "unknown"} • ${new Date(m.created_at).toLocaleString()}`;
  const body = document.createElement("div");
  body.textContent = m.content;
  el.appendChild(meta);
  el.appendChild(body);
  messagesDiv.appendChild(el);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function loadMessages() {
  const data = await callAPI("/messages");
  messagesDiv.innerHTML = "";
  for (const m of data.messages) addMessage(m);
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://10.25.103.54:8000/ws`);
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "message") addMessage(data.message);
    } catch (e) {}
  };
  ws.onclose = () => {
    setTimeout(connectWS, 2000);
  };
}

signupBtn.onclick = async () => {
  try {
    const out = await callAPI("/signup", "POST", {
      username: usernameInput.value.trim(),
      password: passwordInput.value
    });
    token = out.token;
    localStorage.setItem("token", token);
    await loadMessages();
    connectWS();
    showChat();
  } catch (e) {
    authMsg.textContent = e.message;
  }
};

loginBtn.onclick = async () => {
  try {
    const out = await callAPI("/login", "POST", {
      username: usernameInput.value.trim(),
      password: passwordInput.value
    });
    token = out.token;
    localStorage.setItem("token", token);
    await loadMessages();
    connectWS();
    showChat();
  } catch (e) {
    authMsg.textContent = e.message;
  }
};

logoutBtn.onclick = () => {
  token = "";
  localStorage.removeItem("token");
  showAuth();
};

// --- New: File Upload Handler ---
uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = document.getElementById("file").files;
  if (files.length === 0) {
    uploadStatus.innerText = "Please select at least one file.";
    return;
  }

  const formData = new FormData();
  for (const f of files) formData.append("files", f);

  try {
    const res = await callAPI("/upload", "POST", formData);
    uploadStatus.innerText = res.message;

    // Trigger embedding
    await callAPI("/process_embeddings", "POST");
  } catch (err) {
    console.error(err);
    uploadStatus.innerText = "Upload failed. Try again.";
  }
});

// --- New: Send message with PDF-aware LLM ---
sendBtn.onclick = async () => {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";

  await callAPI("/messages", "POST", { content: text });

  // If the message contains a question mark, ask the PDF LLM first
  if (text.includes("?")) {
    try {
      const res = await callAPI("/ask", "POST", new URLSearchParams({ question: text }));
      if (res.answer) {
        addMessage({
          username: "LLM Bot (Docs)",
          content: res.answer,
          is_bot: true,
          created_at: new Date().toISOString()
        });
      }
    } catch (e) {
      console.error("LLM Docs query failed:", e);
    }
  }
};

// Initialize
if (token) {
  loadMessages().then(()=>{
    connectWS();
    showChat();
  }).catch(()=>showAuth());
} else {
  showAuth();
}
