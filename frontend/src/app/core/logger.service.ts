import { Injectable } from '@angular/core';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

@Injectable({ providedIn: 'root' })
export class LoggerService {
  private minLevel: LogLevel = 'info';
  private serverEnabled = false;
  private serverMinLevel: LogLevel = 'error';
  private serverEndpoint: string | null = null;

  setMinLevel(level: LogLevel): void {
    this.minLevel = level;
  }

  configureServer(options: {
    enabled: boolean;
    apiBaseUrl: string;
    minLevel?: LogLevel;
    endpoint?: string;
  }): void {
    this.serverEnabled = options.enabled;
    this.serverMinLevel = options.minLevel ?? 'error';
    this.serverEndpoint = options.endpoint ?? `${options.apiBaseUrl.replace(/\/+$/, '')}/logs/frontend`;
  }

  debug(message: string, context?: Record<string, unknown>): void {
    this.write('debug', message, context);
  }

  info(message: string, context?: Record<string, unknown>): void {
    this.write('info', message, context);
  }

  warn(message: string, context?: Record<string, unknown>): void {
    this.write('warn', message, context);
  }

  error(message: string, context?: Record<string, unknown>): void {
    this.write('error', message, context);
  }

  private write(level: LogLevel, message: string, context?: Record<string, unknown>): void {
    if (LEVEL_ORDER[level] < LEVEL_ORDER[this.minLevel]) return;

    const payload = context ? [message, context] : [message];
    switch (level) {
      case 'debug':
        console.debug(...payload);
        break;
      case 'info':
        console.info(...payload);
        break;
      case 'warn':
        console.warn(...payload);
        break;
      case 'error':
        console.error(...payload);
        break;
      default:
        console.log(...payload);
    }

    this.sendToServer(level, message, context);
  }

  private sendToServer(level: LogLevel, message: string, context?: Record<string, unknown>): void {
    if (!this.serverEnabled) return;
    if (!this.serverEndpoint) return;
    if (LEVEL_ORDER[level] < LEVEL_ORDER[this.serverMinLevel]) return;
    if (typeof navigator === 'undefined') return;

    const payload = {
      level,
      message: message.slice(0, 2000),
      context: context ? safeJsonValue(context) : undefined,
      timestamp: new Date().toISOString(),
      url: typeof location !== 'undefined' ? location.href : undefined,
      userAgent: navigator.userAgent,
    };
    const body = JSON.stringify(payload);

    try {
      if (typeof navigator.sendBeacon === 'function') {
        const blob = new Blob([body], { type: 'application/json' });
        if (navigator.sendBeacon(this.serverEndpoint, blob)) return;
      }
    } catch {
      // ignore
    }

    void fetch(this.serverEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => undefined);
  }
}

const safeJsonValue = (value: unknown): unknown => {
  try {
    return JSON.parse(JSON.stringify(value)) as unknown;
  } catch {
    return String(value);
  }
};
