const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  token: localStorage.getItem("zhilan_token") || "",
  user: null,
  documents: [],
  files: [],
  users: [],
  conversations: [],
  activeConversationId: null,
  chatMessages: [],
  modelCatalog: { providers: [] },
  prompts: [],
  activeAbortController: null,
  pendingChatMessage: "",
  citations: {},
  adminProviders: [],
  authMode: "login",
};

const pageNames = {
  overview: "概览", chat: "AI 对话", search: "知识检索", documents: "文档管理",
  files: "文件中心", prompts: "Prompt 管理", models: "模型管理",
  users: "用户管理", profile: "个人设置",
};

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[char]));
}

function toast(message, type = "success") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  $("#toastRegion").append(item);
  setTimeout(() => item.remove(), 3600);
}

function errorMessage(error) {
  if (typeof error?.detail === "string") return error.detail;
  if (typeof error?.detail?.message === "string") return error.detail.message;
  if (Array.isArray(error?.detail)) return error.detail.map(item => item.msg).join("；");
  return error?.message || "操作失败，请稍后重试";
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && state.token && !path.endsWith("/login")) {
    logout(false);
    toast("登录状态已失效，请重新登录", "error");
    throw { detail: "登录状态已失效" };
  }
  if (!response.ok) {
    let payload = {};
    try { payload = await response.json(); } catch { payload = { detail: `请求失败 (${response.status})` }; }
    throw payload;
  }
  if (response.status === 204) return null;
  return response.json();
}

function setButtonLoading(button, loading, text = "处理中…") {
  if (loading) {
    button.dataset.label = button.innerHTML;
    button.disabled = true;
    button.textContent = text;
  } else {
    button.disabled = false;
    if (button.dataset.label) button.innerHTML = button.dataset.label;
  }
}

function initials(name) {
  return (name || "用户").trim().slice(0, 1).toUpperCase();
}

function roleText(role) { return role === "admin" ? "管理员" : "普通成员"; }
function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}
function formatBytes(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function setAuthMode(mode) {
  state.authMode = mode;
  const register = mode === "register";
  $("#loginTab").classList.toggle("active", !register);
  $("#registerTab").classList.toggle("active", register);
  $$(".register-only").forEach(el => el.classList.toggle("hidden", !register));
  $("#fullName").required = register;
  $("#authTitle").textContent = register ? "创建账户" : "欢迎回来";
  $("#authSubtitle").textContent = register ? "加入团队，开启高效知识协作" : "登录后继续探索你的企业知识库";
  $("#authSubmit span").textContent = register ? "注册账户" : "登录";
  $("#authHint").innerHTML = register
    ? '已有账号？<button type="button" data-switch-auth="login">返回登录</button>'
    : '还没有账号？<button type="button" data-switch-auth="register">立即注册</button>';
  $("#password").autocomplete = register ? "new-password" : "current-password";
}

async function handleAuth(event) {
  event.preventDefault();
  const button = $("#authSubmit");
  const email = $("#email").value.trim();
  const password = $("#password").value;
  if (!email || password.length < 8 || (state.authMode === "register" && !$("#fullName").value.trim())) {
    toast("请完整填写信息，密码至少 8 位", "error");
    return;
  }
  setButtonLoading(button, true, state.authMode === "register" ? "正在创建…" : "正在登录…");
  try {
    if (state.authMode === "register") {
      await api("/auth/register", { method: "POST", body: JSON.stringify({ email, password, full_name: $("#fullName").value.trim() }) });
      toast("注册成功，正在为你登录");
    }
    const result = await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    state.token = result.access_token;
    state.user = result.user;
    localStorage.setItem("zhilan_token", state.token);
    enterApp();
  } catch (error) { toast(errorMessage(error), "error"); }
  finally { setButtonLoading(button, false); }
}

function logout(showToast = true) {
  state.token = "";
  state.user = null;
  localStorage.removeItem("zhilan_token");
  $("#appView").classList.add("hidden");
  $("#authView").classList.remove("hidden");
  $("#authForm").reset();
  setAuthMode("login");
  if (showToast) toast("已安全退出登录");
}

function applyUser() {
  const user = state.user;
  const firstName = (user.full_name || "朋友").trim().split(/\s+/)[0];
  $("#welcomeName").textContent = firstName;
  ["#sideName", "#topName", "#profileName"].forEach(id => $(id).textContent = user.full_name);
  ["#sideAvatar", "#topAvatar", "#profileAvatar"].forEach(id => $(id).textContent = initials(user.full_name));
  $("#sideRole").textContent = roleText(user.role);
  $("#profileRole").textContent = roleText(user.role);
  $("#profileRole").className = `role-badge ${user.role}`;
  $("#profileEmail").textContent = user.email;
  $("#profileEmailInput").value = user.email;
  $("#profileNameInput").value = user.full_name;
  $("#usersNav").classList.toggle("hidden", user.role !== "admin");
  $("#promptsNav").classList.toggle("hidden", user.role !== "admin");
  $("#modelsNav").classList.toggle("hidden", user.role !== "admin");
  const hour = new Date().getHours();
  $("#greeting").textContent = hour < 6 ? "夜深了" : hour < 11 ? "上午好" : hour < 14 ? "中午好" : hour < 19 ? "下午好" : "晚上好";
  $("#todayText").textContent = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());
}

function enterApp() {
  $("#authView").classList.add("hidden");
  $("#appView").classList.remove("hidden");
  applyUser();
  const requested = location.hash.slice(1);
  navigate(pageNames[requested] && !(requested === "users" && state.user.role !== "admin") ? requested : "overview");
  loadOverview();
}

function navigate(page) {
  if (["users", "prompts", "models"].includes(page) && state.user?.role !== "admin") page = "overview";
  $$(".page").forEach(el => el.classList.toggle("active", el.id === `page-${page}`));
  $$(".nav-item[data-page]").forEach(el => el.classList.toggle("active", el.dataset.page === page));
  $("#breadcrumbCurrent").textContent = pageNames[page];
  history.replaceState(null, "", `#${page}`);
  $("#sidebar").classList.remove("open");
  if (page === "documents") loadDocuments();
  if (page === "chat") loadChatWorkspace();
  if (page === "prompts") loadPromptAdmin();
  if (page === "models") loadModelAdmin();
  if (page === "files") loadFiles();
  if (page === "users") loadUsers();
  if (page === "profile") applyUser();
}

async function loadOverview() {
  const jobs = [
    api("/docs/list").then(data => { state.documents = data; renderRecentDocuments(); $("#documentCount").textContent = data.length; }),
    api("/files").then(data => { state.files = data; $("#fileCount").textContent = data.length; }),
  ];
  if (state.user.role === "admin") jobs.push(api("/users").then(data => {
    state.users = data; $("#userCount").textContent = data.length; $("#userCountHint").textContent = "团队账户";
  }));
  else $("#userCount").textContent = "1";
  await Promise.allSettled(jobs);
}

function renderRecentDocuments() {
  const root = $("#recentDocuments");
  const items = state.documents.slice(-4).reverse();
  if (!items.length) { root.innerHTML = '<div class="empty-state" style="padding:25px"><p>暂无知识文档</p></div>'; return; }
  root.innerHTML = items.map(doc => `<div class="mini-doc"><span>▤</span><div><b>${escapeHtml(doc.name)}</b><small>${doc.chunk_count} 个索引片段</small></div></div>`).join("");
}

async function doSearch(query) {
  query = query.trim();
  if (!query) return;
  $("#searchQuery").value = query;
  $("#searchEmpty").classList.add("hidden");
  $("#searchResults").classList.add("hidden");
  $("#searchLoading").classList.remove("hidden");
  try {
    const data = await api("/query/search", { method: "POST", body: JSON.stringify({ query, top_k: Number($("#topK").value) }) });
    $("#answerText").textContent = data.answer || "没有找到能够回答该问题的内容。";
    $("#resultCount").textContent = `${data.results.length} 条结果`;
    $("#resultList").innerHTML = data.results.map((item, index) => `<article class="result-item"><div class="result-top"><span class="result-source">${index + 1}. ${escapeHtml(item.source)}</span><span class="score">相关度 ${Math.round(item.score * 100)}%</span></div><p>${escapeHtml(item.text)}</p></article>`).join("");
    $("#searchResults").classList.remove("hidden");
  } catch (error) {
    toast(errorMessage(error), "error");
    $("#searchEmpty").classList.remove("hidden");
  } finally { $("#searchLoading").classList.add("hidden"); }
}

async function loadChatWorkspace() {
  try {
    const [catalog, prompts, conversations] = await Promise.all([
      api("/ai/models"), api("/prompts"), api("/conversations"),
    ]);
    state.modelCatalog = catalog; state.prompts = prompts; state.conversations = conversations;
    renderModelSelectors(); renderPromptSelector(); renderConversationList();
    if (state.pendingChatMessage) {
      const message = state.pendingChatMessage; state.pendingChatMessage = "";
      $("#chatInput").value = message; sendChatMessage();
    }
  } catch (error) { toast(errorMessage(error), "error"); }
}

function renderModelSelectors() {
  const providers = state.modelCatalog.providers || [];
  const providerSelect = $("#providerSelect");
  providerSelect.innerHTML = providers.length
    ? providers.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")
    : '<option value="">尚未配置</option>';
  providerSelect.value = state.modelCatalog.default_provider_id || providers[0]?.id || "";
  renderModelOptions();
  const usable = Boolean(providers.length);
  $("#chatInput").disabled = !usable; $("#sendChat").disabled = !usable;
  if (!usable) $("#chatStatus").textContent = state.user?.role === "admin" ? "请先到模型管理配置平台与模型" : "管理员尚未配置可用模型";
}

function renderModelOptions() {
  const provider = state.modelCatalog.providers?.find(item => item.id === $("#providerSelect").value);
  $("#modelSelect").innerHTML = (provider?.models || []).map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
  const preferred = provider?.models.find(item => item.is_default) || provider?.models[0];
  if (preferred) $("#modelSelect").value = preferred.id;
}

function renderPromptSelector() {
  $("#promptSelect").innerHTML = state.prompts.filter(item => item.status === "published").map(item => `<option value="${item.id}">${escapeHtml(item.name)} · v${item.version}</option>`).join("");
  const preferred = state.prompts.find(item => item.is_default && item.status === "published");
  if (preferred) $("#promptSelect").value = preferred.id;
}

function renderConversationList() {
  const term = $("#conversationFilter").value.trim().toLowerCase();
  const items = state.conversations.filter(item => item.title.toLowerCase().includes(term));
  $("#conversationList").innerHTML = items.length ? items.map(item => `<button class="conversation-item ${item.id === state.activeConversationId ? "active" : ""}" data-conversation-id="${item.id}"><span>${escapeHtml(item.title)}</span><i data-delete-conversation="${item.id}" title="删除">×</i></button>`).join("") : '<p class="muted" style="padding:12px">暂无历史对话</p>';
}

function newConversation() {
  state.activeConversationId = null; state.chatMessages = []; state.citations = {};
  $("#chatTitle").textContent = "新对话";
  $("#chatStatus").textContent = "AI 会先检索企业知识，再回答你的问题";
  renderChatMessages(); renderConversationList(); $("#chatInput").focus();
}

async function openConversation(id) {
  try {
    const conversation = await api(`/conversations/${encodeURIComponent(id)}`);
    state.activeConversationId = id; state.chatMessages = conversation.messages;
    $("#chatTitle").textContent = conversation.title;
    if (conversation.provider_id) $("#providerSelect").value = conversation.provider_id;
    renderModelOptions();
    if (conversation.model_id) $("#modelSelect").value = conversation.model_id;
    if (conversation.prompt_id) $("#promptSelect").value = conversation.prompt_id;
    renderChatMessages(); renderConversationList();
  } catch (error) { toast(errorMessage(error), "error"); }
}

function messageMarkup(message) {
  const knowledge = message.knowledge;
  let meta = "";
  if (message.role === "assistant") {
    const knowledgeText = knowledge?.used ? "已使用企业知识" : knowledge?.status === "failed" ? "知识检索暂不可用" : "未使用企业知识";
    const modelText = message.model?.name || "";
    const citations = (knowledge?.citations || []).map(item => {
      const key = `${message.id}-${item.index}`; state.citations[key] = item;
      return `<button class="citation-chip" data-citation-key="${key}">[${item.index}] ${escapeHtml(item.document_name)}</button>`;
    }).join("");
    meta = `<div class="message-meta"><span>${knowledgeText}</span><span>${escapeHtml(modelText)}</span>${citations}</div>`;
  }
  return `<article class="chat-message ${message.role}"><div class="message-bubble">${escapeHtml(message.content)}${meta}</div></article>`;
}

function isChatNearBottom(root, threshold = 80) {
  return root.scrollHeight - root.scrollTop - root.clientHeight <= threshold;
}

function renderChatMessages(scrollToBottom = true) {
  const root = $("#chatMessages");
  if (!state.chatMessages.length) {
    root.innerHTML = '<div id="chatEmpty" class="chat-empty"><span>✦</span><h2>今天想聊些什么？</h2><p>我会先查找企业知识；没有相关资料时，也会使用所选模型正常回答。</p><div><button data-chat-example="公司的年假制度是什么？">询问企业制度</button><button data-chat-example="帮我写一封项目周报邮件">帮助写作</button></div></div>';
  } else root.innerHTML = state.chatMessages.map(messageMarkup).join("");
  if (scrollToBottom) root.scrollTop = root.scrollHeight;
}

function parseSSEBlock(block) {
  let event = "message", data = "";
  block.split("\n").forEach(line => { if (line.startsWith("event:")) event = line.slice(6).trim(); if (line.startsWith("data:")) data += line.slice(5).trim(); });
  return data ? { event, data: JSON.parse(data) } : null;
}

async function sendChatMessage() {
  const content = $("#chatInput").value.trim();
  if (!content || state.activeAbortController) return;
  const providerId = $("#providerSelect").value, modelId = $("#modelSelect").value;
  if (!providerId || !modelId) { toast("请先配置并选择模型", "error"); return; }
  $("#chatInput").value = "";
  state.chatMessages.push({ id: `local-${Date.now()}`, role: "user", content, status: "completed", created_at: new Date().toISOString() });
  renderChatMessages();
  const root = $("#chatMessages"), temporary = document.createElement("article");
  temporary.className = "chat-message assistant";
  temporary.innerHTML = '<div class="message-bubble"><span class="typing-dot"></span><div class="message-meta">正在检索企业知识…</div></div>';
  root.append(temporary); root.scrollTop = root.scrollHeight;
  const controller = new AbortController(); state.activeAbortController = controller;
  $("#stopChat").classList.remove("hidden"); $("#sendChat").disabled = true;
  let text = "", buffer = "";
  try {
    const response = await fetch("/chat/completions/stream", {
      method: "POST", signal: controller.signal,
      headers: { "Authorization": `Bearer ${state.token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: state.activeConversationId, message: content, provider_id: providerId, model_id: modelId, prompt_id: $("#promptSelect").value || null, idempotency_key: crypto.randomUUID() }),
    });
    if (!response.ok) { let detail; try { detail = await response.json(); } catch { detail = { detail: `请求失败 (${response.status})` }; } throw detail; }
    const reader = response.body.getReader(), decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n"); buffer = blocks.pop();
      for (const block of blocks) {
        const item = parseSSEBlock(block); if (!item) continue;
        if (item.event === "message.created") state.activeConversationId = item.data.conversation_id;
        if (item.event === "retrieval.completed") temporary.querySelector(".message-meta").textContent = item.data.status === "failed" ? "知识检索暂不可用 · AI 正在回答…" : item.data.used ? "已找到企业知识 · AI 正在回答…" : "未找到相关知识 · AI 正在回答…";
        if (item.event === "message.delta") {
          const followOutput = isChatNearBottom(root);
          text += item.data.content;
          temporary.querySelector(".message-bubble").firstChild.textContent = text;
          if (followOutput) root.scrollTop = root.scrollHeight;
        }
        if (item.event === "message.completed") {
          const followOutput = isChatNearBottom(root);
          state.chatMessages.push(item.data.message);
          temporary.remove();
          renderChatMessages(followOutput);
        }
        if (item.event === "message.failed") throw { detail: item.data.message };
      }
    }
    await refreshConversations();
  } catch (error) {
    temporary.remove();
    if (error.name !== "AbortError") toast(errorMessage(error), "error");
    else toast("已停止生成");
  } finally {
    state.activeAbortController = null; $("#stopChat").classList.add("hidden"); $("#sendChat").disabled = false;
  }
}

async function refreshConversations() {
  state.conversations = await api("/conversations"); renderConversationList();
  const active = state.conversations.find(item => item.id === state.activeConversationId);
  if (active) $("#chatTitle").textContent = active.title;
}

function showCitation(key) {
  const item = state.citations[key]; if (!item) return;
  $("#citationTitle").textContent = item.document_name;
  $("#citationScore").textContent = `相关度 ${Math.round(item.score * 100)}%`;
  $("#citationContent").textContent = item.excerpt; $("#citationDialog").showModal();
}

async function loadModelAdmin() {
  try {
    const providers = await api("/admin/model-providers");
    state.adminProviders = providers;
    $("#providerAdminList").innerHTML = providers.length ? providers.map(provider => `<article class="admin-config-card"><div><h3>${escapeHtml(provider.name)}</h3><span class="status-badge ${provider.is_enabled && provider.has_api_key ? "active" : "inactive"}">${provider.has_api_key ? "密钥已配置" : "缺少密钥"}</span></div><p>${escapeHtml(provider.base_url)}</p><code>${escapeHtml(provider.api_key_env)}</code><div class="admin-model-tags">${provider.models.map(model => `<span>${escapeHtml(model.name)}${model.is_default ? " · 默认" : ""}</span>`).join("") || "暂无模型"}</div><div class="table-actions"><button data-edit-provider="${provider.id}">编辑平台</button><button data-add-model="${provider.id}">＋ 新增模型</button></div></article>`).join("") : '<div class="empty-state"><p>尚未配置模型平台</p></div>';
  } catch (error) { toast(errorMessage(error), "error"); }
}

function resetProviderForm() {
  $("#providerForm").reset(); $("#providerId").value = ""; $("#providerKeyEnv").value = "AI_API_KEY";
  $("#providerFormTitle").textContent = "新增平台与模型"; $("#cancelProviderEdit").classList.add("hidden");
  $("#initialModelFields").classList.remove("hidden");
}

function editProvider(providerId) {
  const provider = state.adminProviders.find(item => item.id === providerId); if (!provider) return;
  $("#providerId").value = provider.id; $("#providerName").value = provider.name;
  $("#providerBaseUrl").value = provider.base_url; $("#providerKeyEnv").value = provider.api_key_env;
  $("#providerApiKey").value = ""; $("#providerFormTitle").textContent = `编辑 ${provider.name}`;
  $("#cancelProviderEdit").classList.remove("hidden"); $("#initialModelFields").classList.add("hidden");
  $("#providerForm").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function saveProvider(event) {
  event.preventDefault(); const button = $("#providerForm .button.primary"); setButtonLoading(button, true);
  try {
    const providerId = $("#providerId").value;
    const payload = { name: $("#providerName").value.trim(), base_url: $("#providerBaseUrl").value.trim(), api_key_env: $("#providerKeyEnv").value.trim() || "AI_API_KEY" };
    if ($("#providerApiKey").value) payload.api_key = $("#providerApiKey").value;
    if (providerId) {
      await api(`/admin/model-providers/${providerId}`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      const modelKey = $("#providerModelKey").value.trim(), modelName = $("#providerModelName").value.trim();
      if (!modelKey || !modelName) throw { detail: "请填写首个模型标识和显示名称" };
      const provider = await api("/admin/model-providers", { method: "POST", body: JSON.stringify(payload) });
      await api(`/admin/model-providers/${provider.id}/models`, { method: "POST", body: JSON.stringify({ model_key: modelKey, name: modelName, is_default: true }) });
    }
    resetProviderForm(); toast("模型平台已保存"); loadModelAdmin();
  } catch (error) { toast(errorMessage(error), "error"); } finally { setButtonLoading(button, false); }
}

function openModelDialog(providerId) {
  const provider = state.adminProviders.find(item => item.id === providerId); if (!provider) return;
  $("#modelForm").reset(); $("#modelProviderId").value = providerId;
  $("#newModelContext").value = "32000"; $("#modelDialogTitle").textContent = `为 ${provider.name} 新增模型`;
  $("#modelDialog").showModal();
}

async function saveModel(event) {
  event.preventDefault(); const button = $("#modelForm .button.primary"); setButtonLoading(button, true);
  try {
    await api(`/admin/model-providers/${$("#modelProviderId").value}/models`, { method: "POST", body: JSON.stringify({ model_key: $("#newModelKey").value.trim(), name: $("#newModelName").value.trim(), context_window: Number($("#newModelContext").value), is_default: $("#newModelDefault").checked }) });
    $("#modelDialog").close(); toast("模型已新增"); loadModelAdmin();
  } catch (error) { toast(errorMessage(error), "error"); } finally { setButtonLoading(button, false); }
}

async function loadPromptAdmin() {
  try {
    state.prompts = await api("/prompts");
    $("#promptAdminList").innerHTML = state.prompts.map(item => `<article class="admin-config-card"><div><h3>${escapeHtml(item.name)}</h3><span class="status-badge ${item.status === "published" ? "active" : "inactive"}">${item.status === "published" ? "已发布" : "草稿"} · v${item.version}</span></div><p>${escapeHtml(item.description || "暂无描述")}</p>${item.status !== "published" ? `<button class="text-button" data-publish-prompt="${item.id}">发布此版本</button>` : ""}</article>`).join("");
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function savePrompt(event) {
  event.preventDefault(); const button = $("#promptForm .button.primary"); setButtonLoading(button, true);
  try {
    await api("/prompts", { method: "POST", body: JSON.stringify({ name: $("#promptName").value.trim(), system_prompt: $("#promptSystem").value, hit_template: $("#promptHit").value, miss_template: $("#promptMiss").value, top_k: Number($("#promptTopK").value), min_score: Number($("#promptMinScore").value), publish: $("#promptPublish").checked }) });
    $("#promptName").value = ""; toast("Prompt 已保存"); loadPromptAdmin();
  } catch (error) { toast(errorMessage(error), "error"); } finally { setButtonLoading(button, false); }
}

async function loadDocuments() {
  try { state.documents = await api("/docs/list"); renderDocuments(); }
  catch (error) { toast(errorMessage(error), "error"); }
}

function renderDocuments() {
  const term = $("#documentFilter").value.trim().toLowerCase();
  const docs = state.documents.filter(doc => doc.name.toLowerCase().includes(term));
  $("#documentTotal").textContent = `共 ${state.documents.length} 份文档`;
  $("#documentsEmpty").classList.toggle("hidden", state.documents.length > 0);
  $("#documentsTable").innerHTML = docs.map(doc => `<tr><td><div class="doc-cell"><span>▤</span><div><b>${escapeHtml(doc.name)}</b><small>知识文档</small></div></div></td><td><span class="mono">${escapeHtml(doc.doc_id)}</span></td><td>${doc.chunk_count} 个</td><td><span class="status-badge active">已索引</span></td><td><div class="table-actions"><button data-view-doc="${escapeHtml(doc.doc_id)}">查看</button></div></td></tr>`).join("");
}

async function saveDocument(event) {
  event.preventDefault();
  const name = $("#documentName").value.trim();
  const content = $("#documentContent").value.trim();
  if (!name || !content) { toast("请填写文档名称和内容", "error"); return; }
  const button = $("#saveDocument");
  setButtonLoading(button, true, "正在建立索引…");
  try {
    await api("/docs/upload", { method: "POST", body: JSON.stringify({ name, content }) });
    $("#documentDialog").close();
    $("#documentForm").reset();
    $("#contentLength").textContent = "0";
    toast("文档已录入并建立索引");
    await loadDocuments();
    loadOverview();
  } catch (error) { toast(errorMessage(error), "error"); }
  finally { setButtonLoading(button, false); }
}

async function viewDocument(docId) {
  try {
    const doc = await api(`/docs/${encodeURIComponent(docId)}`);
    $("#detailName").textContent = doc.name;
    $("#detailId").textContent = `ID ${doc.doc_id}`;
    $("#detailChunks").textContent = `${doc.chunk_count} 个索引片段`;
    $("#detailContent").textContent = doc.content;
    $("#documentDetailDialog").showModal();
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function loadFiles() {
  try { state.files = await api("/files"); renderFiles(); $("#fileCount").textContent = state.files.length; }
  catch (error) { toast(errorMessage(error), "error"); }
}

function fileExtension(name) { return name.includes(".") ? name.split(".").pop().slice(0, 4) : "FILE"; }
function renderFiles() {
  $("#fileTotal").textContent = `共 ${state.files.length} 个文件`;
  $("#filesEmpty").classList.toggle("hidden", state.files.length > 0);
  $("#filesGrid").innerHTML = state.files.map(file => `<article class="file-card"><span class="file-type">${escapeHtml(fileExtension(file.original_filename))}</span><div><b title="${escapeHtml(file.original_filename)}">${escapeHtml(file.original_filename)}</b><small>${formatBytes(file.size)}</small></div><div class="table-actions"><button data-download-file="${escapeHtml(file.filename)}" data-file-name="${escapeHtml(file.original_filename)}" title="下载">↓</button><button class="delete" data-delete-file="${escapeHtml(file.filename)}" data-file-name="${escapeHtml(file.original_filename)}" title="删除">×</button></div></article>`).join("");
}

function uploadFile(file) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { toast("文件不能超过 10 MB", "error"); return; }
  const progress = $("#uploadProgress");
  progress.classList.remove("hidden");
  $("#uploadName").textContent = file.name;
  $("#uploadBar").style.width = "0%";
  $("#uploadPercent").textContent = "0%";
  const form = new FormData(); form.append("file", file);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/files/upload");
  xhr.setRequestHeader("Authorization", `Bearer ${state.token}`);
  xhr.upload.onprogress = event => {
    if (!event.lengthComputable) return;
    const percent = Math.round(event.loaded / event.total * 100);
    $("#uploadBar").style.width = `${percent}%`; $("#uploadPercent").textContent = `${percent}%`;
  };
  xhr.onload = () => {
    setTimeout(() => progress.classList.add("hidden"), 600);
    if (xhr.status >= 200 && xhr.status < 300) { toast("文件上传成功"); loadFiles(); }
    else { try { toast(errorMessage(JSON.parse(xhr.responseText)), "error"); } catch { toast("文件上传失败", "error"); } }
  };
  xhr.onerror = () => { progress.classList.add("hidden"); toast("网络异常，上传失败", "error"); };
  xhr.send(form);
}

async function downloadFile(filename, originalName) {
  try {
    const response = await fetch(`/files/${encodeURIComponent(filename)}`, { headers: { Authorization: `Bearer ${state.token}` } });
    if (!response.ok) throw new Error("下载失败");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = url; link.download = originalName; link.click();
    URL.revokeObjectURL(url);
  } catch { toast("文件下载失败", "error"); }
}

function confirmAction(title, message, okText = "确认") {
  return new Promise(resolve => {
    const dialog = $("#confirmDialog");
    $("#confirmTitle").textContent = title; $("#confirmMessage").textContent = message; $("#confirmOk").textContent = okText;
    const finish = value => { dialog.close(); cleanup(); resolve(value); };
    const yes = () => finish(true), no = () => finish(false), cancel = event => { event.preventDefault(); finish(false); };
    const cleanup = () => { $("#confirmOk").removeEventListener("click", yes); $("#confirmCancel").removeEventListener("click", no); dialog.removeEventListener("cancel", cancel); };
    $("#confirmOk").addEventListener("click", yes); $("#confirmCancel").addEventListener("click", no); dialog.addEventListener("cancel", cancel); dialog.showModal();
  });
}

async function deleteFile(filename, name) {
  if (!await confirmAction("删除文件？", `“${name}”删除后无法恢复。`, "确认删除")) return;
  try { await api(`/files/${encodeURIComponent(filename)}`, { method: "DELETE" }); toast("文件已删除"); loadFiles(); }
  catch (error) { toast(errorMessage(error), "error"); }
}

async function loadUsers() {
  try { state.users = await api("/users"); renderUsers(); $("#userCount").textContent = state.users.length; }
  catch (error) { toast(errorMessage(error), "error"); }
}

function renderUsers() {
  const term = $("#userFilter").value.trim().toLowerCase();
  const users = state.users.filter(user => `${user.full_name} ${user.email}`.toLowerCase().includes(term));
  $("#usersTotal").textContent = `共 ${state.users.length} 位成员`;
  $("#usersTable").innerHTML = users.map(user => `<tr><td><div class="user-cell"><span class="avatar small">${escapeHtml(initials(user.full_name))}</span><div><b>${escapeHtml(user.full_name)}${user.id === state.user.id ? "（我）" : ""}</b><small>${escapeHtml(user.email)}</small></div></div></td><td><span class="role-badge ${user.role}">${roleText(user.role)}</span></td><td><span class="status-badge ${user.is_active ? "active" : "inactive"}">${user.is_active ? "正常" : "已停用"}</span></td><td>${formatDate(user.created_at)}</td><td><div class="table-actions"><button data-edit-user="${user.id}">编辑</button>${user.id !== state.user.id ? `<button class="delete" data-delete-user="${user.id}" data-user-name="${escapeHtml(user.full_name)}">删除</button>` : ""}</div></td></tr>`).join("");
}

function openUserEditor(userId) {
  const user = state.users.find(item => item.id === userId); if (!user) return;
  $("#editUserId").value = user.id; $("#editUserName").textContent = `编辑 ${user.full_name}`;
  $("#editFullName").value = user.full_name; $("#editRole").value = user.role; $("#editActive").checked = user.is_active;
  $("#userDialog").showModal();
}

async function saveUser(event) {
  event.preventDefault();
  const id = $("#editUserId").value;
  const button = $("#userForm .button.primary"); setButtonLoading(button, true, "保存中…");
  try {
    const user = await api(`/users/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ full_name: $("#editFullName").value.trim(), role: $("#editRole").value, is_active: $("#editActive").checked }) });
    if (id === state.user.id) { state.user = user; applyUser(); }
    $("#userDialog").close(); toast("用户信息已更新"); await loadUsers();
  } catch (error) { toast(errorMessage(error), "error"); }
  finally { setButtonLoading(button, false); }
}

async function deleteUser(id, name) {
  if (!await confirmAction("删除用户？", `将永久删除“${name}”的账户。`, "确认删除")) return;
  try { await api(`/users/${encodeURIComponent(id)}`, { method: "DELETE" }); toast("用户已删除"); loadUsers(); }
  catch (error) { toast(errorMessage(error), "error"); }
}

async function saveProfile(event) {
  event.preventDefault();
  const payload = { full_name: $("#profileNameInput").value.trim() };
  if ($("#profilePassword").value) payload.password = $("#profilePassword").value;
  const button = $("#profileForm .button.primary"); setButtonLoading(button, true, "保存中…");
  try {
    state.user = await api("/users/me", { method: "PATCH", body: JSON.stringify(payload) });
    $("#profilePassword").value = ""; applyUser(); toast("个人资料已更新");
  } catch (error) { toast(errorMessage(error), "error"); }
  finally { setButtonLoading(button, false); }
}

function bindEvents() {
  $$('[data-close-dialog]').forEach(button => button.onclick = () => $(`#${button.dataset.closeDialog}`).close());
  $("#loginTab").onclick = () => setAuthMode("login");
  $("#registerTab").onclick = () => setAuthMode("register");
  $("#authForm").addEventListener("submit", handleAuth);
  $("#authHint").addEventListener("click", event => { if (event.target.dataset.switchAuth) setAuthMode(event.target.dataset.switchAuth); });
  $("#togglePassword").onclick = () => { const input = $("#password"); input.type = input.type === "password" ? "text" : "password"; };
  $("#logoutButton").onclick = () => logout();
  $$("[data-page]").forEach(button => button.onclick = () => navigate(button.dataset.page));
  $$("[data-go]").forEach(button => button.onclick = () => navigate(button.dataset.go));
  $("#topProfile").onclick = () => navigate("profile");
  $("#menuButton").onclick = () => $("#sidebar").classList.add("open");
  $("#sidebarOverlay").onclick = () => $("#sidebar").classList.remove("open");
  $("#heroSearchForm").onsubmit = event => { event.preventDefault(); const query = $("#heroSearchInput").value; if (query.trim()) { state.pendingChatMessage = query.trim(); $("#heroSearchInput").value = ""; navigate("chat"); } };
  $("#searchForm").onsubmit = event => { event.preventDefault(); doSearch($("#searchQuery").value); };
  $$(".suggestions button").forEach(button => button.onclick = () => doSearch(button.textContent));
  $("#documentFilter").oninput = renderDocuments;
  $("#newDocumentButton").onclick = () => $("#documentDialog").showModal();
  $("#documentForm").addEventListener("submit", saveDocument);
  $("#documentContent").oninput = event => $("#contentLength").textContent = event.target.value.length;
  $("#documentsTable").onclick = event => { const id = event.target.dataset.viewDoc; if (id) viewDocument(id); };
  $("#closeDetail").onclick = () => $("#documentDetailDialog").close();
  $("#chooseFileButton").onclick = () => $("#fileInput").click();
  $("#dropZone").onclick = event => { if (event.target.id !== "chooseFileButton") $("#fileInput").click(); };
  $("#dropZone").onkeydown = event => { if (event.key === "Enter" || event.key === " ") $("#fileInput").click(); };
  $("#fileInput").onchange = event => { uploadFile(event.target.files[0]); event.target.value = ""; };
  ["dragenter", "dragover"].forEach(name => $("#dropZone").addEventListener(name, event => { event.preventDefault(); $("#dropZone").classList.add("dragging"); }));
  ["dragleave", "drop"].forEach(name => $("#dropZone").addEventListener(name, event => { event.preventDefault(); $("#dropZone").classList.remove("dragging"); }));
  $("#dropZone").addEventListener("drop", event => uploadFile(event.dataTransfer.files[0]));
  $("#refreshFiles").onclick = loadFiles;
  $("#filesGrid").onclick = event => { const target = event.target; if (target.dataset.downloadFile) downloadFile(target.dataset.downloadFile, target.dataset.fileName); if (target.dataset.deleteFile) deleteFile(target.dataset.deleteFile, target.dataset.fileName); };
  $("#userFilter").oninput = renderUsers;
  $("#usersTable").onclick = event => { if (event.target.dataset.editUser) openUserEditor(event.target.dataset.editUser); if (event.target.dataset.deleteUser) deleteUser(event.target.dataset.deleteUser, event.target.dataset.userName); };
  $("#userForm").addEventListener("submit", saveUser);
  $("#profileForm").addEventListener("submit", saveProfile);
  $("#providerSelect").onchange = renderModelOptions;
  $("#newConversation").onclick = newConversation;
  $("#conversationFilter").oninput = renderConversationList;
  $("#conversationList").onclick = async event => {
    const deleteId = event.target.dataset.deleteConversation;
    if (deleteId) {
      event.stopPropagation();
      if (await confirmAction("删除会话？", "该会话将从历史记录中移除。", "确认删除")) {
        await api(`/conversations/${encodeURIComponent(deleteId)}`, { method: "DELETE" });
        if (state.activeConversationId === deleteId) newConversation(); await refreshConversations();
      }
      return;
    }
    const item = event.target.closest("[data-conversation-id]"); if (item) openConversation(item.dataset.conversationId);
  };
  $("#chatForm").onsubmit = event => { event.preventDefault(); sendChatMessage(); };
  $("#chatInput").onkeydown = event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendChatMessage(); } };
  $("#stopChat").onclick = () => state.activeAbortController?.abort();
  $("#chatMessages").onclick = event => {
    if (event.target.dataset.chatExample) { $("#chatInput").value = event.target.dataset.chatExample; sendChatMessage(); }
    if (event.target.dataset.citationKey) showCitation(event.target.dataset.citationKey);
  };
  $("#providerForm").addEventListener("submit", saveProvider);
  $("#cancelProviderEdit").onclick = resetProviderForm;
  $("#providerAdminList").onclick = event => {
    if (event.target.dataset.editProvider) editProvider(event.target.dataset.editProvider);
    if (event.target.dataset.addModel) openModelDialog(event.target.dataset.addModel);
  };
  $("#modelForm").addEventListener("submit", saveModel);
  $("#promptForm").addEventListener("submit", savePrompt);
  $("#promptAdminList").onclick = async event => {
    const id = event.target.dataset.publishPrompt;
    if (id) { try { await api(`/prompts/${encodeURIComponent(id)}/publish`, { method: "POST" }); toast("Prompt 已发布"); loadPromptAdmin(); } catch (error) { toast(errorMessage(error), "error"); } }
  };
}

async function init() {
  bindEvents();
  if (!state.token) return;
  try { state.user = await api("/auth/me"); enterApp(); }
  catch { /* api() resets invalid login state */ }
}

init();
