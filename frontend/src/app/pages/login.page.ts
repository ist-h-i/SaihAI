import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { HaisaSpeechComponent } from '../components/haisa-speech.component';
import { AuthClient } from '../core/auth-client';
import { AuthTokenStore } from '../core/auth-token.store';

@Component({
  imports: [HaisaSpeechComponent],
  template: `
    <div
      class="relative min-h-screen w-full overflow-hidden bg-slate-950 text-slate-100"
      style="
        --login-aurora: rgba(56, 189, 248, 0.22);
        --login-ember: rgba(251, 191, 36, 0.16);
        --login-mist: rgba(16, 185, 129, 0.18);
        --login-grid: rgba(148, 163, 184, 0.08);
      "
    >
      <div class="pointer-events-none absolute inset-0">
        <div class="absolute left-1/2 top-[-6rem] -translate-x-1/2">
          <div class="h-64 w-64 rounded-full bg-[var(--login-aurora)] blur-[120px] login-float"></div>
        </div>
        <div class="absolute bottom-[-9rem] right-[-6rem]">
          <div
            class="h-96 w-96 rounded-full bg-[var(--login-ember)] blur-[140px] login-float login-delay-2"
          ></div>
        </div>
        <div class="absolute bottom-[-7rem] left-[-5rem]">
          <div
            class="h-72 w-72 rounded-full bg-[var(--login-mist)] blur-[130px] login-float login-delay-1"
          ></div>
        </div>
        <div
          class="absolute inset-0 bg-[radial-gradient(circle_at_top,_var(--login-aurora),_transparent_55%)]"
        ></div>
        <div
          class="absolute inset-0 bg-[radial-gradient(circle_at_bottom_right,_var(--login-ember),_transparent_60%)]"
        ></div>
        <div
          class="absolute inset-0 opacity-40 bg-[linear-gradient(130deg,rgba(15,23,42,0.95)_0%,rgba(2,6,23,0.85)_55%,rgba(2,6,23,0.92)_100%)]"
        ></div>
        <div
          class="absolute inset-0 opacity-25"
          style="background-image: linear-gradient(transparent 32px, var(--login-grid) 33px), linear-gradient(90deg, transparent 32px, var(--login-grid) 33px); background-size: 64px 64px;"
        ></div>
      </div>

      <div class="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col items-center justify-center gap-12 px-6 py-12 lg:flex-row">
        <div class="order-2 w-full max-w-xl space-y-6 lg:order-1 login-reveal">
          <div class="inline-flex items-center gap-2 rounded-full border border-slate-800/70 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-300">
            Shadow Ops
            <span class="login-pulse h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]"></span>
          </div>

          <div>
            <div class="text-sm text-slate-400 font-semibold uppercase tracking-[0.4em]">SaihAI</div>
            <h1 class="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              意思決定の余白を、AIが守る
            </h1>
            <p class="mt-3 text-sm text-slate-300 max-w-lg">
              兆候だけを拾い、介入のカードを静かに並べます。あなたは最後の直感で合図を選ぶだけ。
            </p>
          </div>

          <div class="rounded-2xl border border-slate-800 bg-slate-950/50 p-4 overflow-hidden">
            <div class="mt-4 relative h-48 sm:h-44">
              <div class="login-illustration" aria-hidden="true">
                <div class="login-illustration-scene">
                  <div class="login-illustration-space">
                    <div class="login-illustration-stars login-illustration-stars--far"></div>
                    <div class="login-illustration-stars login-illustration-stars--near"></div>
                    <svg
                      class="login-illustration-constellation"
                      viewBox="0 0 260 160"
                      role="presentation"
                      aria-hidden="true"
                    >
                      <line class="login-illustration-constellation-line" x1="20" y1="30" x2="70" y2="20" />
                      <line class="login-illustration-constellation-line" x1="70" y1="20" x2="120" y2="36" />
                      <line class="login-illustration-constellation-line" x1="120" y1="36" x2="170" y2="24" />
                      <line class="login-illustration-constellation-line" x1="170" y1="24" x2="220" y2="50" />
                      <line class="login-illustration-constellation-line" x1="220" y1="50" x2="190" y2="90" />
                      <line class="login-illustration-constellation-line" x1="190" y1="90" x2="140" y2="110" />
                      <line class="login-illustration-constellation-line" x1="140" y1="110" x2="70" y2="100" />
                      <line class="login-illustration-constellation-line" x1="70" y1="100" x2="30" y2="80" />
                      <line class="login-illustration-constellation-line" x1="30" y1="80" x2="20" y2="30" />
                      <line class="login-illustration-constellation-line" x1="70" y1="20" x2="70" y2="100" />
                      <line class="login-illustration-constellation-line" x1="120" y1="36" x2="140" y2="110" />
                      <line class="login-illustration-constellation-line" x1="120" y1="36" x2="220" y2="50" />
                      <line class="login-illustration-constellation-line" x1="30" y1="80" x2="140" y2="110" />
                      <line class="login-illustration-constellation-line" x1="170" y1="24" x2="230" y2="20" />
                      <line class="login-illustration-constellation-line" x1="230" y1="20" x2="220" y2="50" />
                      <line class="login-illustration-constellation-line" x1="190" y1="90" x2="230" y2="90" />
                      <line class="login-illustration-constellation-line" x1="230" y1="90" x2="140" y2="110" />
                      <line class="login-illustration-constellation-line" x1="40" y1="120" x2="70" y2="100" />
                      <line class="login-illustration-constellation-line" x1="40" y1="120" x2="140" y2="110" />
                      <line class="login-illustration-constellation-line" x1="30" y1="80" x2="40" y2="120" />

                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--active login-illustration-constellation-node--cool login-illustration-constellation-node--fast" cx="20" cy="30" r="2.4" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--soft login-illustration-constellation-node--slow" cx="70" cy="20" r="2.2" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--active login-illustration-constellation-node--cool login-illustration-constellation-node--delay-1" cx="120" cy="36" r="2.3" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--warm login-illustration-constellation-node--delay-2" cx="170" cy="24" r="2.2" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--cool login-illustration-constellation-node--fast" cx="220" cy="50" r="2.3" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--active login-illustration-constellation-node--mint login-illustration-constellation-node--delay-2" cx="190" cy="90" r="2.4" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--mint login-illustration-constellation-node--slow" cx="140" cy="110" r="2.1" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--cool login-illustration-constellation-node--delay-3" cx="70" cy="100" r="2.3" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--soft login-illustration-constellation-node--delay-1" cx="30" cy="80" r="2.2" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--active login-illustration-constellation-node--warm login-illustration-constellation-node--fast" cx="230" cy="20" r="2.4" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--mint login-illustration-constellation-node--delay-3" cx="230" cy="90" r="2.2" />
                      <circle class="login-illustration-constellation-node login-illustration-constellation-node--soft login-illustration-constellation-node--slow" cx="40" cy="120" r="2.2" />
                    </svg>
                  </div>
                  <div class="login-illustration-platform"></div>
                  <div class="login-illustration-grid"></div>
                  <div class="login-illustration-ring"></div>
                  <div class="login-illustration-star">
                    <span class="login-illustration-star-glow"></span>
                    <span class="login-illustration-star-core"></span>
                    <span class="login-illustration-star-flare login-illustration-star-flare--one"></span>
                    <span class="login-illustration-star-flare login-illustration-star-flare--two"></span>
                    <span class="login-illustration-star-flare login-illustration-star-flare--three"></span>
                  </div>
                  <div class="login-illustration-stream login-illustration-stream--one"></div>
                  <div class="login-illustration-stream login-illustration-stream--two"></div>
                  <div class="login-illustration-stream login-illustration-stream--three"></div>
                  <span class="login-illustration-node login-illustration-node--one"></span>
                  <span class="login-illustration-node login-illustration-node--two"></span>
                  <span class="login-illustration-node login-illustration-node--three"></span>
                </div>
              </div>
            </div>
            <div class="mt-3 flex items-center gap-3 text-xs text-slate-400">
              <span class="flex items-center gap-2">
                <span class="login-pulse h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]"></span>
                Watchdog active
              </span>
              <span class="hidden sm:inline text-slate-500">/</span>
              <span class="hidden sm:inline">Signal map ready</span>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <div class="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Sentinel
              </div>
              <div class="mt-2 text-sm font-semibold text-slate-200">異常兆候を常時監視</div>
              <div class="mt-1 text-xs text-slate-400">必要な瞬間だけ通知します。</div>
            </div>
            <div class="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <div class="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                Intervention Deck
              </div>
              <div class="mt-2 text-sm font-semibold text-slate-200">介入プランを即時展開</div>
              <div class="mt-1 text-xs text-slate-400">選択肢を整えておきます。</div>
            </div>
          </div>

          <app-haisa-speech
            [tone]="'info'"
            [emotion]="'hope'"
            [message]="'今日も静かに見守っています。'"
            [compact]="true"
          />
        </div>

        <div class="order-1 w-full max-w-md lg:order-2">
          <div class="login-card rounded-2xl border border-slate-800/80 bg-slate-950/70 p-6 backdrop-blur sm:p-7 surface-panel">
            <div class="flex items-start justify-between gap-4">
              <div>
                <div class="text-xs text-slate-400 font-semibold uppercase tracking-[0.3em]">
                  SaihAI Access
                </div>
                <h1 class="mt-2 text-2xl font-extrabold tracking-tight">ログイン</h1>
              </div>
              <div
                class="h-11 w-11 rounded-xl border border-slate-700/70 bg-slate-900/60 grid place-items-center text-slate-200 font-black"
              >
                AI
              </div>
            </div>
            <div class="mt-3">
              <app-haisa-speech
                [tone]="'info'"
                [message]="'開発用アカウントでログインして、シャドー・ダッシュボードを開始します。'"
                [compact]="true"
                [showAvatar]="false"
              />
            </div>

            <div class="mt-6 space-y-4">
              <div>
                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                  User ID
                </label>
                <input
                  class="mt-2 w-full rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-sky-400/60 focus:ring-2 focus:ring-sky-400/20"
                  placeholder="例: tanaka"
                  [value]="userId()"
                  (input)="onUserInput($event)"
                />
              </div>

              <div>
                <label class="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                  Password
                </label>
                <input
                  type="password"
                  class="mt-2 w-full rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-sky-400/60 focus:ring-2 focus:ring-sky-400/20"
                  placeholder="dev password"
                  [value]="password()"
                  (input)="onPasswordInput($event)"
                />
              </div>
            </div>

            @if (error(); as err) {
              <div class="mt-4">
                <app-haisa-speech
                  [tone]="'error'"
                  [message]="err"
                  [compact]="true"
                  [showAvatar]="false"
                />
              </div>
            }

            <button
              type="button"
              class="mt-6 w-full rounded-xl bg-gradient-to-r from-indigo-500 via-sky-500 to-cyan-500 px-4 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(14,116,144,0.35)] hover:from-indigo-400 hover:via-sky-400 hover:to-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
              [disabled]="loading()"
              (click)="submit()"
            >
              {{ loading() ? '認証中...' : 'ログイン' }}
            </button>

            <div class="mt-4 flex items-center justify-between text-[11px] text-slate-500">
              <span>Dev environment</span>
              <span>Version alpha</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class LoginPage {
  private readonly authClient = inject(AuthClient);
  private readonly tokenStore = inject(AuthTokenStore);
  private readonly router = inject(Router);

  protected readonly userId = signal('');
  protected readonly password = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly loading = signal(false);

  protected onUserInput(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    this.userId.set(target.value);
  }

  protected onPasswordInput(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    this.password.set(target.value);
  }

  protected async submit(): Promise<void> {
    if (!this.userId().trim() || !this.password().trim()) {
      this.error.set('ユーザーIDとパスワードを入力してください');
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    try {
      const response = await firstValueFrom(
        this.authClient.login({ userId: this.userId().trim(), password: this.password().trim() })
      );
      this.tokenStore.setToken(response.access_token);
      const redirect = this.router.parseUrl(this.router.url).queryParams['redirect'] || '/dashboard';
      await this.router.navigateByUrl(redirect);
    } catch (e) {
      if (e instanceof HttpErrorResponse) {
        const detail =
          typeof e.error === 'string'
            ? e.error
            : e.error && typeof e.error === 'object' && 'detail' in e.error
              ? String((e.error as { detail?: string }).detail)
              : null;
        this.error.set(detail || 'ログインに失敗しました');
      } else {
        const message = e instanceof Error ? e.message : 'ログインに失敗しました';
        this.error.set(message);
      }
    } finally {
      this.loading.set(false);
    }
  }
}
