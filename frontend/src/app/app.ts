import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Title } from '@angular/platform-browser';
import { filter, firstValueFrom } from 'rxjs';

import { ToastCenterComponent } from './core/toast-center.component';
import { ApiClient } from './core/api-client';
import { ToastService } from './core/toast.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ToastCenterComponent],
  template: `
    @if (isLoginRoute()) {
      <router-outlet />
    } @else {
      <div class="min-h-[100dvh] w-full overflow-hidden bg-slate-950 text-slate-100 flex">
        <aside
          id="desktop-nav"
          class="hidden lg:flex shrink-0 bg-slate-950 border-slate-800 flex-col gap-6 overflow-hidden transition-[width,padding] duration-300 ease-out"
          [style.width.px]="desktopNavOpen() ? 260 : 72"
          [style.padding]="desktopNavOpen() ? '1.25rem' : '0.75rem'"
          [style.borderRightWidth.px]="1"
        >
          <div
            class="flex items-center gap-3"
            [class.flex-col]="!desktopNavOpen()"
            [class.items-center]="!desktopNavOpen()"
            [class.gap-2]="!desktopNavOpen()"
          >
            <div
              class="h-10 w-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 grid place-items-center"
            >
              <span class="font-black text-indigo-300">AI</span>
            </div>
            @if (desktopNavOpen()) {
              <div class="leading-tight">
                <div class="text-lg font-extrabold tracking-tight">
                  Saih<span class="text-fuchsia-400">AI</span>
                  <span class="ml-1 text-xs text-slate-500 font-semibold">v2</span>
                </div>
                <div class="text-[11px] text-slate-400">99% autonomy, 1% intuition</div>
              </div>
            }
            <button
              type="button"
              class="h-8 w-8 rounded-lg border border-slate-800 bg-white/5 grid place-items-center text-slate-200 hover:bg-white/10"
              [class.ml-auto]="desktopNavOpen()"
              (click)="toggleDesktopNav()"
              [attr.aria-label]="desktopNavOpen() ? 'Collapse navigation' : 'Expand navigation'"
            >
              <svg
                class="h-4 w-4 transition-transform duration-200"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                [style.transform]="desktopNavOpen() ? 'rotate(0deg)' : 'rotate(180deg)'"
              >
                <path d="M12.5 4.5l-5 5 5 5" />
              </svg>
            </button>
          </div>

          <div>
            @if (desktopNavOpen()) {
              <div class="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-2 px-3">
                Cockpit
              </div>
            }
            <a
              routerLink="/dashboard"
              routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
              class="group flex items-center gap-3 rounded-lg border border-transparent text-slate-300 hover:bg-white/5 py-2"
              [class.px-3]="desktopNavOpen()"
              [class.px-2]="!desktopNavOpen()"
              [class.justify-center]="!desktopNavOpen()"
            >
              <span
                class="h-8 w-8 rounded-lg border border-slate-800 bg-white/5 grid place-items-center text-slate-200 group-hover:bg-white/10"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="3" y="3" width="6" height="6" rx="1"></rect>
                  <rect x="11" y="3" width="6" height="4" rx="1"></rect>
                  <rect x="11" y="9" width="6" height="8" rx="1"></rect>
                  <rect x="3" y="11" width="6" height="6" rx="1"></rect>
                </svg>
              </span>
              @if (desktopNavOpen()) {
                <span class="text-sm">経営ダッシュボード</span>
              }
            </a>
            <a
              routerLink="/simulator"
              routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
              class="group flex items-center gap-3 rounded-lg border border-transparent text-slate-300 hover:bg-white/5 py-2"
              [class.px-3]="desktopNavOpen()"
              [class.px-2]="!desktopNavOpen()"
              [class.justify-center]="!desktopNavOpen()"
            >
              <span
                class="h-8 w-8 rounded-lg border border-slate-800 bg-white/5 grid place-items-center text-slate-200 group-hover:bg-white/10"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="10" cy="10" r="5.5"></circle>
                  <path d="M10 2.5v3M10 14.5v3M2.5 10h3M14.5 10h3"></path>
                </svg>
              </span>
              @if (desktopNavOpen()) {
                <span class="text-sm">戦術シミュレーター</span>
              }
            </a>
            <a
              routerLink="/saved-plans"
              routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
              class="group flex items-center gap-3 rounded-lg border border-transparent text-slate-300 hover:bg-white/5 py-2"
              [class.px-3]="desktopNavOpen()"
              [class.px-2]="!desktopNavOpen()"
              [class.justify-center]="!desktopNavOpen()"
            >
              <span
                class="h-8 w-8 rounded-lg border border-slate-800 bg-white/5 grid place-items-center text-slate-200 group-hover:bg-white/10"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M6 3.5h8a1 1 0 0 1 1 1v12l-5-2.5L5 16.5v-12a1 1 0 0 1 1-1z" />
                </svg>
              </span>
              @if (desktopNavOpen()) {
                <span class="text-sm">保存済みプラン</span>
              }
            </a>
            <a
              routerLink="/genome"
              routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
              class="group flex items-center gap-3 rounded-lg border border-transparent text-slate-300 hover:bg-white/5 py-2"
              [class.px-3]="desktopNavOpen()"
              [class.px-2]="!desktopNavOpen()"
              [class.justify-center]="!desktopNavOpen()"
            >
              <span
                class="h-8 w-8 rounded-lg border border-slate-800 bg-white/5 grid place-items-center text-slate-200 group-hover:bg-white/10"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="5" cy="10" r="2"></circle>
                  <circle cx="15" cy="6" r="2"></circle>
                  <circle cx="15" cy="14" r="2"></circle>
                  <path d="M7 10h5M13 7.5L7.8 10M13 12.5L7.8 10"></path>
                </svg>
              </span>
              @if (desktopNavOpen()) {
                <span class="text-sm">人材データベース</span>
              }
            </a>
            <button
              type="button"
              class="group flex items-center gap-3 rounded-lg border border-transparent text-slate-300 hover:bg-white/5 py-2 transition"
              [class.px-3]="desktopNavOpen()"
              [class.px-2]="!desktopNavOpen()"
              [class.justify-center]="!desktopNavOpen()"
              [class.opacity-60]="demoBusy()"
              [class.cursor-not-allowed]="demoBusy()"
              [disabled]="demoBusy()"
              (click)="startDemo()"
            >
              <span
                class="h-8 w-8 rounded-lg border border-slate-800 bg-white/5 grid place-items-center text-slate-200 group-hover:bg-white/10"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M6 4.5l9 5.5-9 5.5z" />
                  <path d="M6 4.5v11" />
                </svg>
              </span>
              @if (desktopNavOpen()) {
                <span class="text-sm">デモ</span>
              }
            </button>
          </div>

          @if (desktopNavOpen()) {
            <div class="mt-auto rounded-lg border border-slate-800 bg-white/5 p-3">
              <div class="text-[10px] text-slate-400 font-semibold">AI Watchdog</div>
              <div class="mt-1 flex items-center gap-2 text-[12px] font-bold text-emerald-300">
                <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
                Active
              </div>
            </div>
          }
        </aside>

        <div
          class="flex-1 flex flex-col overflow-hidden bg-[radial-gradient(circle_at_top_right,#1e293b_0%,#0b1022_55%)]"
        >
          <main class="flex-1 overflow-auto p-4 sm:p-6">
            <div class="mb-3 flex items-center gap-2 lg:hidden">
              <button
                type="button"
                class="h-9 w-9 rounded-lg border border-slate-800 bg-white/5 grid place-items-center hover:bg-white/10"
                (click)="toggleMobileNav()"
                aria-label="Open navigation"
                aria-controls="mobile-nav"
                [attr.aria-expanded]="mobileNavOpen()"
              >
                <span class="flex flex-col gap-1">
                  <span class="h-0.5 w-5 bg-slate-200"></span>
                  <span class="h-0.5 w-5 bg-slate-200"></span>
                  <span class="h-0.5 w-5 bg-slate-200"></span>
                </span>
              </button>
            </div>
            <router-outlet />
          </main>
        </div>

        @if (mobileNavOpen()) {
          <div class="fixed inset-0 z-40 lg:hidden" aria-hidden="false">
            <div class="absolute inset-0 bg-black/60" (click)="closeMobileNav()"></div>
            <aside
              id="mobile-nav"
              role="dialog"
              aria-modal="true"
              aria-label="ナビゲーション"
              class="absolute left-0 top-0 h-full w-[min(86vw,320px)] bg-slate-950 border-r border-slate-800 p-5 flex flex-col gap-6 shadow-2xl"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                  <div
                    class="h-10 w-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 grid place-items-center"
                  >
                    <span class="font-black text-indigo-300">AI</span>
                  </div>
                  <div class="leading-tight">
                    <div class="text-lg font-extrabold tracking-tight">
                      Saih<span class="text-fuchsia-400">AI</span>
                      <span class="ml-1 text-xs text-slate-500 font-semibold">v2</span>
                    </div>
                    <div class="text-[11px] text-slate-400">99% autonomy, 1% intuition</div>
                  </div>
                </div>
                <button
                  type="button"
                  class="h-9 w-9 rounded-lg border border-slate-800 bg-white/5 text-slate-200 hover:bg-white/10 text-lg leading-none"
                  (click)="closeMobileNav()"
                  aria-label="メニューを閉じる"
                >
                  ×
                </button>
              </div>

              <div>
                <div
                  class="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-2 px-3"
                >
                  Cockpit
                </div>
                <a
                  routerLink="/dashboard"
                  routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
                  class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
                  (click)="closeMobileNav()"
                >
                  <span class="text-sm">経営ダッシュボード</span>
                </a>
                <a
                  routerLink="/simulator"
                  routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
                  class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
                  (click)="closeMobileNav()"
                >
                  <span class="text-sm">戦術シミュレーター</span>
                </a>
                <a
                  routerLink="/saved-plans"
                  routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
                  class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
                  (click)="closeMobileNav()"
                >
                  <span class="text-sm">保存済みプラン</span>
                </a>
                <a
                  routerLink="/genome"
                  routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
                  class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
                  (click)="closeMobileNav()"
                >
                  <span class="text-sm">人材データベース</span>
                </a>
                <button
                  type="button"
                  class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5 transition"
                  [class.opacity-60]="demoBusy()"
                  [class.cursor-not-allowed]="demoBusy()"
                  [disabled]="demoBusy()"
                  (click)="startDemo(); closeMobileNav()"
                >
                  <span class="text-sm">デモ</span>
                </button>
              </div>

              <div class="mt-auto rounded-lg border border-slate-800 bg-white/5 p-3">
                <div class="text-[10px] text-slate-400 font-semibold">AI Watchdog</div>
                <div class="mt-1 flex items-center gap-2 text-[12px] font-bold text-emerald-300">
                  <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
                  Active
                </div>
              </div>
            </aside>
          </div>
        }
      </div>
    }
    <app-toast-center />
  `,
  styles: [],
})
export class App {
  protected readonly title = signal('SaihAI');
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly titleService = inject(Title);
  private readonly api = inject(ApiClient);
  private readonly toast = inject(ToastService);
  private readonly activePath = signal('/dashboard');
  protected readonly isLoginRoute = computed(() => this.activePath() === '/login');
  protected readonly mobileNavOpen = signal(false);
  protected readonly desktopNavOpen = signal(true);
  protected readonly demoBusy = signal(false);

  protected readonly pageTitle = computed(() => {
    switch (this.activePath()) {
      case '/dashboard':
        return '経営ダッシュボード';
      case '/simulator':
        return '戦術シミュレーター';
      case '/saved-plans':
        return '保存済みプラン';
      case '/genome':
        return '人材データベース';
      default:
        return 'SaihAI';
    }
  });
  private readonly documentTitle = computed(() => {
    const currentTitle = this.pageTitle();

    return currentTitle === 'SaihAI' ? currentTitle : `${currentTitle} | SaihAI`;
  });

  constructor() {
    this.activePath.set(this.router.url.split('?')[0] || '/dashboard');
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        this.activePath.set(this.router.url.split('?')[0] || '/dashboard');
        this.mobileNavOpen.set(false);
      });

    effect(() => {
      this.titleService.setTitle(this.documentTitle());
    });
  }

  protected toggleMobileNav(): void {
    this.mobileNavOpen.set(!this.mobileNavOpen());
  }

  protected toggleDesktopNav(): void {
    this.desktopNavOpen.set(!this.desktopNavOpen());
  }

  protected closeMobileNav(): void {
    this.mobileNavOpen.set(false);
  }

  protected async startDemo(): Promise<void> {
    if (this.demoBusy()) return;
    this.demoBusy.set(true);
    try {
      const result = await firstValueFrom(this.api.startDemo());
      const alertId = result.alertId ? ` (alertId: ${result.alertId})` : '';
      this.toast.show({
        tone: 'success',
        title: 'デモを開始しました',
        message: `Slack にデモアラートを送信しました${alertId}`,
      });
    } catch (error) {
      let message = 'Slack 連携の設定を確認してください。';
      if (error instanceof HttpErrorResponse) {
        if (typeof error.error?.detail === 'string') {
          message = error.error.detail;
        } else if (error.message) {
          message = error.message;
        }
      }
      this.toast.show({ tone: 'error', title: 'デモ開始に失敗しました', message });
    } finally {
      this.demoBusy.set(false);
    }
  }
}
