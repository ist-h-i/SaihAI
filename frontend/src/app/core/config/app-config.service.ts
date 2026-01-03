import { Injectable } from '@angular/core';

import type { LogLevel } from '../logger.service';

export interface AppConfig {
  apiBaseUrl: string;
  authToken?: string | null;
  logLevel?: LogLevel;
  logToServer?: boolean;
  serverLogLevel?: LogLevel;
}

const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1';
const RUNTIME_CONFIG_PATH = '/assets/runtime-config.json';

@Injectable({ providedIn: 'root' })
export class AppConfigService {
  private config: AppConfig = { apiBaseUrl: DEFAULT_API_BASE_URL, authToken: null };

  get apiBaseUrl(): string {
    return this.config.apiBaseUrl;
  }

  get authToken(): string | null {
    return this.config.authToken ?? null;
  }

  get logLevel(): LogLevel | undefined {
    return this.config.logLevel;
  }

  get logToServer(): boolean {
    return this.config.logToServer ?? false;
  }

  get serverLogLevel(): LogLevel | undefined {
    return this.config.serverLogLevel;
  }

  async load(): Promise<void> {
    const assetConfig = await this.readAssetConfig();
    const windowConfig = this.readWindowConfig();
    this.config = normalizeConfig({
      ...this.config,
      ...assetConfig,
      ...windowConfig,
    });
  }

  private readWindowConfig(): Partial<AppConfig> {
    const config = (globalThis as { __APP_CONFIG__?: Partial<AppConfig> }).__APP_CONFIG__;
    if (!config || typeof config !== 'object') return {};
    return config;
  }

  private async readAssetConfig(): Promise<Partial<AppConfig>> {
    try {
      const response = await fetch(RUNTIME_CONFIG_PATH, { cache: 'no-store' });
      if (!response.ok) return {};
      const data = await response.json();
      if (!data || typeof data !== 'object') return {};
      return data as Partial<AppConfig>;
    } catch {
      return {};
    }
  }
}

const normalizeConfig = (config: AppConfig): AppConfig => {
  const apiBaseUrl = normalizeString(config.apiBaseUrl) ?? DEFAULT_API_BASE_URL;
  const authToken = normalizeString(config.authToken ?? undefined) ?? null;
  const logLevel = normalizeLogLevel(config.logLevel);
  const serverLogLevel = normalizeLogLevel(config.serverLogLevel);
  const logToServer = normalizeBoolean(config.logToServer);
  return {
    apiBaseUrl: apiBaseUrl.replace(/\/+$/, ''),
    authToken,
    logLevel,
    serverLogLevel,
    logToServer,
  };
};

const normalizeString = (value?: string | null): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length ? trimmed : undefined;
};

const normalizeLogLevel = (value: unknown): LogLevel | undefined => {
  if (typeof value !== 'string') return undefined;
  const lowered = value.trim().toLowerCase();
  if (lowered === 'debug' || lowered === 'info' || lowered === 'warn' || lowered === 'error') {
    return lowered;
  }
  return undefined;
};

const normalizeBoolean = (value: unknown): boolean | undefined => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    const lowered = value.trim().toLowerCase();
    if (lowered === 'true' || lowered === '1' || lowered === 'yes') return true;
    if (lowered === 'false' || lowered === '0' || lowered === 'no') return false;
  }
  return undefined;
};
