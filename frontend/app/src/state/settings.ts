const STORAGE_KEY = "evoquant.console.settings.v1";

export type EnvMode = "research" | "paper" | "live";

export type Settings = {
  apiBase: string;
  apiToken: string;
  accountId: string;
  env: EnvMode;
  asOf: string;
};

export const DEFAULT_SETTINGS: Settings = {
  apiBase: "http://127.0.0.1:8080",
  apiToken: "",
  accountId: "paper_default",
  env: "paper",
  asOf: new Date().toISOString().slice(0, 10),
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(next: Settings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}
