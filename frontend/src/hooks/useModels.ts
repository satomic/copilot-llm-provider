import { useState, useEffect, useCallback } from "react";
import type { ModelObject } from "@/types/api";
import { fetchModels } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";

interface UseModelsReturn {
  models: ModelObject[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook to fetch and cache available models from the API.
 * Automatically fetches on mount and exposes a refresh function.
 */
export function useModels(): UseModelsReturn {
  const { apiKey } = useAuth();
  const [models, setModels] = useState<ModelObject[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);

    fetchModels(apiKey)
      .then((data) => {
        setModels(data.data);
      })
      .catch((err: Error) => {
        setError(err.message);
        setModels([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [apiKey]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { models, loading, error, refresh };
}
