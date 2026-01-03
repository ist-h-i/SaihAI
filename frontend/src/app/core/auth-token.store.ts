import { Injectable, computed, signal } from '@angular/core';

import { AppConfigService } from './config/app-config.service';

const STORAGE_KEY = 'saihai.authToken';

@Injectable({ providedIn: 'root' })
export class AuthTokenStore {
  private readonly tokenSignal = signal<string | null>(null);
  readonly token = computed(() => this.tokenSignal());

  constructor(config: AppConfigService) {
    const stored = readStorage();
    const initial = stored ?? config.authToken;
    if (initial) this.tokenSignal.set(initial);
  }

  setToken(token: string | null): void {
    const normalized = normalizeString(token) ?? null;
    this.tokenSignal.set(normalized);
    writeStorage(normalized);
  }

  clearToken(): void {
    this.setToken(null);
  }
}

const readStorage = (): string | null => {
  if (typeof localStorage === 'undefined') return null;
  return normalizeString(localStorage.getItem(STORAGE_KEY)) ?? null;
};

const writeStorage = (value: string | null): void => {
  if (typeof localStorage === 'undefined') return;
  if (!value) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  localStorage.setItem(STORAGE_KEY, value);
};

const normalizeString = (value?: string | null): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length ? trimmed : undefined;
};
