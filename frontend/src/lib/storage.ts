const THEME_KEY = "extract-theme";
const JOBS_KEY = "extract-jobs";
const NAMES_KEY = "extract-job-names";
const DB_NAME = "extract-pdfs";
const STORE = "pdfs";
const MAX_PDFS = 20;

export type Theme = "dark" | "light";

export function readTheme(): Theme {
  const value = localStorage.getItem(THEME_KEY);
  return value === "light" ? "light" : "dark";
}

export function writeTheme(theme: Theme): void {
  localStorage.setItem(THEME_KEY, theme);
  document.documentElement.dataset.theme = theme;
}

export function rememberJob(jobId: string, filename: string): void {
  const jobs = readJobIds().filter((id) => id !== jobId);
  jobs.unshift(jobId);
  localStorage.setItem(JOBS_KEY, JSON.stringify(jobs.slice(0, 100)));
  const names = readJobNames();
  names[jobId] = filename;
  localStorage.setItem(NAMES_KEY, JSON.stringify(names));
}

export function readJobIds(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(JOBS_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function readJobNames(): Record<string, string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(NAMES_KEY) ?? "{}") as unknown;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "jobId" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function savePdf(jobId: string, blob: Blob): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ jobId, blob, savedAt: Date.now() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  await prunePdfs(db);
  db.close();
}

export async function loadPdf(jobId: string): Promise<Blob | null> {
  const db = await openDb();
  const record = await new Promise<{ blob: Blob } | undefined>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).get(jobId);
    request.onsuccess = () => resolve(request.result as { blob: Blob } | undefined);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return record?.blob ?? null;
}

async function prunePdfs(db: IDBDatabase): Promise<void> {
  const records = await new Promise<Array<{ jobId: string; savedAt: number }>>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result as Array<{ jobId: string; savedAt: number }>);
    request.onerror = () => reject(request.error);
  });
  if (records.length <= MAX_PDFS) return;
  const extra = [...records].sort((a, b) => a.savedAt - b.savedAt).slice(0, records.length - MAX_PDFS);
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    for (const item of extra) {
      tx.objectStore(STORE).delete(item.jobId);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
