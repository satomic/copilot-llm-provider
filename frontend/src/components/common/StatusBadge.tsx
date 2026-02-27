import { useI18n } from "@/contexts/I18nContext";

interface StatusBadgeProps {
  connected: boolean;
}

/**
 * Small inline status indicator with a colored dot and text.
 */
export default function StatusBadge({ connected }: StatusBadgeProps) {
  const { t } = useI18n();

  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span
        className={`h-2 w-2 rounded-full ${
          connected ? "bg-success" : "bg-danger"
        }`}
      />
      <span className={connected ? "text-success" : "text-danger"}>
        {connected ? t("status.connected") : t("status.disconnected")}
      </span>
    </span>
  );
}
