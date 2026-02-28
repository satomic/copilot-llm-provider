import { useState, useEffect, type ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { healthCheck } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";

interface LayoutProps {
  title: string;
  children: ReactNode;
}

/**
 * Main layout wrapper used by all authenticated pages.
 * Provides sidebar navigation, top bar, and the content area.
 */
export default function Layout({ title, children }: LayoutProps) {
  const { token } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [connected, setConnected] = useState(false);

  // Periodically check server connectivity
  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const ok = await healthCheck(token);
      if (!cancelled) setConnected(ok);
    };

    check();
    const interval = setInterval(check, 15000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token]);

  return (
    <div className="flex h-screen bg-canvas overflow-hidden">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          title={title}
          connected={connected}
          onMenuToggle={() => setSidebarOpen((prev) => !prev)}
        />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
