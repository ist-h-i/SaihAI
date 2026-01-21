import { Injectable, computed, signal } from '@angular/core';

export type ThemeMode = 'dark' | 'light';

const STORAGE_KEY = 'saihai.theme';
const MEDIA_QUERY = '(prefers-color-scheme: dark)';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly themeSignal = signal<ThemeMode>('dark');
  readonly theme = computed(() => this.themeSignal());

  private hasStoredPreference = false;
  private mediaQueryList: MediaQueryList | null = null;
  private readonly mediaListener = (event: MediaQueryListEvent) => {
    if (this.hasStoredPreference) return;
    this.applyTheme(event.matches ? 'dark' : 'light');
  };

  init(): void {
    const storedTheme = readStoredTheme();
    if (storedTheme) {
      this.hasStoredPreference = true;
      this.applyTheme(storedTheme);
      return;
    }

    if (typeof window === 'undefined') return;
    const mql = window.matchMedia?.(MEDIA_QUERY);
    this.mediaQueryList = mql ?? null;
    this.applyTheme(mql?.matches ? 'dark' : 'light');

    if (mql && typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', this.mediaListener);
    }
  }

  toggle(): void {
    this.setTheme(this.theme() === 'dark' ? 'light' : 'dark');
  }

  setTheme(theme: ThemeMode): void {
    const normalized = normalizeTheme(theme);
    if (!normalized) return;
    this.hasStoredPreference = true;
    writeStoredTheme(normalized);
    this.applyTheme(normalized);

    const mql = this.mediaQueryList;
    if (mql && typeof mql.removeEventListener === 'function') {
      mql.removeEventListener('change', this.mediaListener);
    }
  }

  private applyTheme(theme: ThemeMode): void {
    this.themeSignal.set(theme);
    if (typeof document === 'undefined') return;
    document.documentElement.setAttribute('data-theme', theme);
  }
}

const normalizeTheme = (value: unknown): ThemeMode | undefined => {
  if (value === 'dark' || value === 'light') return value;
  return undefined;
};

const readStoredTheme = (): ThemeMode | undefined => {
  if (typeof localStorage === 'undefined') return undefined;
  try {
    return normalizeTheme(localStorage.getItem(STORAGE_KEY));
  } catch {
    return undefined;
  }
};

const writeStoredTheme = (value: ThemeMode): void => {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // ignore storage failures (e.g. blocked, quota exceeded)
  }
};
