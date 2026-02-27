import StatusBadge from "@/components/common/StatusBadge";

interface TopBarProps {
  title: string;
  connected: boolean;
  onMenuToggle: () => void;
}

/**
 * Top bar with mobile menu toggle, page title, and connection status.
 */
export default function TopBar({ title, connected, onMenuToggle }: TopBarProps) {

  return (
    <header className="h-12 bg-surface border-b border-edge flex items-center justify-between px-4 lg:px-5 sticky top-0 z-30">
      {/* Left: mobile menu toggle + title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="lg:hidden text-fg-muted hover:text-fg p-1 rounded-md hover:bg-overlay"
          aria-label="Toggle menu"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
          </svg>
        </button>
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
      </div>

      {/* Right: connection status */}
      <StatusBadge connected={connected} />
    </header>
  );
}
