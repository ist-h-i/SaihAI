import { Component, inject } from '@angular/core';

import { Toast, ToastService, ToastTone } from './toast.service';

const TONE_CLASSES: Record<ToastTone, string> = {
  error: 'border-rose-500/40 bg-rose-500/10 text-rose-100',
  info: 'border-sky-500/40 bg-sky-500/10 text-sky-100',
  success: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100',
};

@Component({
  selector: 'app-toast-center',
  template: `
    <div
      class="pointer-events-none fixed top-4 right-4 z-50 flex max-w-sm flex-col gap-2"
      aria-live="polite"
    >
      @for (toast of service.toasts(); track toast.id) {
        <div [class]="toneClass(toast)">
          <div class="flex items-start gap-3">
            <div class="flex-1">
              @if (toast.title) {
                <div class="text-sm font-semibold">{{ toast.title }}</div>
              }
              <div class="text-xs text-slate-200">{{ toast.message }}</div>
            </div>
            <button
              type="button"
              class="text-xs text-slate-200/70 hover:text-slate-100"
              (click)="dismiss(toast.id)"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        </div>
      }
    </div>
  `,
})
export class ToastCenterComponent {
  protected readonly service = inject(ToastService);

  protected toneClass(toast: Toast): string {
    return `pointer-events-auto rounded-lg border px-4 py-3 shadow-lg backdrop-blur ${
      TONE_CLASSES[toast.tone]
    }`;
  }

  protected dismiss(id: string): void {
    this.service.dismiss(id);
  }
}
