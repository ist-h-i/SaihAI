import { Component, inject } from '@angular/core';

import { HaisaSpeechComponent } from '../components/haisa-speech.component';
import { ToastService } from './toast.service';

@Component({
  selector: 'app-toast-center',
  imports: [HaisaSpeechComponent],
  template: `
    <div
      class="pointer-events-none fixed top-4 right-4 z-50 flex max-w-sm flex-col gap-2"
      aria-live="polite"
    >
      @for (toast of service.toasts(); track toast.id) {
        <app-haisa-speech
          [tone]="toast.tone"
          [title]="toast.title"
          [message]="toast.message"
          [compact]="true"
          [showAvatar]="false"
          [dismissible]="true"
          [dismissLabel]="'閉じる'"
          (dismissed)="dismiss(toast.id)"
        />
      }
    </div>
  `,
})
export class ToastCenterComponent {
  protected readonly service = inject(ToastService);

  protected dismiss(id: string): void {
    this.service.dismiss(id);
  }
}
