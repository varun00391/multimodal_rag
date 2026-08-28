import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ToastProvider } from "./components/Toast";
import { readTheme, type Theme } from "./lib/storage";
import { JobReview } from "./routes/JobReview";
import { JobsHome } from "./routes/JobsHome";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  const [theme, setTheme] = useState<Theme>(() => {
    const initial = readTheme();
    document.documentElement.dataset.theme = initial;
    return initial;
  });
  const [filename, setFilename] = useState<string | null>(null);

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AppShell theme={theme} onTheme={setTheme} filename={filename}>
            <Routes>
              <Route path="/" element={<JobsHome />} />
              <Route path="/jobs/:jobId" element={<JobReview onFilename={setFilename} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AppShell>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
