import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-empty-state',
  template: `
    <div class="ui-empty">
      @if (kicker) {
        <div class="ui-kicker">{{ kicker }}</div>
      }
      <div class="text-base font-semibold text-slate-100">{{ title }}</div>
      <div class="mt-1 text-sm text-slate-400">{{ description }}</div>
      @if (primaryLabel || secondaryLabel) {
        <div class="mt-3 flex flex-wrap gap-2">
          @if (primaryLabel) {
            <button type="button" class="ui-button-primary" (click)="primary.emit()">
              {{ primaryLabel }}
            </button>
          }
          @if (secondaryLabel) {
            <button type="button" class="ui-button-secondary" (click)="secondary.emit()">
              {{ secondaryLabel }}
            </button>
          }
        </div>
      }
      <ng-content />
    </div>
  `,
})
export class EmptyStateComponent {
  @Input({ required: true }) title = '';
  @Input({ required: true }) description = '';
  @Input() kicker?: string;
  @Input() primaryLabel?: string;
  @Input() secondaryLabel?: string;

  @Output() primary = new EventEmitter<void>();
  @Output() secondary = new EventEmitter<void>();
}
