"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchDashboard } from "./data";
import type { DashboardData } from "./types";

interface DashboardState {
  data: DashboardData | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function useDashboard(): DashboardState {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    fetchDashboard(controller.signal)
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active || (reason instanceof DOMException && reason.name === "AbortError")) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Unknown error.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [attempt]);

  return { data, error, loading, reload };
}
