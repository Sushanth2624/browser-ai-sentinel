import { useEffect, useState } from "react";

// Simple polling hook — refetch every intervalMs. No WebSocket infra for a single-user local
// tool, matching the project's "keep minimal" pattern elsewhere (see the plan).
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 8000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetcher()
        .then((result) => {
          if (!cancelled) {
            setData(result);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : String(err));
        });
    };
    load();
    const id = setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs]);

  return { data, error };
}
