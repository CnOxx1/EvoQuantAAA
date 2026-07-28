const KEY = "evoquant.settings.v2";

export type Settings = {
  apiBase: string;
  token: string;
  asOf: string;
  accountId: string;
  env: "research" | "paper" | "live";
};

export const DEFAULT_SETTINGS: Settings = {
  apiBase: "http://127.0.0.1:8088",
  token: "",
  asOf: new Date().toISOString().slice(0, 10),
  accountId: "paper_default",
  env: "paper",
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(s: Settings) {
  localStorage.setItem(KEY, JSON.stringify(s));
}
