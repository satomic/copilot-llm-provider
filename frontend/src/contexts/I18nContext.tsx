import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";

type Locale = "en" | "zh";

interface I18nContextType {
  locale: Locale;
  toggleLocale: () => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextType | null>(null);

const STORAGE_KEY = "copilot-llm-provider-locale";

const translations: Record<Locale, Record<string, string>> = {
  en: {
    // App
    "app.title": "Copilot LLM Provider",
    "app.subtitle": "LLM API Server",

    // Navigation
    "nav.dashboard": "Dashboard",
    "nav.playground": "Playground",
    "nav.tools": "CLI Reference",
    "nav.apiRef": "API Reference",
    "nav.sessions": "Sessions",
    "nav.settings": "Settings",
    "nav.logout": "Logout",

    // Status
    "status.connected": "Connected",
    "status.disconnected": "Disconnected",

    // Theme
    "theme.dark": "Dark mode",
    "theme.light": "Light mode",

    // Chat
    "chat.you": "You",
    "chat.assistant": "Assistant",

    // Models
    "models.error": "Failed to load models:",
    "models.loading": "Loading models...",
    "models.noModels": "No models available",

    // Login page
    "login.title": "Copilot LLM Provider",
    "login.subtitle": "Connect to your Copilot-powered LLM API server",
    "login.apiKey": "API Key",
    "login.placeholder": "Leave empty for no-auth mode",
    "login.hint": "Enter the API key configured on your server, or leave blank if authentication is disabled.",
    "login.error.connection": "Could not connect to the server. Please check that the backend is running.",
    "login.error.failed": "Connection failed. Please ensure the backend server is accessible.",
    "login.connect": "Connect",
    "login.connecting": "Connecting...",
    "login.footer": "The server should be running at",
    "login.setApiKey": "Set as server API key",
    "login.setApiKeyHint": "This will configure the server to require this API key for all requests.",
    "login.createAccount": "Create Account",
    "login.signIn": "Sign In",
    "login.createAccountHint": "Create the first admin account to get started.",
    "login.signInHint": "Sign in with your admin credentials.",
    "login.username": "Username",
    "login.usernamePlaceholder": "Enter username",
    "login.password": "Password",
    "login.passwordPlaceholder": "Enter password",

    // Dashboard page
    "dashboard.title": "Dashboard",
    "dashboard.serverStatus": "Server Status",
    "dashboard.checking": "Checking connection...",
    "dashboard.online": "Backend server is running and reachable",
    "dashboard.offline": "Cannot reach the backend server",
    "dashboard.playground": "Playground",
    "dashboard.playgroundDesc": "Chat with models in real-time",
    "dashboard.settings": "Settings",
    "dashboard.settingsDesc": "API endpoints and examples",
    "dashboard.models": "Available Models",
    "dashboard.refresh": "Refresh",
    "dashboard.refreshing": "Refreshing...",
    "dashboard.loadingModels": "Loading models...",
    "dashboard.noModels": "No models available. Check your server configuration.",
    "dashboard.usageStats": "Usage Statistics",
    "dashboard.totalRequests": "Total Requests",
    "dashboard.premiumRequests": "Premium",
    "dashboard.freeRequests": "Free",
    "dashboard.noStats": "No usage data yet",
    "dashboard.modelUsage": "Model Usage",
    "dashboard.requests": "requests",
    "dashboard.lastUsed": "Last used",
    "dashboard.premium": "Premium",
    "dashboard.standard": "Standard",
    "dashboard.free": "Free",
    "dashboard.weightedTotal": "Billing Units",
    "dashboard.weighted": "weighted",
    "dashboard.dailyTrend": "Daily Trend",
    "dashboard.requestDistribution": "Request Distribution",
    "dashboard.modelsCount": "models",
    "dashboard.aliasUsage": "API Key Usage",

    // Playground page
    "playground.title": "Playground",
    "playground.params": "Parameters",
    "playground.clearChat": "Clear Chat",
    "playground.startConvo": "Start a conversation",
    "playground.startConvoDesc": "Select a model and send a message to begin.",
    "playground.streaming": "Streaming...",
    "playground.temperature": "Temperature",
    "playground.precise": "Precise",
    "playground.creative": "Creative",
    "playground.maxTokens": "Max Tokens",
    "playground.currentModel": "Current Model",
    "playground.noneSelected": "None selected",
    "playground.messages": "Messages",
    "playground.messagesInContext": "messages in context",
    "playground.inputPlaceholder": "Type a message...",
    "playground.send": "Send",
    "playground.compareMode": "Compare",
    "playground.addModel": "Add Model",
    "playground.removeModel": "Remove",
    "playground.selectModels": "Select models to compare",
    "playground.noResponse": "No response yet",

    // Settings page
    "settings.title": "Settings",
    "settings.connectionInfo": "Connection Info",
    "settings.authMode": "Auth Mode:",
    "settings.apiKeyAuth": "API Key",
    "settings.noAuth": "No Authentication",
    "settings.apiKeyLabel": "API Key:",
    "settings.serverApiKey": "Server API Key",
    "settings.serverApiKeyDesc": "Configure the API key that all clients must provide to use this server.",
    "settings.currentKey": "Current Key:",
    "settings.newKey": "New API Key",
    "settings.setKey": "Set API Key",
    "settings.removeKey": "Disable Auth",
    "settings.keySet": "API key configured successfully",
    "settings.keyRemoved": "Authentication disabled",
    "settings.endpoints": "API Endpoints",
    "settings.openaiChat": "OpenAI Chat Completions",
    "settings.anthropicMessages": "Anthropic Messages",
    "settings.modelsList": "Models List",
    "settings.healthCheck": "Health Check",
    "settings.copy": "Copy",
    "settings.copied": "Copied!",
    "settings.usageExamples": "Usage Examples",
    "settings.platform": "Platform",
    "settings.curl": "cURL",
    "settings.powershell": "PowerShell",
    "settings.python": "Python (OpenAI SDK)",
    "settings.nodejs": "Node.js (OpenAI SDK)",

    // API Reference page
    "apiRef.title": "API Reference",
    "apiRef.openai": "OpenAI",
    "apiRef.anthropic": "Anthropic",
    "apiRef.chatCompletions": "Chat Completions",
    "apiRef.messages": "Messages",
    "apiRef.pythonOpenai": "Python (OpenAI SDK)",
    "apiRef.nodejsOpenai": "Node.js (OpenAI SDK)",
    "apiRef.pythonAnthropic": "Python (Anthropic SDK)",
    "apiRef.nodejsAnthropic": "Node.js (Anthropic SDK)",

    // Settings — API Key management
    "settings.apiKeys": "API Keys",
    "settings.apiKeysDesc": "Create and manage API keys for external access.",
    "settings.createKey": "Create Key",
    "settings.cancel": "Cancel",
    "settings.keyAlias": "Key Alias",
    "settings.keyAliasPlaceholder": "e.g. my-app, team-backend",
    "settings.allowedModels": "Allowed Models",
    "settings.allowedModelsHint": "Leave empty to allow all models.",
    "settings.maxRequests": "Max Requests",
    "settings.maxPremiumRequests": "Max Premium Requests",
    "settings.unlimited": "Unlimited",
    "settings.keyCreated": "Key Created Successfully!",
    "settings.keyCreatedHint": "Copy this key now — it won't be shown again.",
    "settings.noKeys": "No API keys created yet.",
    "settings.edit": "Edit",
    "settings.editKey": "Edit API Key",
    "settings.save": "Save",
    "settings.keyUpdated": "API key updated successfully.",
    "settings.disabled": "Disabled",
    "settings.disable": "Disable",
    "settings.enable": "Enable",
    "settings.resetUsage": "Reset Usage",
    "settings.usage": "Usage",
    "settings.models": "Models",
    "settings.allModels": "All models",

    // Client setup page
    "tools.title": "CLI Reference",
    "tools.platform": "Platform",
    "tools.hint": "Replace YOUR_API_KEY with the API key configured on your server.",
    "tools.envVars": "Environment Variables",
    "tools.claudeCode": "Claude Code",
    "tools.claudeCodeDesc": "Anthropic's official CLI for Claude",
    "tools.codexCli": "Codex CLI",
    "tools.codexCliDesc": "OpenAI's command-line coding agent",

    // Sessions page
    "sessions.title": "Sessions",
    "sessions.records": "Session Records",
    "sessions.loading": "Loading...",
    "sessions.noSessions": "No sessions recorded yet",
    "sessions.selectSession": "Select a session to view details",
    "sessions.detail": "Session Detail",
    "sessions.sessionId": "Session ID",
    "sessions.model": "Model",
    "sessions.time": "Time",
    "sessions.duration": "Duration",
    "sessions.format": "API Format",
    "sessions.streaming": "Streaming",
    "sessions.clientIp": "Client IP",
    "sessions.messages": "Messages",
    "sessions.response": "Response",
    "sessions.noResponse": "(empty response)",
    "sessions.prev": "Previous",
    "sessions.next": "Next",
    "sessions.inputPlaceholder": "Type a message to continue the conversation...",
    "sessions.send": "Send",
    "sessions.sending": "Sending...",
    "sessions.delete": "Delete",
    "sessions.deleteSelected": "Delete Selected",
    "sessions.selectAll": "Select All",
    "sessions.deselectAll": "Deselect All",
    "sessions.selected": "selected",
    "sessions.confirmDelete": "Are you sure you want to delete this session?",
    "sessions.confirmBatchDelete": "Are you sure you want to delete {count} sessions?",
    "sessions.filterModel": "Model",
    "sessions.filterAlias": "API Key",
    "sessions.filterToken": "GitHub Token",
    "sessions.filterAll": "All",

    // GitHub Token management
    "tokens.title": "GitHub Tokens",
    "tokens.desc": "Manage GitHub tokens for multi-account Copilot access. Requests are distributed via round-robin.",
    "tokens.addToken": "Add Token",
    "tokens.alias": "Token Alias",
    "tokens.aliasPlaceholder": "e.g. personal, team-account",
    "tokens.token": "GitHub Token",
    "tokens.tokenPlaceholder": "github_pat_...",
    "tokens.noTokens": "No GitHub tokens configured.",
    "tokens.noTokensHint": "Add a GitHub token to start using multi-account pooling.",
    "tokens.status": "Status",
    "tokens.active": "Active",
    "tokens.error": "Error",
    "tokens.stopped": "Stopped",
    "tokens.pending": "Pending",
    "tokens.requests": "Requests",
    "tokens.premiumReqs": "Premium",
    "tokens.lastUsed": "Last used",
    "tokens.never": "Never",
    "tokens.quota": "Quota",
    "tokens.quotaLoading": "Fetching...",
    "tokens.quotaUnknown": "Unknown",
    "tokens.refreshQuota": "Refresh Quota",
    "tokens.poolStatus": "Token Pool",
    "tokens.activeTokens": "active",
    "tokens.totalTokens": "total",

    // Dashboard — token usage
    "dashboard.tokenUsage": "GitHub Token Usage",
  },
  zh: {
    // App
    "app.title": "Copilot LLM Provider",
    "app.subtitle": "LLM API 服务器",

    // Navigation
    "nav.dashboard": "仪表盘",
    "nav.playground": "聊天测试",
    "nav.tools": "CLI 参考",
    "nav.apiRef": "API 参考",
    "nav.sessions": "会话记录",
    "nav.settings": "设置",
    "nav.logout": "退出登录",

    // Status
    "status.connected": "已连接",
    "status.disconnected": "未连接",

    // Theme
    "theme.dark": "深色模式",
    "theme.light": "浅色模式",

    // Chat
    "chat.you": "你",
    "chat.assistant": "助手",

    // Models
    "models.error": "加载模型失败：",
    "models.loading": "加载模型中...",
    "models.noModels": "暂无可用模型",

    // Login page
    "login.title": "Copilot LLM Provider",
    "login.subtitle": "连接到您的 Copilot 驱动的 LLM API 服务器",
    "login.apiKey": "API 密钥",
    "login.placeholder": "留空表示无需认证",
    "login.hint": "输入您服务器上配置的 API 密钥，如果未启用认证则留空。",
    "login.error.connection": "无法连接到服务器，请检查后端是否正在运行。",
    "login.error.failed": "连接失败，请确保后端服务器可访问。",
    "login.connect": "连接",
    "login.connecting": "连接中...",
    "login.footer": "服务器应运行在",
    "login.setApiKey": "设置为服务器 API 密钥",
    "login.setApiKeyHint": "这将配置服务器要求所有请求必须提供此 API 密钥。",
    "login.createAccount": "创建账户",
    "login.signIn": "登录",
    "login.createAccountHint": "创建第一个管理员账户以开始使用。",
    "login.signInHint": "使用管理员凭据登录。",
    "login.username": "用户名",
    "login.usernamePlaceholder": "输入用户名",
    "login.password": "密码",
    "login.passwordPlaceholder": "输入密码",

    // Dashboard page
    "dashboard.title": "仪表盘",
    "dashboard.serverStatus": "服务器状态",
    "dashboard.checking": "正在检查连接...",
    "dashboard.online": "后端服务器正在运行且可访问",
    "dashboard.offline": "无法连接到后端服务器",
    "dashboard.playground": "聊天测试",
    "dashboard.playgroundDesc": "与模型实时对话",
    "dashboard.settings": "设置",
    "dashboard.settingsDesc": "API 端点和示例",
    "dashboard.models": "可用模型",
    "dashboard.refresh": "刷新",
    "dashboard.refreshing": "刷新中...",
    "dashboard.loadingModels": "加载模型中...",
    "dashboard.noModels": "暂无可用模型，请检查服务器配置。",
    "dashboard.usageStats": "使用统计",
    "dashboard.totalRequests": "总请求数",
    "dashboard.premiumRequests": "高级请求",
    "dashboard.freeRequests": "免费请求",
    "dashboard.noStats": "暂无使用数据",
    "dashboard.modelUsage": "模型用量",
    "dashboard.requests": "次请求",
    "dashboard.lastUsed": "最后使用",
    "dashboard.premium": "高级",
    "dashboard.standard": "标准",
    "dashboard.free": "免费",
    "dashboard.weightedTotal": "计费单元",
    "dashboard.weighted": "加权",
    "dashboard.dailyTrend": "每日趋势",
    "dashboard.requestDistribution": "请求分布",
    "dashboard.modelsCount": "个模型",
    "dashboard.aliasUsage": "API Key 用量",

    // Playground page
    "playground.title": "聊天测试",
    "playground.params": "参数",
    "playground.clearChat": "清除对话",
    "playground.startConvo": "开始对话",
    "playground.startConvoDesc": "选择一个模型并发送消息开始对话。",
    "playground.streaming": "生成中...",
    "playground.temperature": "温度",
    "playground.precise": "精确",
    "playground.creative": "创意",
    "playground.maxTokens": "最大令牌数",
    "playground.currentModel": "当前模型",
    "playground.noneSelected": "未选择",
    "playground.messages": "消息",
    "playground.messagesInContext": "条上下文消息",
    "playground.inputPlaceholder": "输入消息...",
    "playground.send": "发送",
    "playground.compareMode": "对比",
    "playground.addModel": "添加模型",
    "playground.removeModel": "移除",
    "playground.selectModels": "选择要对比的模型",
    "playground.noResponse": "暂无响应",

    // Settings page
    "settings.title": "设置",
    "settings.connectionInfo": "连接信息",
    "settings.authMode": "认证模式：",
    "settings.apiKeyAuth": "API 密钥",
    "settings.noAuth": "无需认证",
    "settings.apiKeyLabel": "API 密钥：",
    "settings.serverApiKey": "服务器 API 密钥",
    "settings.serverApiKeyDesc": "配置所有客户端必须提供的 API 密钥。",
    "settings.currentKey": "当前密钥：",
    "settings.newKey": "新 API 密钥",
    "settings.setKey": "设置密钥",
    "settings.removeKey": "禁用认证",
    "settings.keySet": "API 密钥配置成功",
    "settings.keyRemoved": "认证已禁用",
    "settings.endpoints": "API 端点",
    "settings.openaiChat": "OpenAI 聊天补全",
    "settings.anthropicMessages": "Anthropic 消息",
    "settings.modelsList": "模型列表",
    "settings.healthCheck": "健康检查",
    "settings.copy": "复制",
    "settings.copied": "已复制！",
    "settings.usageExamples": "使用示例",
    "settings.platform": "平台",
    "settings.curl": "cURL",
    "settings.powershell": "PowerShell",
    "settings.python": "Python (OpenAI SDK)",
    "settings.nodejs": "Node.js (OpenAI SDK)",

    // API Reference page
    "apiRef.title": "API 参考",
    "apiRef.openai": "OpenAI",
    "apiRef.anthropic": "Anthropic",
    "apiRef.chatCompletions": "Chat Completions",
    "apiRef.messages": "Messages",
    "apiRef.pythonOpenai": "Python (OpenAI SDK)",
    "apiRef.nodejsOpenai": "Node.js (OpenAI SDK)",
    "apiRef.pythonAnthropic": "Python (Anthropic SDK)",
    "apiRef.nodejsAnthropic": "Node.js (Anthropic SDK)",

    // Settings — API Key management
    "settings.apiKeys": "API 密钥管理",
    "settings.apiKeysDesc": "创建和管理用于外部访问的 API 密钥。",
    "settings.createKey": "创建密钥",
    "settings.cancel": "取消",
    "settings.keyAlias": "密钥别名",
    "settings.keyAliasPlaceholder": "例如 my-app、team-backend",
    "settings.allowedModels": "允许的模型",
    "settings.allowedModelsHint": "留空则允许所有模型。",
    "settings.maxRequests": "最大请求数",
    "settings.maxPremiumRequests": "最大高级请求数",
    "settings.unlimited": "无限制",
    "settings.keyCreated": "密钥创建成功！",
    "settings.keyCreatedHint": "请立即复制此密钥，之后将不再显示。",
    "settings.noKeys": "尚未创建任何 API 密钥。",
    "settings.edit": "编辑",
    "settings.editKey": "编辑 API 密钥",
    "settings.save": "保存",
    "settings.keyUpdated": "API 密钥更新成功。",
    "settings.disabled": "已禁用",
    "settings.disable": "禁用",
    "settings.enable": "启用",
    "settings.resetUsage": "重置用量",
    "settings.usage": "用量",
    "settings.models": "模型",
    "settings.allModels": "所有模型",

    // Client setup page
    "tools.title": "CLI 参考",
    "tools.platform": "平台",
    "tools.hint": "请将 YOUR_API_KEY 替换为服务器上配置的 API 密钥。",
    "tools.envVars": "环境变量",
    "tools.claudeCode": "Claude Code",
    "tools.claudeCodeDesc": "Anthropic 官方 Claude CLI 工具",
    "tools.codexCli": "Codex CLI",
    "tools.codexCliDesc": "OpenAI 命令行编程助手",

    // Sessions page
    "sessions.title": "会话记录",
    "sessions.records": "会话列表",
    "sessions.loading": "加载中...",
    "sessions.noSessions": "暂无会话记录",
    "sessions.selectSession": "选择一个会话查看详情",
    "sessions.detail": "会话详情",
    "sessions.sessionId": "会话 ID",
    "sessions.model": "模型",
    "sessions.time": "时间",
    "sessions.duration": "耗时",
    "sessions.format": "API 格式",
    "sessions.streaming": "流式",
    "sessions.clientIp": "客户端 IP",
    "sessions.messages": "消息",
    "sessions.response": "响应",
    "sessions.noResponse": "（空响应）",
    "sessions.prev": "上一页",
    "sessions.next": "下一页",
    "sessions.inputPlaceholder": "输入消息继续对话...",
    "sessions.send": "发送",
    "sessions.sending": "发送中...",
    "sessions.delete": "删除",
    "sessions.deleteSelected": "删除所选",
    "sessions.selectAll": "全选",
    "sessions.deselectAll": "取消全选",
    "sessions.selected": "已选",
    "sessions.confirmDelete": "确定要删除此会话吗？",
    "sessions.confirmBatchDelete": "确定要删除 {count} 个会话吗？",
    "sessions.filterModel": "模型",
    "sessions.filterAlias": "API Key",
    "sessions.filterToken": "GitHub Token",
    "sessions.filterAll": "全部",

    // GitHub Token management
    "tokens.title": "GitHub Tokens",
    "tokens.desc": "管理多个 GitHub Token，实现多账户 Copilot 访问。请求通过轮询分配。",
    "tokens.addToken": "添加 Token",
    "tokens.alias": "Token 别名",
    "tokens.aliasPlaceholder": "例如 personal、team-account",
    "tokens.token": "GitHub Token",
    "tokens.tokenPlaceholder": "github_pat_...",
    "tokens.noTokens": "尚未配置 GitHub Token。",
    "tokens.noTokensHint": "添加 GitHub Token 以开始多账户池化。",
    "tokens.status": "状态",
    "tokens.active": "活跃",
    "tokens.error": "错误",
    "tokens.stopped": "已停止",
    "tokens.pending": "等待中",
    "tokens.requests": "请求数",
    "tokens.premiumReqs": "高级请求",
    "tokens.lastUsed": "最后使用",
    "tokens.never": "从未",
    "tokens.quota": "配额",
    "tokens.quotaLoading": "获取中...",
    "tokens.quotaUnknown": "未知",
    "tokens.refreshQuota": "刷新配额",
    "tokens.poolStatus": "Token 池",
    "tokens.activeTokens": "活跃",
    "tokens.totalTokens": "总计",

    // Dashboard — token usage
    "dashboard.tokenUsage": "GitHub Token 用量",
  },
};

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "zh") return stored;
    return "en";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, locale);
  }, [locale]);

  const toggleLocale = useCallback(() => {
    setLocale((prev) => (prev === "en" ? "zh" : "en"));
  }, []);

  const t = useCallback(
    (key: string): string => {
      return translations[locale][key] ?? key;
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, toggleLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextType {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}
