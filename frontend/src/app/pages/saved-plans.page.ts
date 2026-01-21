import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { EmptyStateComponent } from '../components/empty-state.component';
import { SimulatorStore } from '../core/simulator-store';
import { SavedPlanSummary } from '../core/types';

@Component({
  imports: [CommonModule, EmptyStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0">
        <div class="ui-kicker">Plan Archive</div>
        <h2 class="mt-1 text-xl sm:text-2xl font-extrabold tracking-tight">保存済みプラン</h2>
        <p class="mt-1 text-sm text-slate-300 max-w-2xl">
          シミュレーション結果を一覧で管理し、必要なプランをシミュレーターへ適用します。
        </p>
      </div>

      <div class="w-full lg:w-[300px]">
        <div class="ui-panel p-3">
          <div class="ui-kicker">Status</div>
          <div class="mt-1 text-sm font-semibold text-slate-100">保存済み {{ planCount() }} 件</div>
          <div class="mt-1 text-xs text-slate-400">最新更新: {{ latestPlanLabel() }}</div>
        </div>
      </div>
    </div>

    <section class="mt-3 ui-panel p-3">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="ui-kicker">Plan Library</div>
          <div class="text-sm font-semibold text-slate-100">一覧</div>
          <div class="mt-1 text-xs text-slate-400">
            開くを押すとシミュレーターに反映されます。
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button type="button" class="ui-button-secondary text-xs" (click)="startNewPlan()">
            新規作成
          </button>
          <button
            type="button"
            class="ui-button-ghost text-xs"
            [disabled]="store.savedPlansLoading()"
            (click)="reloadSavedPlans()"
          >
            一覧更新
          </button>
        </div>
      </div>

      @if (store.savedPlansError(); as planErr) {
        <div class="mt-2 text-xs text-rose-200">{{ planErr }}</div>
      }

      @if (actionError(); as actionErr) {
        <div class="mt-2 text-xs text-rose-200">{{ actionErr }}</div>
      }

      @if (store.savedPlansLoading()) {
        <div class="mt-3 text-xs text-slate-400">loading saved plans...</div>
      } @else if (store.savedPlans().length) {
        <div class="mt-3 grid gap-2 max-h-[520px] overflow-auto pr-1">
          @for (plan of store.savedPlans(); track plan.id) {
            <div class="rounded-xl border border-slate-800 bg-slate-950/30 p-3">
              <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                <button
                  type="button"
                  class="w-full text-left min-w-0 ui-focus-ring"
                  (click)="openSavedPlan(plan.id)"
                >
                  <div class="text-sm font-semibold text-slate-100 truncate">{{ plan.title }}</div>
                  <div class="mt-1 text-xs text-slate-400">
                    {{ plan.projectName ?? '—' }}
                  </div>
                  <div class="mt-1 text-[11px] text-slate-500">
                    更新: {{ formatPlanDate(plan.updatedAt ?? plan.createdAt) }}
                  </div>
                  @if (plan.contentText) {
                    <div class="mt-2 text-[11px] text-slate-500">{{ planPreview(plan) }}</div>
                  }
                </button>
                <div class="flex items-center justify-between gap-2 sm:flex-col sm:items-end sm:gap-2">
                  <span class="ui-pill border-indigo-500/40 bg-indigo-500/10 text-indigo-100">
                    Plan {{ plan.selectedPlan ?? plan.recommendedPlan ?? '-' }}
                  </span>
                  <button
                    type="button"
                    class="ui-button-secondary text-[11px]"
                    (click)="openSavedPlan(plan.id)"
                  >
                    開く
                  </button>
                  <button
                    type="button"
                    class="ui-button-ghost text-[11px]"
                    [disabled]="actionLoading() && actionPlanId() === plan.id"
                    (click)="deleteSavedPlan(plan.id, $event)"
                  >
                    @if (actionLoading() && actionPlanId() === plan.id) {
                      削除中...
                    } @else {
                      削除
                    }
                  </button>
                </div>
              </div>
            </div>
          }
        </div>
      } @else {
        <app-empty-state
          kicker="Empty"
          title="保存済みプランがありません"
          description="シミュレーションを実行するとここに保存されます。"
        />
      }
    </section>
  `,
})
export class SavedPlansPage {
  protected readonly store = inject(SimulatorStore);
  private readonly router = inject(Router);
  protected readonly actionLoading = signal(false);
  protected readonly actionError = signal<string | null>(null);
  protected readonly actionPlanId = signal<string | null>(null);

  protected readonly planCount = computed(() => this.store.savedPlans().length);
  protected readonly latestPlanLabel = computed(() => this.resolveLatestPlanLabel());

  constructor() {
    void this.init();
  }

  protected reloadSavedPlans(): void {
    void this.store.loadSavedPlans();
  }

  protected startNewPlan(): void {
    void this.router.navigate(['/simulator'], { queryParams: { newPlan: '1' } });
  }

  protected openSavedPlan(planId: string): void {
    void this.router.navigate(['/simulator'], { queryParams: { savedPlan: planId } });
  }

  protected async deleteSavedPlan(planId: string, event?: Event): Promise<void> {
    event?.stopPropagation();
    if (this.actionLoading()) return;
    this.actionError.set(null);
    this.actionLoading.set(true);
    this.actionPlanId.set(planId);
    try {
      await this.store.deleteSavedPlan(planId);
    } catch (e) {
      this.actionError.set(this.resolveSavedPlanError(e));
    } finally {
      this.actionLoading.set(false);
      this.actionPlanId.set(null);
    }
  }

  protected formatPlanDate(value?: string | null): string {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  protected planPreview(plan: SavedPlanSummary): string {
    const raw = String(plan.contentText ?? '').trim();
    if (!raw) return '';
    const max = 140;
    return raw.length > max ? `${raw.slice(0, max)}…` : raw;
  }

  private async init(): Promise<void> {
    await this.store.loadSavedPlans();
  }

  private resolveLatestPlanLabel(): string {
    const first = this.store.savedPlans()[0];
    if (!first) return '--';
    return this.formatPlanDate(first.updatedAt ?? first.createdAt);
  }

  private resolveSavedPlanError(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (typeof error.error === 'object' && error.error && 'detail' in error.error) {
        return String((error.error as { detail?: unknown }).detail ?? error.message);
      }
      return error.message;
    }
    if (error instanceof Error) return error.message;
    return 'unknown error';
  }
}
