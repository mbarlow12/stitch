import { useEffect, useState } from "react";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import ColophonPanel from "./ColophonPanel";
import { useConfig } from "../config/useConfig";

const WARMING_DELAY_MS = 2000;

function useIsWarmingUp(delayMs = WARMING_DELAY_MS) {
  const queryClient = useQueryClient();
  const isPending = useIsFetching() > 0;
  const [hasStalled, setHasStalled] = useState(false);

  const hasServerAnswered = queryClient
    .getQueryCache()
    .getAll()
    .some((query) => query.state.status === "success");

  useEffect(() => {
    if (!isPending) {
      return undefined;
    }

    const timer = setTimeout(() => setHasStalled(true), delayMs);

    return () => {
      clearTimeout(timer);
      setHasStalled(false);
    };
  }, [isPending, delayMs]);

  return isPending && hasStalled && !hasServerAnswered;
}

function normalizeEnvLabel(value) {
  return (value ?? "").trim();
}

function isProductionEnv(label) {
  const normalized = label.toLowerCase();
  return normalized === "production" || normalized === "prod";
}

function getBannerAppearance(label) {
  const normalized = label.toLowerCase();

  if (normalized === "main") {
    return {
      className: "bg-green-500 text-white",
    };
  } else if (normalized === "next") {
    return {
      className: "bg-yellow-500 text-white",
    };
  } else if (normalized.startsWith("hotfix")) {
    return {
      className: "bg-orange-500 text-white",
    };
  } else if (normalized.startsWith("develop")) {
    return {
      className: "bg-red-500 text-white",
    };
  } else if (normalized.startsWith("pr-")) {
    return {
      className: "bg-indigo-500 text-white",
    };
  } else {
    return {
      className: "bg-pink-500 text-white",
    };
  }
}

export default function EnvironmentBanner() {
  const config = useConfig();
  const [isOpen, setIsOpen] = useState(false);
  const isWarmingUp = useIsWarmingUp();
  const label = normalizeEnvLabel(config.appEnv);
  const bannerAppearance = getBannerAppearance(label);

  if (!label || isProductionEnv(label)) {
    return null;
  }

  return (
    <div className="sticky top-0 z-50 w-full">
      <div
        className={bannerAppearance.className}
        style={bannerAppearance.style}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-2 text-sm font-medium sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <span className="min-w-0 truncate rounded-md bg-bluespruce px-3 py-1 shadow-sm ring-1 ring-white/20">
              {label.toUpperCase()} Environment
            </span>

            {isWarmingUp ? (
              <span role="status" className="min-w-0 truncate font-normal">
                Server is waking up — this can take a few seconds.
              </span>
            ) : null}
          </div>

          <button
            type="button"
            onClick={() => setIsOpen((value) => !value)}
            className="shrink-0 rounded-md border border-white/30 bg-bluespruce px-2.5 py-1 text-sm font-semibold shadow-sm transition-colors hover:bg-rmiblue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2"
            aria-expanded={isOpen}
            aria-controls="frontend-diagnostics-panel"
          >
            {isOpen ? "Hide diagnostics" : "Show diagnostics"}
          </button>
        </div>
      </div>

      {isOpen ? (
        <div id="frontend-diagnostics-panel">
          <ColophonPanel diagnosticsOpen={isOpen} />
        </div>
      ) : null}
    </div>
  );
}
