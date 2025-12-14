import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 flex">
      <aside class="w-[260px] bg-slate-950 border-r border-slate-800 p-5 flex flex-col gap-6">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 grid place-items-center">
            <span class="font-black text-indigo-300">AI</span>
          </div>
          <div class="leading-tight">
            <div class="text-lg font-extrabold tracking-tight">
              saih<span class="text-fuchsia-400">AI</span>
              <span class="ml-1 text-xs text-slate-500 font-semibold">v2</span>
            </div>
            <div class="text-[11px] text-slate-400">99% autonomy, 1% intuition</div>
          </div>
        </div>

        <div>
          <div class="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-2 px-3">Cockpit</div>
          <a
            routerLink="/dashboard"
            routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
            class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
          >
            <span class="text-sm">経営ダッシュボード</span>
          </a>
          <a
            routerLink="/simulator"
            routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
            class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
          >
            <span class="text-sm">戦術シミュレーター</span>
          </a>
          <a
            routerLink="/genome"
            routerLinkActive="bg-indigo-500/15 text-indigo-200 border-indigo-400/50"
            class="group flex items-center gap-3 px-3 py-2 rounded-lg border border-transparent text-slate-300 hover:bg-white/5"
          >
            <span class="text-sm">Genome DB</span>
          </a>
        </div>

        <div>
          <div class="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-2 px-3">Debug & Demo</div>
          <button
            type="button"
            class="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-200 hover:bg-rose-500/15"
            (click)="triggerDemo('alert')"
          >
            <span class="text-sm font-semibold">緊急介入 (Alert)</span>
          </button>
          <button
            type="button"
            class="mt-2 w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 hover:bg-indigo-500/15"
            (click)="triggerDemo('manual')"
          >
            <span class="text-sm font-semibold">AI自動編成 (手動)</span>
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

      <div class="flex-1 flex flex-col overflow-hidden bg-[radial-gradient(circle_at_top_right,#1e293b_0%,#0b1022_55%)]">
        <header class="h-16 shrink-0 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur px-6 flex items-center justify-between">
          <div class="text-base font-bold tracking-tight">{{ pageTitle() }}</div>
          <div class="flex items-center gap-3">
            <button
              type="button"
              class="px-3 py-2 rounded-lg border border-slate-800 bg-white/5 text-slate-200 hover:bg-white/10 text-sm"
            >
              レポート
            </button>
            <button
              type="button"
              class="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm"
              (click)="triggerDemo('manual')"
            >
              AI自動編成
            </button>
          </div>
        </header>

        <main class="flex-1 overflow-auto p-6">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
  styles: [],
})
export class App {
  protected readonly title = signal('SaihAI');
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly activePath = signal('/dashboard');

  protected readonly pageTitle = computed(() => {
    switch (this.activePath()) {
      case '/dashboard':
        return '経営ダッシュボード';
      case '/simulator':
        return '戦術シミュレーター';
      case '/genome':
        return 'Genome DB';
      default:
        return 'SaihAI';
    }
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
      });
  }

  protected triggerDemo(mode: 'alert' | 'manual'): void {
    void this.router.navigate(['/simulator'], { queryParams: { demo: mode } });
  }
}
