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
      class="haisa-chat-line haisa-chat-line--speech haisa-speech-line pointer-events-auto"
      [class.haisa-chat-line--inline]="!showAvatar && !reserveAvatarSpace"
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
      } @else if (reserveAvatarSpace) {
        <div
          class="haisa-avatar haisa-avatar--placeholder"
          [style.width.px]="avatarSizePx()"
          [style.height.px]="avatarSizePx()"
          [style.border-radius.px]="avatarRadiusPx()"
          aria-hidden="true"
        ></div>
      }

      <div
        class="haisa-bubble ai haisa-speech-bubble border shadow-lg backdrop-blur"
        [class.haisa-bubble--compact]="compact"
        [class.haisa-bubble--tail]="showAvatar"
        [class.haisa-speech-bubble--highlight]="highlight"
        [class.haisa-tone-neutral]="tone === 'neutral'"
        [class.haisa-tone-info]="tone === 'info'"
        [class.haisa-tone-success]="tone === 'success'"
        [class.haisa-tone-warning]="tone === 'warning'"
        [class.haisa-tone-error]="tone === 'error'"
        [style.padding]="bubblePadding()"
      >
        <div class="haisa-bubble-header">
          @if (showAvatar || !reserveAvatarSpace) {
            <div class="haisa-speaker text-[10px] font-semibold tracking-wider">
              {{ speaker }}
            </div>
          }
          <div class="haisa-bubble-header-actions">
            @if (meta) {
              <div class="haisa-meta text-[10px] font-semibold">{{ meta }}</div>
            }
            @if (dismissible) {
              <button
                type="button"
                class="haisa-dismiss text-xs text-slate-200/70 hover:text-slate-100"
                (click)="dismissed.emit()"
                [attr.aria-label]="dismissLabel"
              >
                ×
              </button>
            }
          </div>
        </div>

        @if (title) {
          <div class="haisa-title-row">
            <div class="haisa-title text-sm font-semibold text-slate-100">{{ title }}</div>
            @if (tag) {
              <div class="haisa-tag text-[10px] font-semibold tracking-wider">{{ tag }}</div>
            }
          </div>
        }
        <div class="haisa-message mt-1 text-xs text-slate-200 whitespace-pre-line">
          {{ message }}
        </div>
      </div>
    </div>
  `,
})
export class HaisaSpeechComponent {
  @Input({ required: true }) message = '';
  @Input() title?: string;
  @Input() tag?: string;
  @Input() meta?: string;
  @Input() tone: HaisaSpeechTone = 'neutral';
  @Input() emotion?: HaisaEmotion;
  @Input() compact = false;
  @Input() showAvatar = true;
  @Input() reserveAvatarSpace = false;
  @Input() highlight = false;
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
    if (!this.showAvatar && !this.reserveAvatarSpace) return 0;
    return this.compact ? 0.5 : 0.75;
  }

  protected bubblePadding(): string {
    return this.compact ? '0.55rem 0.8rem' : '0.75rem 1rem';
  }
}
