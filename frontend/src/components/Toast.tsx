import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface ToastState {
  message: string;
}

interface ToastContextValue {
  toast: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => undefined });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ToastState | null>(null);

  const toast = useCallback((message: string) => {
    setState({ message });
    window.setTimeout(() => setState(null), 3500);
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {state ? <div className="toast">{state.message}</div> : null}
    </ToastContext.Provider>
  );
}

export function useToast(): (message: string) => void {
  return useContext(ToastContext).toast;
}
