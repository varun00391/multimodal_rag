import { useQuery } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { getHealth } from "../api/client";
import type { Theme } from "../lib/storage";
import { writeTheme } from "../lib/storage";

export function AppShell({
  children,
  theme,
  onTheme,
  filename,
}: {
  children: ReactNode;
  theme: Theme;
  onTheme: (theme: Theme) => void;
  filename?: string | null;
}) {
  const location = useLocation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  });

  return (
    <div className="app-shell">
      <div className="unsupported">Extract is built for a desktop review workspace.</div>
      <header className="app-header">
        <div className="app-header-left">
          <Link to="/" className="wordmark">
            <span className="wordmark-mark" />
            Extract
          </Link>
          <Link to="/" className={`nav-link${location.pathname === "/" ? " active" : ""}`}>
            Jobs
          </Link>
          {filename ? (
            <span className="breadcrumb" title={filename}>
              / {filename}
            </span>
          ) : null}
        </div>
        <div className="app-header-center" />
        <div className="app-header-right">
          <span className={`health-dot${health.data?.status === "ok" ? " ok" : ""}`} title="API health" />
          <button
            className="icon-btn"
            type="button"
            aria-label="Toggle theme"
            onClick={() => {
              const next = theme === "dark" ? "light" : "dark";
              writeTheme(next);
              onTheme(next);
            }}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>
      <main className="page">{children}</main>
    </div>
  );
}
