import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";

interface AuthContextType {
  token: string;
  username: string;
  isAuthenticated: boolean;
  login: (token: string, username: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = "copilot-llm-provider-token";
const USERNAME_KEY = "copilot-llm-provider-username";
const AUTH_FLAG_KEY = "copilot-llm-provider-authenticated";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string>(() => {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  });
  const [username, setUsername] = useState<string>(() => {
    return localStorage.getItem(USERNAME_KEY) ?? "";
  });
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return localStorage.getItem(AUTH_FLAG_KEY) === "true";
  });

  useEffect(() => {
    localStorage.setItem(TOKEN_KEY, token);
  }, [token]);

  useEffect(() => {
    localStorage.setItem(USERNAME_KEY, username);
  }, [username]);

  useEffect(() => {
    localStorage.setItem(AUTH_FLAG_KEY, String(isAuthenticated));
  }, [isAuthenticated]);

  const login = useCallback((newToken: string, newUsername: string) => {
    setToken(newToken);
    setUsername(newUsername);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    // Tell server to invalidate session
    if (token) {
      fetch("/api/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    setToken("");
    setUsername("");
    setIsAuthenticated(false);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(AUTH_FLAG_KEY);
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, username, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
