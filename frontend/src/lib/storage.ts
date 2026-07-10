const SELECTION_KEY = "kgent_selection";

export interface ProviderSelection {
  provider: string;
  model: string;
}

export function loadSelection(): ProviderSelection | null {
  try {
    const raw = localStorage.getItem(SELECTION_KEY);
    return raw ? (JSON.parse(raw) as ProviderSelection) : null;
  } catch {
    return null;
  }
}

export function saveSelection(sel: ProviderSelection): void {
  localStorage.setItem(SELECTION_KEY, JSON.stringify(sel));
}

const THEME_KEY = "kgent_theme";

export type Theme = "dark" | "light";

export function loadTheme(): Theme {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === "dark" || raw === "light") return raw;
  } catch {
    /* ignore */
  }
  return "dark";
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* ignore */
  }
}

const ACTIVE_CONV_KEY = "kgent_active_conv";

export function loadActiveConv(): string | null {
  try {
    return localStorage.getItem(ACTIVE_CONV_KEY);
  } catch {
    return null;
  }
}

export function saveActiveConv(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACTIVE_CONV_KEY, id);
    else localStorage.removeItem(ACTIVE_CONV_KEY);
  } catch {
    /* ignore */
  }
}

const SIDEBAR_KEY = "kgent_sidebar_open";

export function loadSidebarOpen(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) !== "0";
  } catch {
    return true;
  }
}

export function saveSidebarOpen(open: boolean): void {
  try {
    localStorage.setItem(SIDEBAR_KEY, open ? "1" : "0");
  } catch {
    /* ignore */
  }
}
