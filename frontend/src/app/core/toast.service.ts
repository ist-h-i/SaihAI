import { Injectable, signal } from '@angular/core';

export type ToastTone = 'error' | 'info' | 'success';

export interface Toast {
  id: string;
  tone: ToastTone;
  title?: string;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<Toast[]>([]);
  private counter = 0;
  private readonly timeouts = new Map<string, number>();

  show(toast: Omit<Toast, 'id'>, options?: { durationMs?: number }): void {
    const id = `toast-${++this.counter}`;
    this.toasts.update((current) => [...current, { ...toast, id }]);

    const durationMs = options?.durationMs ?? 5000;
    if (typeof window !== 'undefined') {
      const timeoutId = window.setTimeout(() => this.dismiss(id), durationMs);
      this.timeouts.set(id, timeoutId);
    }
  }

  error(message: string, title = 'APIエラー'): void {
    this.show({ tone: 'error', title, message });
  }

  dismiss(id: string): void {
    const timeoutId = this.timeouts.get(id);
    if (timeoutId && typeof window !== 'undefined') {
      window.clearTimeout(timeoutId);
    }
    this.timeouts.delete(id);
    this.toasts.update((current) => current.filter((toast) => toast.id !== id));
  }
}
