import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subscription } from 'rxjs';

import { EmptyStateComponent } from '../components/empty-state.component';
import { HaisaSpeechComponent } from '../components/haisa-speech.component';
import { NeuralOrbComponent } from '../components/neural-orb.component';
import {
  HaisaEmotion,
  haisaAvatarSrc as resolveHaisaAvatarSrc,
  haisaEmotionForFit,
  haisaEmotionForRisk,
  haisaEmotionLabel as resolveHaisaEmotionLabel,
} from '../core/haisa-emotion';
import { SimulatorStore } from '../core/simulator-store';
import { SimulationPlan, SimulationResult } from '../core/types';

interface ChatEntry {
  from: 'ai' | 'user';
  text: string;
  emotion?: HaisaEmotion;
}

@Component({
  imports: [NeuralOrbComponent, HaisaSpeechComponent, EmptyStateComponent],
  template: `
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0">
        <div class="ui-kicker">Tactical Simulator</div>
        <h2 class="mt-1 text-xl sm:text-2xl font-extrabold tracking-tight">戦術シミュレーター</h2>
        <p class="mt-2 text-sm text-slate-300 max-w-2xl">
          案件と候補者を選び、AIの「未来予測」と介入プランを確認します。
        </p>
      </div>

      <div class="w-full lg:w-[320px]">
        <div class="ui-panel">
          <div class="ui-kicker">Next Action</div>
          @if (store.loading() || store.streaming()) {
            <div class="mt-1 text-sm font-semibold text-slate-100">AIが編成中</div>
            <div class="mt-1 text-xs text-slate-400">進捗を確認しながら待機します。</div>
            <div class="mt-3">
              <button type="button" class="ui-button-secondary" disabled>進行中...</button>
            </div>
          } @else if (store.simulationResult()) {
            <div class="mt-1 text-sm font-semibold text-slate-100">介入チェックポイントへ</div>
            <div class="mt-1 text-xs text-slate-400">
              結果を確認し、プランを承認または指示を追加します。
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button type="button" class="ui-button-primary" (click)="openOverlay('manual')">
                介入を開く
              </button>
              <button type="button" class="ui-button-secondary" (click)="startDemo('alert')">
                緊急デモ
              </button>
            </div>
          } @else if (canRunSimulation()) {
            <div class="mt-1 text-sm font-semibold text-slate-100">AI自動編成を実行</div>
            <div class="mt-1 text-xs text-slate-400">
              選択内容を確認し、シミュレーションを開始します。
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button type="button" class="ui-button-primary" (click)="store.runSimulation()">
                AI自動編成
              </button>
              <button type="button" class="ui-button-secondary" (click)="startDemo('manual')">
                デモで確認
              </button>
            </div>
          } @else {
            <div class="mt-1 text-sm font-semibold text-slate-100">対象を選択</div>
            <div class="mt-1 text-xs text-slate-400">
              案件とメンバーを選ぶと、次のアクションに進めます。
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button type="button" class="ui-button-secondary" (click)="startDemo('manual')">
                デモで開始
              </button>
              <button type="button" class="ui-button-ghost" (click)="startDemo('alert')">
                緊急デモ
              </button>
            </div>
          }
        </div>
      </div>
    </div>

    @if (store.error(); as err) {
      <div class="mb-3 mt-4">
        <app-haisa-speech
          [tone]="'error'"
          [message]="err"
          [compact]="true"
          [showAvatar]="false"
        />
      </div>
    }

    <div class="mt-4 ui-panel-muted">
      <div class="ui-kicker">Flow</div>
      <ol class="mt-3 grid gap-2 sm:grid-cols-4 text-xs">
        @for (step of steps; track step.id) {
          <li
            class="flex items-center gap-2 rounded-lg border px-3 py-2"
            [class.border-emerald-500/50]="currentStep() > step.id"
            [class.bg-emerald-500/10]="currentStep() > step.id"
            [class.text-emerald-100]="currentStep() > step.id"
            [class.border-indigo-500/50]="currentStep() === step.id"
            [class.bg-indigo-500/10]="currentStep() === step.id"
            [class.text-indigo-100]="currentStep() === step.id"
            [class.border-slate-800]="currentStep() < step.id"
            [class.text-slate-400]="currentStep() < step.id"
          >
            <span class="text-[10px] font-bold">{{ step.id }}</span>
            <span class="font-semibold">{{ step.label }}</span>
          </li>
        }
      </ol>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <section class="ui-panel" id="simulator-input">
        <div class="flex items-center justify-between gap-3 mb-3">
          <div class="font-semibold">1. 入力（対象の選択）</div>
          @if (store.loading()) {
            <span class="text-xs text-slate-400">processing...</span>
          }
        </div>

        <label class="block text-sm text-slate-300 mb-2">案件</label>
        <select
          class="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 ui-focus-ring"
          [value]="store.selectedProjectId() ?? ''"
          (change)="onProjectChange($event)"
        >
          <option value="" disabled>選択してください</option>
          @for (p of store.projects(); track p.id) {
            <option [value]="p.id">{{ p.name }}（予算 {{ p.budget }}）</option>
          }
        </select>

        <div class="mt-4 flex items-center justify-between">
          <div class="text-sm text-slate-300">メンバー</div>
          <button
            type="button"
            class="text-xs px-2 py-1 rounded border border-slate-700 hover:border-slate-500 ui-focus-ring"
            (click)="store.clearSelection()"
          >
            Clear
          </button>
        </div>

        <div class="mt-2 grid gap-2 max-h-[360px] overflow-auto pr-1 lg:max-h-none lg:overflow-visible lg:pr-0">
          @for (m of store.members(); track m.id) {
            <label
              class="flex items-start gap-3 rounded border border-slate-800 bg-slate-900/40 px-3 py-2"
            >
              <input
                type="checkbox"
                class="mt-1"
                [checked]="store.selectedMemberIds().includes(m.id)"
                (change)="store.toggleMember(m.id)"
              />
              <div class="flex-1">
                <div class="flex items-center justify-between gap-3">
                  <div class="font-medium">{{ m.name }}</div>
                  <div class="text-xs text-slate-300">{{ m.cost }} / {{ m.availability }}%</div>
                </div>
                <div class="text-xs text-slate-400 mt-1">{{ m.skills.join(', ') }}</div>
              </div>
            </label>
          }
        </div>

        <div class="mt-4">
          <div class="text-sm text-slate-300">チーム編成</div>
          <div
            class="mt-2 min-h-12 rounded-xl border border-slate-800 bg-slate-950/30 p-3 flex flex-wrap gap-2 items-center"
          >
            @if (store.selectedMembers().length) {
              @for (m of store.selectedMembers(); track m.id) {
                <button
                  type="button"
                  class="px-3 py-2 rounded-lg border border-slate-700 bg-white/5 hover:bg-white/10 text-sm font-semibold ui-focus-ring"
                  (click)="store.toggleMember(m.id)"
                  [title]="'クリックで外す: ' + m.name"
                >
                  {{ m.name }}
                </button>
              }
            } @else {
              <span class="text-xs text-slate-500">メンバーを選択してください</span>
            }
          </div>

          <div class="mt-3">
            <div class="flex items-center justify-between text-xs text-slate-400">
              <span>予算消化率</span>
              <span class="text-slate-200"
                >{{ budgetUsed() }} / {{ store.selectedProject()?.budget ?? 0 }}</span
              >
            </div>
            <div class="mt-2 h-2 rounded bg-slate-800 overflow-hidden">
              <div
                class="h-2"
                [style.width.%]="budgetPct()"
                [style.background]="budgetBarColor()"
              ></div>
            </div>
          </div>
        </div>

        <button
          type="button"
          class="mt-4 w-full ui-button-primary disabled:opacity-60"
          [disabled]="store.loading()"
          (click)="store.runSimulation()"
        >
          AI自動編成
        </button>
        @if (store.loading()) {
          <div class="text-xs text-slate-400 mt-2">running…</div>
        }
      </section>

      <section class="ui-panel">
        <div class="flex items-center justify-between gap-3 mb-3">
          <div class="font-semibold">2. 結果</div>
          <button
            type="button"
            class="ui-button-secondary text-xs disabled:opacity-60"
            [disabled]="!store.simulationResult()"
            (click)="openOverlay('manual')"
          >
            介入チェックポイント
          </button>
        </div>

        @if (store.streaming() || store.planProgressLog().length || store.planDiscussionLog().length) {
          <details class="mb-4 rounded-xl border border-slate-800 bg-slate-900/30 p-3" [open]="store.streaming()">
            <summary class="cursor-pointer list-none flex items-center justify-between gap-3">
              <span class="text-sm font-semibold">AI進捗ストリーム</span>
              <span class="text-xs text-slate-300"
                >{{ store.planProgress()?.progress ?? 0 }}%</span
              >
            </summary>
            <div class="mt-3">
              <div class="mt-2 flex items-center justify-between text-xs text-slate-400">
                <span>{{ store.planProgress()?.phase ?? 'idle' }}</span>
                <span class="text-slate-200">{{ store.planProgress()?.progress ?? 0 }}%</span>
              </div>
              <div class="mt-2 h-2 rounded bg-slate-800 overflow-hidden">
                <div
                  class="h-2 bg-indigo-500"
                  [style.width.%]="store.planProgress()?.progress ?? 0"
                ></div>
              </div>

              <div class="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <div class="ui-kicker">Progress Log</div>
                  @if (store.planProgressLog().length) {
                    <ul class="mt-2 space-y-1 text-xs text-slate-300">
                      @for (entry of store.planProgressLog(); track $index) {
                        <li>{{ entry.message }}</li>
                      }
                    </ul>
                  } @else {
                    <div class="mt-2 text-xs text-slate-500">Waiting for updates...</div>
                  }
                </div>
                <div>
                  <div class="ui-kicker">Debate Stream</div>
                  @if (store.planDiscussionLog().length) {
                    <ul class="mt-2 space-y-2 text-xs">
                      @for (entry of store.planDiscussionLog(); track $index) {
                        <li class="flex items-start gap-2">
                          <span
                            class="shrink-0 px-2 py-0.5 rounded-md border border-slate-700 bg-slate-900/60"
                            [class.border-rose-500/40]="entry.tone === 'risk'"
                            [class.border-emerald-500/40]="entry.tone === 'hr'"
                            [class.border-indigo-500/40]="entry.tone === 'pm'"
                            [class.border-amber-500/40]="entry.tone === 'gunshi'"
                          >
                            {{ entry.agent }}
                          </span>
                          <span class="text-slate-200">{{ entry.message }}</span>
                        </li>
                      }
                    </ul>
                  } @else {
                    <div class="mt-2 text-xs text-slate-500">Waiting for debate...</div>
                  }
                </div>
              </div>
            </div>
          </details>
        }

        @if (store.simulationResult(); as r) {
          <div class="ui-panel-muted">
            <div class="ui-kicker">Summary</div>
            <div class="mt-2 text-sm text-slate-300">
              {{ r.project.name }} / pattern:
              <span class="text-slate-100 font-semibold">{{ r.pattern }}</span>
            </div>
            <div class="mt-3 flex flex-wrap gap-2 text-xs">
              <span class="ui-pill border-emerald-500/40 bg-emerald-500/10 text-emerald-200">
                推奨 Plan {{ recommendedPlan()?.planType ?? '-' }}
              </span>
              <span class="ui-pill border-rose-500/40 bg-rose-500/10 text-rose-200">
                risk {{ r.metrics.riskPct }}%
              </span>
              <span class="ui-pill border-indigo-500/40 bg-indigo-500/10 text-indigo-100">
                budget {{ r.metrics.budgetPct }}%
              </span>
            </div>
          </div>

          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div class="rounded border border-slate-800 bg-slate-900/30 p-3">
              <div class="text-xs text-slate-400">予算</div>
              <div class="mt-1 text-sm">
                {{ r.metrics.budgetUsed }} / {{ r.project.budget }}（{{ r.metrics.budgetPct }}%）
              </div>
              <div class="mt-2 h-2 rounded bg-slate-800 overflow-hidden">
                <div class="h-2 bg-emerald-500" [style.width.%]="r.metrics.budgetPct"></div>
              </div>
            </div>
            <div class="rounded border border-slate-800 bg-slate-900/30 p-3">
              <div class="text-xs text-slate-400">スコア</div>
              <div class="mt-1 text-sm">
                skill {{ r.metrics.skillFitPct }}% / career {{ r.metrics.careerFitPct }}%
              </div>
              <div class="mt-1 text-sm">risk {{ r.metrics.riskPct }}%</div>
            </div>
          </div>

          <div class="mt-4">
            <details class="rounded-xl border border-slate-800 bg-slate-900/30 p-3">
              <summary class="cursor-pointer list-none text-sm font-semibold">要件カバー率</summary>
              @if (r.requirementResult.length) {
                <div class="mt-2 flex flex-wrap gap-2">
                  @for (req of r.requirementResult; track req.name) {
                    <span
                      class="text-[11px] px-2 py-1 rounded-full border"
                      [class.border-emerald-500/40]="req.fulfilled"
                      [class.bg-emerald-500/10]="req.fulfilled"
                      [class.text-emerald-200]="req.fulfilled"
                      [class.border-rose-500/40]="!req.fulfilled"
                      [class.bg-rose-500/10]="!req.fulfilled"
                      [class.text-rose-200]="!req.fulfilled"
                    >
                      {{ req.name }} {{ req.fulfilled ? 'OK' : 'NG' }}
                    </span>
                  }
                </div>
              } @else {
                <div class="mt-2 text-xs text-slate-400">requiredSkills 未登録</div>
              }
            </details>
          </div>

          <div class="mt-4">
            <details class="rounded-xl border border-slate-800 bg-slate-900/30 p-3">
              <summary class="cursor-pointer list-none text-sm font-semibold">未来タイムライン</summary>
              <ul class="mt-2 space-y-2 timeline-list">
                @for (t of r.timeline; track $index) {
                  <li
                    class="text-sm timeline-entry"
                    [class.status-growth]="t.level === 'good'"
                    [class.status-stable]="t.level === 'ok'"
                    [class.status-alert]="t.level === 'bad'"
                  >
                    <span class="text-xs text-slate-400">{{ t.t }}</span>
                    <span
                      class="ml-2"
                      [class.text-emerald-300]="t.level === 'good'"
                      [class.text-amber-300]="t.level === 'ok'"
                      [class.text-rose-300]="t.level === 'bad'"
                      >{{ t.text }}</span
                    >
                  </li>
                }
              </ul>
            </details>
          </div>

          <div class="mt-4">
            <details class="rounded-xl border border-slate-800 bg-slate-900/30 p-3">
              <summary class="cursor-pointer list-none text-sm font-semibold">エージェント所見</summary>
              <div class="mt-2 grid gap-2 sm:grid-cols-2">
                <div class="rounded border border-slate-800 bg-slate-900/30 p-3 text-sm">
                  <div class="flex items-center justify-between">
                    <span class="font-semibold">PM</span>
                    <span
                      [class.text-emerald-300]="r.agents.pm.vote === 'ok'"
                      [class.text-rose-300]="r.agents.pm.vote === 'ng'"
                      >{{ r.agents.pm.vote }}</span
                    >
                  </div>
                  <div class="text-xs text-slate-300 mt-1">{{ r.agents.pm.note }}</div>
                </div>
                <div class="rounded border border-slate-800 bg-slate-900/30 p-3 text-sm">
                  <div class="flex items-center justify-between">
                    <span class="font-semibold">HR</span>
                    <span
                      [class.text-emerald-300]="r.agents.hr.vote === 'ok'"
                      [class.text-rose-300]="r.agents.hr.vote === 'ng'"
                      >{{ r.agents.hr.vote }}</span
                    >
                  </div>
                  <div class="text-xs text-slate-300 mt-1">{{ r.agents.hr.note }}</div>
                </div>
                <div class="rounded border border-slate-800 bg-slate-900/30 p-3 text-sm">
                  <div class="flex items-center justify-between">
                    <span class="font-semibold">Risk</span>
                    <span
                      [class.text-emerald-300]="r.agents.risk.vote === 'ok'"
                      [class.text-rose-300]="r.agents.risk.vote === 'ng'"
                      >{{ r.agents.risk.vote }}</span
                    >
                  </div>
                  <div class="text-xs text-slate-300 mt-1">{{ r.agents.risk.note }}</div>
                </div>
                <div class="rounded border border-slate-800 bg-slate-900/30 p-3 text-sm">
                  <div class="flex items-center justify-between">
                    <span class="font-semibold">Gunshi</span>
                    <span class="text-indigo-300">{{ r.agents.gunshi.recommend }}</span>
                  </div>
                  <div class="text-xs text-slate-300 mt-1">{{ r.agents.gunshi.note }}</div>
                </div>
              </div>
            </details>
          </div>

          <div class="mt-4">
            <div class="text-sm font-semibold">推奨プラン</div>
            @if (recommendedPlan(); as plan) {
              <div class="mt-2 rounded border border-emerald-500/50 bg-emerald-500/10 p-3">
                <div class="flex items-center justify-between gap-2">
                  <div class="font-semibold text-slate-100">
                    Plan {{ plan.planType }}: {{ plan.summary }}
                  </div>
                  <span
                    class="text-[10px] font-bold tracking-wider rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-emerald-200"
                  >
                    AI推奨
                  </span>
                </div>
                <div class="mt-2 text-xs text-slate-300">
                  pros: {{ plan.prosCons.pros.join(' / ') }}
                </div>
                <div class="mt-1 text-xs text-slate-300">
                  cons: {{ plan.prosCons.cons.join(' / ') }}
                </div>
              </div>
            } @else {
              <div class="mt-2 text-xs text-slate-400">推奨プランがありません。</div>
            }

            @if (secondaryPlans().length) {
              <details class="mt-3 rounded-xl border border-slate-800 bg-slate-900/30 p-3">
                <summary class="cursor-pointer list-none text-sm font-semibold">他のプラン</summary>
                <div class="mt-3 grid gap-3 grid-cols-1 sm:grid-cols-2">
                  @for (p of secondaryPlans(); track p.id) {
                    <div
                      class="relative rounded border border-slate-800 bg-slate-900/30 p-3 transition hover:border-slate-500"
                    >
                      <div class="font-semibold text-slate-100 leading-tight">
                        Plan {{ p.planType }}: {{ p.summary }}
                      </div>
                      <div class="mt-3 text-xs text-slate-300 space-y-1">
                        <div class="flex items-baseline gap-1">
                          <span class="text-slate-400">pros:</span>
                          <span class="text-slate-200">{{ p.prosCons.pros.join(' / ') }}</span>
                        </div>
                        <div class="flex items-baseline gap-1">
                          <span class="text-slate-400">cons:</span>
                          <span class="text-slate-200">{{ p.prosCons.cons.join(' / ') }}</span>
                        </div>
                      </div>
                    </div>
                  }
                </div>
              </details>
            }
          </div>
        } @else {
          <app-empty-state
            kicker="Empty"
            title="結果はまだありません"
            description="案件とメンバーを選択してAI自動編成を実行してください。"
            primaryLabel="デモで確認"
            secondaryLabel="緊急デモ"
            (primary)="startDemo('manual')"
            (secondary)="startDemo('alert')"
          />
        }
      </section>
    </div>

    @if (overlayOpen()) {
      <div class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/70" (click)="closeOverlay()"></div>
        <div
          class="absolute inset-0 sm:inset-auto sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 w-full h-full sm:w-[min(1120px,calc(100vw-3rem))] sm:h-[min(780px,calc(100vh-3rem))] rounded-none sm:rounded-2xl overflow-hidden border border-slate-800 bg-slate-950/70 surface-overlay"
        >
          <app-neural-orb class="absolute inset-0 opacity-30"></app-neural-orb>

          <div class="relative h-full flex flex-col">
            <div
              class="min-h-12 sm:min-h-14 shrink-0 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur px-4 sm:px-5 py-2 sm:py-3 flex items-start sm:items-center justify-between gap-3"
            >
              <div class="flex flex-wrap items-center gap-2 sm:gap-3 min-w-0">
                <div
                  class="px-3 py-1 rounded-full text-xs font-extrabold tracking-wide text-white status-indicator"
                  [class.bg-rose-500]="overlayMode() === 'alert'"
                  [class.bg-indigo-600]="overlayMode() !== 'alert'"
                  [class.status-alert]="overlayMode() === 'alert'"
                  [class.status-stable]="overlayMode() !== 'alert'"
                >
                  {{ overlayMode() === 'alert' ? 'ALERT ACTIVE' : 'MANUAL MODE' }}
                </div>
                <div class="font-bold text-slate-100 leading-tight">介入チェックポイント</div>
              </div>
              <button
                type="button"
                class="text-slate-300 hover:text-white text-2xl leading-none shrink-0"
                (click)="closeOverlay()"
              >
                ×
              </button>
            </div>

            <div class="flex-1 min-h-0 overflow-y-auto lg:overflow-hidden" data-overlay-scroll>
              <div class="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(320px,40%)] lg:gap-0 min-h-full">
                <div class="border-b lg:border-b-0 lg:border-r border-slate-800/80 flex flex-col min-h-0 overflow-visible lg:overflow-hidden">
                  <div class="p-4 sm:p-5 border-b border-slate-800/80 bg-white/5">
                    <div class="ui-kicker">{{ overlayKpiLabel() }}</div>
                    <div
                      class="mt-1 text-3xl sm:text-4xl font-extrabold tracking-tight"
                      [class.text-rose-200]="overlayMode() === 'alert'"
                      [class.text-emerald-200]="overlayMode() !== 'alert'"
                    >
                      {{ overlayKpiVal() }}
                    </div>
                    <div class="mt-1 text-sm text-slate-300">{{ overlayKpiDesc() }}</div>
                  </div>

                  <div class="p-4 sm:p-5 border-b border-slate-800/80">
                    <div class="ui-kicker">Step 1: 見る</div>
                    @if (store.simulationResult(); as r) {
                      <div class="mt-2 text-sm text-slate-200 font-semibold">
                        推奨 Plan {{ recommendedPlan()?.planType ?? r.agents.gunshi.recommend }}
                      </div>
                      <ul class="mt-2 space-y-1 text-xs text-slate-400">
                        <li>risk: {{ r.metrics.riskPct }}%</li>
                        <li>budget: {{ r.metrics.budgetPct }}%</li>
                        <li>pattern: {{ r.pattern }}</li>
                      </ul>
                    } @else {
                      <div class="mt-2 text-xs text-slate-400">結果がありません。</div>
                    }
                  </div>

                  <details class="border-b border-slate-800/80">
                    <summary
                      class="cursor-pointer list-none px-4 sm:px-5 py-3 text-[11px] text-slate-400 font-bold uppercase tracking-wider"
                    >
                      根拠ログ（Agent Log）
                    </summary>
                    <div class="p-4 sm:p-5 space-y-2 font-mono text-xs min-h-0 lg:flex-1 lg:overflow-auto">
                      @for (l of overlayLog(); track $index) {
                        <div class="flex items-start gap-3">
                          <span
                            class="shrink-0 px-2 py-1 rounded-md border border-slate-700 bg-slate-900/60"
                            [class.border-rose-500/40]="l.tone === 'risk'"
                            [class.border-emerald-500/40]="l.tone === 'hr'"
                            [class.border-indigo-500/40]="l.tone === 'pm'"
                            [class.border-amber-500/40]="l.tone === 'gunshi'"
                          >
                            {{ l.agent }}
                          </span>
                          <span class="text-slate-200 flex-1 min-w-0 break-words">{{ l.text }}</span>
                        </div>
                      }
                    </div>
                  </details>
                </div>

                <div class="flex flex-col min-h-0 overflow-visible lg:overflow-hidden">
                  <div class="p-4 sm:p-5 border-b border-slate-800/80">
                    <div class="ui-kicker">Step 2: 選ぶ</div>
                    <div class="text-sm font-bold text-slate-100">戦略プランの選択</div>
                    @if (store.simulationResult(); as r) {
                      <div class="mt-3 grid gap-3 grid-cols-1 sm:grid-cols-2">
                        @for (p of r.plans; track p.id) {
                          <button
                            type="button"
                            class="relative text-left rounded-xl border bg-slate-900/40 p-4 hover:bg-slate-900/55 status-plan"
                            [class.border-emerald-500]="p.recommended || selectedPlanId() === p.planType"
                            [class.border-slate-800]="!p.recommended && selectedPlanId() !== p.planType"
                            [class.status-recommended]="p.recommended"
                            (click)="selectPlan(p.planType)"
                          >
                            @if (p.recommended) {
                              <div
                                class="absolute right-3 top-3 text-[10px] px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-200 font-bold"
                              >
                                AI推奨
                              </div>
                            }
                            @if (selectedPlanId() === p.planType) {
                              <div
                                class="absolute left-3 top-3 text-[10px] px-2 py-1 rounded-full bg-indigo-500/20 text-indigo-100 font-bold"
                              >
                                選択中
                              </div>
                            }
                            <div class="font-extrabold text-slate-100 break-words">
                              Plan {{ p.planType }}: {{ p.summary }}
                            </div>
                            <div class="mt-2 text-xs text-slate-300">
                              pros: {{ p.prosCons.pros.join(' / ') }}
                            </div>
                            <div class="mt-1 text-xs text-slate-300">
                              cons: {{ p.prosCons.cons.join(' / ') }}
                            </div>
                          </button>
                        }
                      </div>
                    } @else {
                      <div class="mt-3 text-sm text-slate-400">
                        先にシミュレーションを実行してください。
                      </div>
                    }
                  </div>

                  <div class="flex flex-col min-h-0 lg:flex-1 lg:overflow-hidden">
                    <div class="px-4 sm:px-5 py-3 border-b border-slate-800/80">
                      <div class="ui-kicker">Step 3: 指示</div>
                      <div class="text-sm font-semibold text-slate-100">指示ログ</div>
                    </div>
                    <div class="p-4 sm:p-5 space-y-3 min-h-0 lg:flex-1 lg:overflow-auto">
                      @for (m of overlayChat(); track $index) {
                        <div
                          class="haisa-chat-line"
                          [class.justify-end]="m.from === 'user'"
                          [class.justify-start]="m.from !== 'user'"
                        >
                          <div
                            class="max-w-[80%] rounded-2xl px-4 py-3 text-sm border haisa-bubble haisa-bubble--tail break-words"
                            [class.bg-indigo-600]="m.from === 'user'"
                            [class.text-white]="m.from === 'user'"
                            [class.border-indigo-500/40]="m.from === 'user'"
                            [class.bg-slate-900/40]="m.from !== 'user'"
                            [class.text-slate-100]="m.from !== 'user'"
                            [class.border-slate-800]="m.from !== 'user'"
                            [class.ai]="m.from !== 'user'"
                            [class.user]="m.from === 'user'"
                          >
                            {{ m.text }}
                          </div>
                        </div>
                      }
                    </div>

                    <div class="p-4 sm:p-5 border-t border-slate-800/80">
                      <div class="flex items-center gap-3">
                        <div
                          class="haisa-avatar"
                          [attr.title]="haisaEmotionLabel(overlayHaisaEmotion())"
                          [style.width.px]="56"
                          [style.height.px]="56"
                          [style.border-radius.px]="18"
                          aria-hidden="true"
                        >
                          <img
                            [src]="haisaAvatarSrc(overlayHaisaEmotion())"
                            alt=""
                            class="haisa-avatar-image"
                            aria-hidden="true"
                          />
                        </div>
                        <div class="min-w-0">
                          <div class="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
                            ハイサイくん
                          </div>
                          <div class="text-xs text-slate-300">指示をまとめて共有します。</div>
                        </div>
                      </div>
                    </div>

                    <div class="p-4 sm:p-5 border-t border-slate-800/80 flex flex-col gap-3">
                      <input
                        #chatInput
                        type="text"
                        class="w-full bg-slate-950/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 ui-focus-ring"
                        placeholder="条件や指示を入力"
                        (keydown.enter)="sendChat(chatInput.value); chatInput.value = ''"
                        autocomplete="off"
                      />
                      <div class="flex flex-wrap gap-2">
                        <button
                          type="button"
                          class="ui-button-secondary"
                          (click)="sendChat(chatInput.value); chatInput.value = ''"
                        >
                          指示を送信
                        </button>
                        <button
                          type="button"
                          class="ui-button-primary"
                          (click)="approvePlan()"
                        >
                          承認して実行
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    }
  `,
})
export class SimulatorPage implements OnDestroy {
  protected readonly store = inject(SimulatorStore);
  private readonly route = inject(ActivatedRoute);

  protected readonly overlayOpen = signal(false);
  protected readonly overlayMode = signal<'alert' | 'manual'>('alert');
  protected readonly overlayKpiLabel = signal('RISK');
  protected readonly overlayKpiVal = signal('--%');
  protected readonly overlayKpiDesc = signal('');

  protected readonly overlayLog = signal<
    { agent: string; tone: 'pm' | 'hr' | 'risk' | 'gunshi'; text: string }[]
  >([]);
  protected readonly overlayChat = signal<ChatEntry[]>([]);

  protected readonly selectedPlanId = signal<'A' | 'B' | 'C' | null>(null);

  protected readonly steps = [
    { id: 1, label: '対象選択' },
    { id: 2, label: 'AI実行' },
    { id: 3, label: '結果確認' },
    { id: 4, label: '介入' },
  ];

  protected readonly currentStep = computed(() => {
    if (this.overlayOpen()) return 4;
    if (this.store.simulationResult()) return 3;
    if (this.store.loading() || this.store.streaming()) return 2;
    return 1;
  });

  protected readonly canRunSimulation = computed(() => {
    return Boolean(this.store.selectedProjectId()) && this.store.selectedMemberIds().length > 0;
  });

  protected readonly recommendedPlan = computed<SimulationPlan | null>(() => {
    const result = this.store.simulationResult();
    if (!result?.plans?.length) return null;
    return result.plans.find((p) => p.recommended) ?? result.plans[0] ?? null;
  });

  protected readonly secondaryPlans = computed<SimulationPlan[]>(() => {
    const result = this.store.simulationResult();
    if (!result?.plans?.length) return [];
    const recommended = this.recommendedPlan();
    return result.plans.filter((p) => p !== recommended);
  });

  protected readonly budgetUsed = computed(() =>
    this.store.selectedMembers().reduce((sum, m) => sum + m.cost, 0)
  );
  protected readonly budgetPct = computed(() => {
    const budget = this.store.selectedProject()?.budget ?? 0;
    if (!budget) return 0;
    return Math.min(100, Math.round((this.budgetUsed() / budget) * 100));
  });
  protected readonly budgetBarColor = computed(() =>
    this.budgetPct() >= 100 ? '#f43f5e' : '#06b6d4'
  );

  private readonly timers: number[] = [];
  private lastKey = '';
  private querySub: Subscription | null = null;

  constructor() {
    void this.init();
  }

  protected onProjectChange(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    this.store.setProject(target.value);
  }

  protected startDemo(mode: 'alert' | 'manual'): void {
    void this.runDemo(mode);
  }

  ngOnDestroy(): void {
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
    this.querySub?.unsubscribe();
    this.querySub = null;
    this.store.closePlanStream();
  }

  private async init(): Promise<void> {
    await this.store.loadOnce();

    this.querySub?.unsubscribe();
    this.querySub = this.route.queryParamMap.subscribe((p) => {
      const demo = p.get('demo');
      const focus = p.get('focus');
      const key = `${demo ?? ''}|${focus ?? ''}`;
      if (key === this.lastKey) return;
      this.lastKey = key;

      if (focus) this.store.focusMember(focus);
      if (demo === 'alert' || demo === 'manual') void this.runDemo(demo);
    });
  }

  private async runDemo(mode: 'alert' | 'manual'): Promise<void> {
    const projectId = this.store.projects().some((x) => x.id === 'ec')
      ? 'ec'
      : this.store.projects()[0]?.id;
    if (projectId) this.store.setProject(projectId);

    const ids = this.store.members().map((m) => m.id);
    if (mode === 'alert') {
      if (ids.includes('tanaka')) this.store.focusMember('tanaka');
      if (ids.includes('kobayashi')) this.store.focusMember('kobayashi');
    } else {
      if (ids.includes('yamada')) this.store.focusMember('yamada');
      if (ids.includes('suzuki')) this.store.focusMember('suzuki');
    }

    await this.store.runSimulation();
    this.openOverlay(mode);
  }

  protected openOverlay(mode: 'alert' | 'manual'): void {
    const r = this.store.simulationResult();
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
    this.overlayMode.set(mode);
    this.overlayOpen.set(true);
    this.overlayLog.set([]);
    this.selectedPlanId.set(this.recommendedPlan()?.planType ?? null);

    const initialEmotion = this.emotionForOverlay(mode, r);
    this.overlayChat.set([
      {
        from: 'ai',
        emotion: initialEmotion,
        text: r
          ? `状況を整理しました。推奨プランは「${r.agents.gunshi.recommend}」です。プラン選択後、必要なら指示を追加し、最後に承認してください。`
          : 'まずシミュレーションを実行してください。',
      },
    ]);

    if (r) {
      if (mode === 'alert') {
        this.overlayKpiLabel.set('RISK');
        this.overlayKpiVal.set(`${r.metrics.riskPct}%`);
        this.overlayKpiDesc.set(`pattern=${r.pattern} / 離職・炎上の兆候を検知`);
      } else {
        this.overlayKpiLabel.set('GROWTH');
        this.overlayKpiVal.set(`${r.metrics.careerFitPct}%`);
        this.overlayKpiDesc.set('介入で未来を良い方向へ固定化します');
      }

      const toneOf = (agentId: string): 'pm' | 'hr' | 'risk' | 'gunshi' => {
        switch (agentId) {
          case 'PM':
            return 'pm';
          case 'HR':
            return 'hr';
          case 'RISK':
            return 'risk';
          default:
            return 'gunshi';
        }
      };

      const script: { agent: string; tone: 'pm' | 'hr' | 'risk' | 'gunshi'; text: string }[] = r
        .meetingLog?.length
        ? [
            { agent: 'System', tone: 'gunshi', text: `対象: ${r.project.name}` },
            ...r.meetingLog.map((e) => ({
              agent: e.agent_id,
              tone: toneOf(e.agent_id),
              text: `${e.message} (DECISION=${e.decision}, RISK=${e.risk_score})`,
            })),
          ]
        : [
            { agent: 'System', tone: 'gunshi', text: `対象: ${r.project.name}` },
            {
              agent: 'PM',
              tone: 'pm',
              text: `SKILL_FIT=${r.metrics.skillFitPct}% / BUDGET=${r.metrics.budgetPct}%`,
            },
            {
              agent: 'HR',
              tone: 'hr',
              text: `${r.agents.hr.vote === 'ng' ? '燃え尽き/負荷' : '成長機会'} の観点で ${r.agents.hr.vote}`,
            },
            {
              agent: 'RISK',
              tone: 'risk',
              text: `INCIDENT_RISK=${r.metrics.riskPct}% / pattern=${r.pattern}`,
            },
            {
              agent: 'Gunshi',
              tone: 'gunshi',
              text: `結論: Plan ${r.agents.gunshi.recommend}（${r.agents.gunshi.note}）`,
            },
          ];
      this.playLog(script);
    }
  }

  protected closeOverlay(): void {
    this.overlayOpen.set(false);
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
  }

  protected selectPlan(id: 'A' | 'B' | 'C'): void {
    this.selectedPlanId.set(id);
    this.overlayChat.update((curr) => [
      ...curr,
      {
        from: 'ai',
        emotion: 'effort',
        text: `Plan ${id} を選択しました。条件を追加するか、承認してください。`,
      },
    ]);
  }

  protected approvePlan(): void {
    const selected = this.selectedPlanId() ?? this.recommendedPlan()?.planType ?? 'A';
    this.overlayChat.update((curr) => [
      ...curr,
      { from: 'ai', emotion: 'relief', text: `Plan ${selected} を承認しました。実行します。` },
    ]);
    const t = window.setTimeout(() => this.closeOverlay(), 900);
    this.timers.push(t);
  }

  protected sendChat(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) return;

    this.overlayChat.update((curr) => [...curr, { from: 'user', text: trimmed }]);
    const tone = this.emotionFromChatRequest(trimmed);
    const t = window.setTimeout(() => {
      this.overlayChat.update((curr) => [
        ...curr,
        {
          from: 'ai',
          emotion: tone,
          text: `承知しました。「${trimmed}」方針で再計算します。`,
        },
      ]);
    }, 450);
    this.timers.push(t);
  }

  protected haisaEmotionLabel(emotion?: HaisaEmotion): string {
    return resolveHaisaEmotionLabel(emotion ?? 'standard');
  }

  protected overlayHaisaEmotion(): HaisaEmotion {
    const chat = this.overlayChat();
    for (let i = chat.length - 1; i >= 0; i -= 1) {
      const entry = chat[i];
      if (entry?.from !== 'user') return entry.emotion ?? 'standard';
    }
    return 'standard';
  }

  protected haisaAvatarSrc(emotion: HaisaEmotion = 'standard'): string {
    return resolveHaisaAvatarSrc(emotion);
  }

  private emotionForOverlay(
    mode: 'alert' | 'manual',
    result: SimulationResult | null
  ): HaisaEmotion {
    if (!result) return mode === 'alert' ? 'haste' : 'effort';
    if (mode === 'alert') {
      return haisaEmotionForRisk(result.metrics.riskPct ?? 0);
    }
    return haisaEmotionForFit(result.metrics.careerFitPct ?? 0);
  }

  private emotionFromChatRequest(text: string): HaisaEmotion {
    if (text.includes('承認')) return 'relief';
    if (text.includes('再計算') || text.includes('調整')) return 'energy';
    if (text.includes('Plan')) return 'effort';
    if (text.includes('危険') || text.includes('爆発')) return 'haste';
    return 'hope';
  }

  private playLog(
    lines: { agent: string; tone: 'pm' | 'hr' | 'risk' | 'gunshi'; text: string }[]
  ): void {
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
    lines.forEach((l, i) => {
      const t = window.setTimeout(() => {
        this.overlayLog.update((curr) => [...curr, l]);
      }, i * 450);
      this.timers.push(t);
    });
  }
}
