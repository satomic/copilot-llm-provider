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

    // Settings page
    "settings.title": "Settings",
    "settings.connectionInfo": "Connection Info",
    "settings.authMode": "Auth Mode:",
    "settings.apiKeyAuth": "API Key",
    "settings.noAuth": "No Authentication",
    "settings.apiKeyLabel": "API Key:",
    "settings.endpoints": "API Endpoints",
    "settings.openaiChat": "OpenAI Chat Completions",
    "settings.anthropicMessages": "Anthropic Messages",
    "settings.modelsList": "Models List",
    "settings.healthCheck": "Health Check",
    "settings.copy": "Copy",
    "settings.copied": "Copied!",
    "settings.usageExamples": "Usage Examples",
    "settings.curl": "cURL",
    "settings.python": "Python (OpenAI SDK)",
    "settings.nodejs": "Node.js (OpenAI SDK)",
  },
  zh: {
    // App
    "app.title": "Copilot LLM Provider",
    "app.subtitle": "LLM API 服务器",

    // Navigation
    "nav.dashboard": "仪表盘",
    "nav.playground": "聊天测试",
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

    // Settings page
    "settings.title": "设置",
    "settings.connectionInfo": "连接信息",
    "settings.authMode": "认证模式：",
    "settings.apiKeyAuth": "API 密钥",
    "settings.noAuth": "无需认证",
    "settings.apiKeyLabel": "API 密钥：",
    "settings.endpoints": "API 端点",
    "settings.openaiChat": "OpenAI 聊天补全",
    "settings.anthropicMessages": "Anthropic 消息",
    "settings.modelsList": "模型列表",
    "settings.healthCheck": "健康检查",
    "settings.copy": "复制",
    "settings.copied": "已复制！",
    "settings.usageExamples": "使用示例",
    "settings.curl": "cURL",
    "settings.python": "Python (OpenAI SDK)",
    "settings.nodejs": "Node.js (OpenAI SDK)",
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
