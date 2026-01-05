import { Component, EventEmitter, Input, Output } from '@angular/core';

export type HaisaSpeechTone = 'neutral' | 'info' | 'success' | 'warning' | 'error';

export type HaisaEmotion =
  | 'standard'
  | 'hope'
  | 'joy'
  | 'relief'
  | 'anxiety'
  | 'energy'
  | 'effort'
  | 'haste'
  | 'explosion';

const HAISA_ASSET_DIR = '/assets/haisaikun';

const HAISA_IMAGE_BY_EMOTION: Record<HaisaEmotion, string> = {
  standard: 'standard.png',
  hope: 'hope.png',
  joy: 'joy.png',
  relief: 'relief.png',
  anxiety: 'anxiety.png',
  energy: 'energy.png',
  effort: 'effort.png',
  haste: 'haste.png',
  explosion: 'explosion.png',
};

const DEFAULT_EMOTION_BY_TONE: Record<HaisaSpeechTone, HaisaEmotion> = {
  neutral: 'standard',
  info: 'hope',
  success: 'relief',
  warning: 'haste',
  error: 'anxiety',
};

@Component({
  selector: 'app-haisa-speech',
  template: `
    <div
      class="haisa-chat-line haisa-speech-line pointer-events-auto"
      [style.gap.rem]="lineGapRem()"
    >
      @if (showAvatar) {
        <div
          class="haisa-avatar"
          [style.width.px]="avatarSizePx()"
          [style.height.px]="avatarSizePx()"
          [style.border-radius.px]="avatarRadiusPx()"
          aria-hidden="true"
        >
          <img [src]="avatarSrc()" alt="" class="haisa-avatar-image" aria-hidden="true" />
        </div>
      }

      <div
        class="haisa-bubble ai border shadow-lg backdrop-blur"
        [style.padding]="bubblePadding()"
        [class.border-slate-700/60]="tone === 'neutral'"
        [class.border-sky-500/40]="tone === 'info'"
        [class.border-emerald-500/40]="tone === 'success'"
        [class.border-amber-500/40]="tone === 'warning'"
        [class.border-rose-500/40]="tone === 'error'"
      >
        <div class="flex items-start gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-3">
              <div class="text-[10px] text-slate-400 font-semibold tracking-wider">
                {{ speaker }}
              </div>
              @if (meta) {
                <div class="text-[10px] text-slate-400 font-semibold">{{ meta }}</div>
              }
            </div>
            @if (title) {
              <div class="mt-1 text-sm font-semibold text-slate-100">{{ title }}</div>
            }
            <div class="mt-1 text-xs text-slate-200 whitespace-pre-line">{{ message }}</div>
          </div>
          @if (dismissible) {
            <button
              type="button"
              class="text-xs text-slate-200/70 hover:text-slate-100"
              (click)="dismissed.emit()"
              [attr.aria-label]="dismissLabel"
            >
              ×
            </button>
          }
        </div>
      </div>
    </div>
  `,
})
export class HaisaSpeechComponent {
  @Input({ required: true }) message = '';
  @Input() title?: string;
  @Input() meta?: string;
  @Input() tone: HaisaSpeechTone = 'neutral';
  @Input() emotion?: HaisaEmotion;
  @Input() compact = false;
  @Input() showAvatar = true;
  @Input() dismissible = false;
  @Input() dismissLabel = '閉じる';
  @Input() speaker = 'ハイサイくん';

  @Output() dismissed = new EventEmitter<void>();

  protected avatarSrc(): string {
    const emotion = this.emotion ?? DEFAULT_EMOTION_BY_TONE[this.tone] ?? 'standard';
    const file = HAISA_IMAGE_BY_EMOTION[emotion] ?? HAISA_IMAGE_BY_EMOTION.standard;
    return `${HAISA_ASSET_DIR}/${file}`;
  }

  protected avatarSizePx(): number {
    return this.compact ? 56 : 80;
  }

  protected avatarRadiusPx(): number {
    return this.compact ? 18 : 22;
  }

  protected lineGapRem(): number {
    if (!this.showAvatar) return 0;
    return this.compact ? 0.5 : 0.75;
  }

  protected bubblePadding(): string {
    return this.compact ? '0.55rem 0.8rem' : '0.75rem 1rem';
  }
}
