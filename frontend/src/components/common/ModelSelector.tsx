import type { ModelObject } from "@/types/api";
import { useI18n } from "@/contexts/I18nContext";

interface ModelSelectorProps {
  models: ModelObject[];
  selectedModel: string;
  onSelect: (modelId: string) => void;
  loading: boolean;
  error: string | null;
}

/**
 * Dropdown selector for choosing a model from the available list.
 */
export default function ModelSelector({
  models,
  selectedModel,
  onSelect,
  loading,
  error,
}: ModelSelectorProps) {
  const { t } = useI18n();

  if (error) {
    return (
      <div className="text-danger text-xs px-3 py-1.5 bg-danger/8 border border-danger/20 rounded-md">
        {t("models.error")} {error}
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        value={selectedModel}
        onChange={(e) => onSelect(e.target.value)}
        disabled={loading}
        className="w-full bg-canvas border border-edge text-fg rounded-md pl-3 pr-8 py-1.5 text-xs
          focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
          disabled:opacity-50 disabled:cursor-not-allowed
          appearance-none cursor-pointer"
      >
        {loading ? (
          <option value="">{t("models.loading")}</option>
        ) : models.length === 0 ? (
          <option value="">{t("models.noModels")}</option>
        ) : (
          models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.id}
            </option>
          ))
        )}
      </select>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted"
      >
        <path
          fillRule="evenodd"
          d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
          clipRule="evenodd"
        />
      </svg>
    </div>
  );
}
