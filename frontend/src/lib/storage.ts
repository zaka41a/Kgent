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
