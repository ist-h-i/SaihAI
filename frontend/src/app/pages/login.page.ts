import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { AuthClient } from '../core/auth-client';
import { AuthTokenStore } from '../core/auth-token.store';

@Component({
  template: `
    <div class="min-h-screen w-full bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div class="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-950/70 p-6">
        <div class="text-sm text-slate-400 font-bold uppercase tracking-wider">SaihAI</div>
        <h1 class="mt-2 text-2xl font-extrabold tracking-tight">ログイン</h1>
        <p class="mt-2 text-sm text-slate-300">
          開発用アカウントでログインしてダッシュボードを開始します。
        </p>

        <div class="mt-6">
          <label class="text-xs text-slate-400 font-semibold">User ID</label>
          <input
            class="mt-2 w-full rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 outline-none focus:border-indigo-500/60"
            placeholder="例: tanaka"
            [value]="userId()"
            (input)="onUserInput($event)"
          />
        </div>

        <div class="mt-4">
          <label class="text-xs text-slate-400 font-semibold">Password</label>
          <input
            type="password"
            class="mt-2 w-full rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 outline-none focus:border-indigo-500/60"
            placeholder="dev password"
            [value]="password()"
            (input)="onPasswordInput($event)"
          />
        </div>

        @if (error(); as err) {
          <div class="mt-3 text-sm text-rose-300">{{ err }}</div>
        }

        <button
          type="button"
          class="mt-6 w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold hover:bg-indigo-500 disabled:opacity-60"
          [disabled]="loading()"
          (click)="submit()"
        >
          ログイン
        </button>
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
