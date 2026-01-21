import { CommonModule, DecimalPipe } from '@angular/common';
import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Subscription, firstValueFrom } from 'rxjs';

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
import { ApiClient } from '../core/api-client';
import { SimulatorStore } from '../core/simulator-store';
import {
  Member,
  PlanStreamTone,
  ProjectTeamMember,
  SimulationPlan,
  SimulationResult,
  TeamSuggestion,
} from '../core/types';

interface ChatEntry {
  from: 'ai' | 'user';
  text: string;
  emotion?: HaisaEmotion;
}

type BadgeTone = 'good' | 'warn' | 'risk' | 'neutral';

interface MemberBadge {
  label: string;
  value: string;
  tone: BadgeTone;
}


const LEADER_NAME_TOKENS = ['sato', '佐藤'];
const VETERAN_NAME_TOKENS = ['tanaka', '田中'];
const COMPRESSED_COST = 30;
const PLAN_STREAM_LABEL_COLORS: Record<PlanStreamTone, string> = {
  pm: '#2563EB',
  hr: '#16A34A',
  risk: '#D97706',
  gunshi: '#7C3AED',
};
const PLAN_STREAM_LABELS: Record<PlanStreamTone, string> = {
  pm: 'PM',
  hr: 'HR',
  risk: 'RISK',
  gunshi: '軍師',
};

@Component({
  imports: [CommonModule, DecimalPipe, NeuralOrbComponent, HaisaSpeechComponent, EmptyStateComponent],
  template: `
    <ng-template #progressStreamTemplate>
      <div class="rounded-xl border border-slate-800 bg-slate-900/30 p-3">
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm font-semibold">AI進捗ストリーム</span>
          <span class="text-xs text-slate-300">{{ store.planProgress()?.progress ?? 0 }}%</span>
        </div>
        <div class="mt-2 flex items-center justify-between text-xs text-slate-400">
          <span>{{ store.planProgress()?.phase ?? 'idle' }}</span>
          <span class="text-slate-200">{{ store.planProgress()?.progress ?? 0 }}%</span>
        </div>
        <div class="mt-2 h-2 rounded bg-slate-800 overflow-hidden">
          <div class="h-2 bg-indigo-500" [style.width.%]="store.planProgress()?.progress ?? 0">
          </div>
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <div class="ui-kicker">Progress Log</div>
            @if (store.planProgressLog().length) {
              <ul
                class="mt-2 space-y-1 text-xs text-slate-300 h-40 overflow-hidden flex flex-col justify-end leading-snug"
              >
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
              <ul
                class="mt-2 space-y-2 text-xs h-40 overflow-hidden flex flex-col justify-end leading-snug"
              >
                @for (entry of store.planDiscussionLog(); track $index) {
                  <li class="flex items-start gap-2">
                    <span
                      class="shrink-0 w-[7ch] px-2 py-0.5 rounded-md border border-slate-700 bg-slate-900/60 text-left"
                      [style.color]="planStreamLabelColors[entry.tone]"
                    >
                      {{ planStreamLabels[entry.tone] }}
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
    </ng-template>

    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0">
        <div class="ui-kicker">Tactical Simulator</div>
        <h2 class="mt-1 text-xl sm:text-2xl font-extrabold tracking-tight">戦術シミュレーター</h2>
        <p class="mt-1 text-sm text-slate-300 max-w-2xl">
          案件を選び、メンバー選択あり/なしで AI による編成案と介入プランを確認します。
        </p>
      </div>

      <div class="w-full lg:w-[300px]">
        <div class="ui-panel p-3">
          <div class="ui-kicker">Next Action</div>
          @if (store.loading() || store.streaming()) {
            <div class="mt-1 text-sm font-semibold text-slate-100">AIが編成中</div>
            <div class="mt-1 text-xs text-slate-400">進捗ストリームを更新中。</div>
            <div class="mt-3">
              <span
                class="ui-pill border-indigo-500/40 bg-indigo-500/10 text-indigo-100 inline-flex items-center gap-2"
                role="status"
              >
                <svg
                  class="h-3 w-3 animate-spin text-indigo-200"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    class="opacity-30"
                    cx="12"
                    cy="12"
                    r="10"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="3"
                  ></circle>
                  <path
                    class="opacity-90"
                    fill="currentColor"
                    d="M12 2a10 10 0 0 1 9.54 6.5l-2.8 1.1A7 7 0 0 0 12 5V2z"
                  ></path>
                </svg>
                <span>processing / waiting</span>
              </span>
            </div>
          } @else if (store.teamSuggestions().length) {
            <div class="mt-1 text-sm font-semibold text-slate-100">編成案を選択</div>
            <div class="mt-1 text-xs text-slate-400">候補から1案を適用してシミュレーションします。</div>
          } @else if (validSimulationResult()) {
            @if (interventionCompleted()) {
              <div class="mt-1 text-sm font-semibold text-slate-100">介入完了</div>
              <div class="mt-1 text-xs text-slate-400">プランの実行を反映しました。</div>
            } @else {
              <div class="mt-1 text-sm font-semibold text-slate-100">介入へ</div>
              <div class="mt-1 text-xs text-slate-400">結果セクションで介入に進みます。</div>
            }
          } @else if (canRunSimulation()) {
            @if (store.selectedMemberIds().length) {
              <div class="mt-1 text-sm font-semibold text-slate-100">実行準備完了</div>
              <div class="mt-1 text-xs text-slate-400">選択メンバーでシミュレーションします。</div>
            } @else {
              <div class="mt-1 text-sm font-semibold text-slate-100">候補プールから提案</div>
              <div class="mt-1 text-xs text-slate-400">未選択のまま実行すると編成案を提示します。</div>
            }
          } @else {
            <div class="mt-1 text-sm font-semibold text-slate-100">対象を選択</div>
            <div class="mt-1 text-xs text-slate-400">案件を選んで開始します。</div>
          }
        </div>
      </div>
    </div>

    @if (store.error(); as err) {
      <div class="mb-3 mt-3">
        <app-haisa-speech [tone]="'error'" [message]="err" [compact]="true" [showAvatar]="false" />
      </div>
    }

    <div class="mt-3 ui-panel-muted ui-flow-panel p-3">
      <div class="ui-flow-label">Flow</div>
      <ol class="mt-2 grid gap-2 sm:grid-cols-4 text-xs">
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

    <div class="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <section class="ui-panel p-3" id="simulator-input">
        <div class="flex items-center justify-between gap-3 mb-2">
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
            <option [value]="p.id">{{ p.name }}（予算 {{ p.budget | number:'1.0-0' }}）</option>
          }
        </select>

        <div class="mt-3 flex items-center justify-between">
          <div class="text-sm text-slate-300">Candidate Pool</div>
          <div class="text-xs text-slate-400">{{ store.members().length }} 名</div>
        </div>

        <div
          class="mt-2 grid gap-2 max-h-[300px] overflow-auto pr-1 sm:grid-cols-2 sm:max-h-[340px] lg:max-h-[420px] xl:grid-cols-3"
        >
          @for (m of store.members(); track m.id) {
            <button
              type="button"
              class="member-card ui-panel-interactive text-left"
              [class.member-card--selected]="store.selectedMemberIds().includes(m.id)"
              (click)="store.toggleMember(m.id)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="font-semibold text-slate-100 truncate">{{ m.name }}</div>
                  <div class="text-xs text-slate-400 truncate">{{ memberRoleLabel(m) }}</div>
                </div>
                <div class="text-right shrink-0">
                  <div class="text-sm text-slate-200 font-bold">¥{{ m.cost | number:'1.0-0' }}</div>
                  <div class="text-[11px] text-slate-400">{{ m.availability }}%</div>
                </div>
              </div>
              <div class="mt-2 text-xs text-slate-400 break-words">{{ m.skills.join(', ') }}</div>
              <div class="mt-3 flex flex-wrap gap-2">
                @for (badge of memberBadges(m); track badge.label) {
                  <span
                    class="member-badge"
                    [class.badge-good]="badge.tone === 'good'"
                    [class.badge-warn]="badge.tone === 'warn'"
                    [class.badge-risk]="badge.tone === 'risk'"
                    [class.badge-neutral]="badge.tone === 'neutral'"
                  >
                    <span class="member-badge-label">{{ badge.label }}</span>
                    <span class="member-badge-value">{{ badge.value }}</span>
                  </span>
                }
              </div>
              <div class="mt-3 text-[11px] text-slate-400">
                {{ store.selectedMemberIds().includes(m.id) ? '選択中' : 'クリックで追加' }}
              </div>
            </button>
          }
        </div>

        <div class="mt-3">
          <div class="text-sm text-slate-300">Split View</div>
          <div class="mt-2 space-y-2">
            <div class="rounded-xl border border-slate-800 bg-slate-950/30 p-3">
              <div class="flex items-center justify-between text-xs text-slate-400">
                <span>Current (Read-only)</span>
                <span>{{ store.currentTeam().length }} 名</span>
              </div>
              @if (store.currentTeamLoading()) {
                <div class="mt-2 text-xs text-slate-400">loading current team…</div>
              } @else if (store.currentTeamError(); as err) {
                <div class="mt-2 text-xs text-rose-200">{{ err }}</div>
              } @else if (store.currentTeam().length) {
                <div class="mt-3 grid gap-2 sm:grid-cols-2 max-h-[260px] overflow-auto pr-1">
                  @for (m of store.currentTeam(); track m.id) {
                    <div class="member-card member-card--readonly">
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <div class="font-semibold text-slate-100 truncate">{{ m.name }}</div>
                          <div class="text-xs text-slate-400 truncate">
                            {{ currentRoleLabel(m) }}
                            @if (allocationLabel(m.assignment?.allocationRate); as rateLabel) {
                              <span class="ml-2 text-slate-500">{{ rateLabel }}</span>
                            }
                          </div>
                        </div>
                        <div class="text-right shrink-0">
                          <div class="text-sm text-slate-200 font-bold">¥{{ m.cost | number:'1.0-0' }}</div>
                          <div class="text-[11px] text-slate-400">{{ m.availability }}%</div>
                        </div>
                      </div>
                      <div class="mt-2 text-xs text-slate-400 break-words">
                        {{ m.skills.join(', ') }}
                      </div>
                      <div class="mt-3 flex flex-wrap gap-2">
                        @for (badge of memberBadges(m); track badge.label) {
                          <span
                            class="member-badge"
                            [class.badge-good]="badge.tone === 'good'"
                            [class.badge-warn]="badge.tone === 'warn'"
                            [class.badge-risk]="badge.tone === 'risk'"
                            [class.badge-neutral]="badge.tone === 'neutral'"
                          >
                            <span class="member-badge-label">{{ badge.label }}</span>
                            <span class="member-badge-value">{{ badge.value }}</span>
                          </span>
                        }
                      </div>
                    </div>
                  }
                </div>
              } @else {
                <div class="mt-2 text-xs text-slate-500">現状チームのデータがありません。</div>
              }
            </div>

            <div class="rounded-xl border border-slate-800 bg-slate-950/30 p-3">
              <div class="flex items-center justify-between text-xs text-slate-400">
                <span>Simulation (Editable)</span>
                @if (store.selectedMemberIds().length) {
                  <button
                    type="button"
                    class="text-[11px] px-2 py-1 rounded border border-slate-700 hover:border-slate-500 ui-focus-ring"
                    (click)="store.clearSelection()"
                  >
                    選択解除
                  </button>
                }
              </div>
              @if (store.selectedMembers().length) {
                <div class="mt-3 grid gap-2 sm:grid-cols-2 max-h-[260px] overflow-auto pr-1">
                  @for (m of store.selectedMembers(); track m.id) {
                    <button
                      type="button"
                      class="member-card member-card--selected text-left"
                      (click)="store.toggleMember(m.id)"
                      [title]="'クリックで外す: ' + m.name"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <div class="font-semibold text-slate-100 truncate">{{ m.name }}</div>
                          <div class="text-xs text-slate-400 truncate">
                            {{ memberRoleLabel(m, store.selectedMembers(), true) }}
                          </div>
                        </div>
                        <div class="text-right shrink-0">
                          <div class="text-sm text-slate-200 font-bold">
                            ¥{{ memberCostValue(m, store.selectedMembers(), true) | number:'1.0-0' }}
                          </div>
                          @if (memberCostAdjusted(m, store.selectedMembers())) {
                            <div class="text-[10px] text-slate-500 line-through">
                              ¥{{ m.cost | number:'1.0-0' }}
                            </div>
                          } @else {
                            <div class="text-[11px] text-slate-400">{{ m.availability }}%</div>
                          }
                        </div>
                      </div>
                      <div class="mt-2 text-xs text-slate-400 break-words">
                        {{ m.skills.join(', ') }}
                      </div>
                      <div class="mt-3 flex flex-wrap gap-2">
                        @for (badge of memberBadges(m); track badge.label) {
                          <span
                            class="member-badge"
                            [class.badge-good]="badge.tone === 'good'"
                            [class.badge-warn]="badge.tone === 'warn'"
                            [class.badge-risk]="badge.tone === 'risk'"
                            [class.badge-neutral]="badge.tone === 'neutral'"
                          >
                            <span class="member-badge-label">{{ badge.label }}</span>
                            <span class="member-badge-value">{{ badge.value }}</span>
                          </span>
                        }
                      </div>
                      <div class="mt-3 text-[11px] text-slate-400">クリックで外す</div>
                    </button>
                  }
                </div>
              } @else {
                <div class="mt-2 text-xs text-slate-500">
                  メンバーを選択するか、未選択のまま AI自動編成 を実行してください
                </div>
              }
            </div>
          </div>

          <div class="mt-3">
            <div class="flex items-center justify-between text-xs text-slate-400">
              <span>予算消化率</span>
              <span class="text-slate-200"
                >{{ budgetUsed() | number:'1.0-0' }} / {{
                  (store.selectedProject()?.budget ?? 0) | number:'1.0-0'
                }}</span
              >
            </div>
            @if (compressionActive()) {
              <div class="mt-1 text-[11px] text-emerald-200">
                Advisor cost compression applied
              </div>
            }
            <div class="mt-2 h-2 rounded bg-slate-800 overflow-hidden">
              <div
                class="h-2"
                [style.width.%]="budgetPct()"
                [style.background]="budgetBarColor()"
              ></div>
            </div>
          </div>
        </div>

        @if (validSimulationResult()) {
          <button
            type="button"
            class="mt-3 w-full ui-button-secondary disabled:opacity-60"
            [disabled]="store.loading()"
            (click)="store.runSimulation()"
          >
            再シミュレーション
          </button>
        } @else {
          <button
            type="button"
            class="mt-3 w-full ui-button-primary disabled:opacity-60"
            [disabled]="store.loading() || !canRunSimulation()"
            (click)="store.runSimulation()"
          >
            AI自動編成
          </button>
        }
        @if (store.loading()) {
          <div class="text-xs text-slate-400 mt-2">running…</div>
        }

        @if (!validSimulationResult() && store.teamSuggestionsResponse(); as suggestionResponse) {
          @if (suggestionResponse.suggestions.length) {
            <div class="mt-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <div class="ui-kicker">Team Suggestions</div>
                  <div class="mt-1 text-xs text-slate-400">
                    availability ≥ {{ suggestionResponse.minAvailability }}% / candidates
                    {{ suggestionResponse.candidateCount }}
                  </div>
                </div>
                <div class="text-xs text-slate-400">
                  {{ suggestionResponse.project.name }}
                </div>
              </div>

              <div class="mt-3 grid gap-2 max-h-[320px] overflow-auto pr-1">
                @for (s of suggestionResponse.suggestions; track s.id) {
                  <div class="rounded-xl border border-slate-800 bg-slate-900/30 p-3">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <div class="text-sm font-semibold text-slate-100 truncate">案 {{ s.id }}</div>
                        <div class="mt-1 text-xs text-slate-400 break-words">{{ s.why }}</div>
                        @if (s.missingSkills.length) {
                          <div class="mt-2 text-[11px] text-rose-200">
                            不足: {{ s.missingSkills.join(', ') }}
                          </div>
                        }
                      </div>
                      <div class="flex flex-col items-end gap-2 shrink-0">
                        @if (s.source === 'external') {
                          <span class="ui-pill border-slate-500/40 bg-slate-500/10 text-slate-200">
                            External
                          </span>
                        }
                        @if (s.isRecommended) {
                          <span class="ui-pill border-emerald-500/40 bg-emerald-500/10 text-emerald-200">
                            Recommended
                          </span>
                        }
                      </div>
                    </div>

                    @if (s.metrics) {
                      <div class="mt-3 flex flex-wrap gap-2 text-xs">
                        <span class="ui-pill border-indigo-500/40 bg-indigo-500/10 text-indigo-100">
                          skill {{ s.metrics.skillFitPct }}%
                        </span>
                        <span class="ui-pill border-rose-500/40 bg-rose-500/10 text-rose-200">
                          risk {{ s.metrics.riskPct }}%
                        </span>
                        <span class="ui-pill border-slate-500/40 bg-slate-500/10 text-slate-200">
                          budget {{ s.metrics.budgetPct }}%
                        </span>
                      </div>
                    }

                    <div class="mt-3 grid gap-2 sm:grid-cols-2">
                      @for (m of s.team; track m.id) {
                        <div class="rounded-lg border border-slate-800 bg-slate-950/30 p-2">
                          <div class="flex items-start justify-between gap-2">
                            <div class="min-w-0">
                              <div class="text-sm font-semibold text-slate-100 truncate">
                                {{ m.name }}
                              </div>
                              <div class="text-[11px] text-slate-400 truncate">
                                {{ m.role ?? '—' }}
                              </div>
                            </div>
                            <div class="text-right shrink-0 text-[11px] text-slate-400">
                              @if (m.cost != null) {
                                <div>¥{{ m.cost | number:'1.0-0' }}</div>
                              } @else {
                                <div>--</div>
                              }
                              @if (m.availability != null) {
                                <div>{{ m.availability }}%</div>
                              } @else {
                                <div>--</div>
                              }
                            </div>
                          </div>
                        </div>
                      }
                    </div>

                    <div class="mt-3 flex items-center justify-end">
                      @if (s.applyable) {
                        <button
                          type="button"
                          class="ui-button-primary text-xs disabled:opacity-60"
                          [disabled]="store.loading()"
                          (click)="applySuggestion(s)"
                        >
                          適用してシミュレーション
                        </button>
                      } @else {
                        <div class="text-xs text-slate-400">外部調達枠のため適用できません</div>
                      }
                    </div>
                  </div>
                }
              </div>
            </div>
          }
        }
      </section>

      <section class="ui-panel p-3 lg:sticky lg:top-6 lg:max-h-[calc(100vh-8rem)] lg:overflow-auto">
        <div class="flex items-center justify-between gap-3 mb-2">
          <div class="font-semibold">2. 結果</div>
          @if (validSimulationResult()) {
            <button type="button" class="ui-button-primary text-xs" (click)="openOverlay('manual')">
              介入へ
            </button>
          } @else {
            <button type="button" class="ui-button-secondary text-xs" disabled>
              介入チェックポイント
            </button>
          }
        </div>

        @if (
          store.streaming() || store.planProgressLog().length || store.planDiscussionLog().length
        ) {
          <div class="mb-3">
            <ng-container [ngTemplateOutlet]="progressStreamTemplate"></ng-container>
          </div>
        }

        @if (validSimulationResult(); as r) {
          <div class="ui-panel-muted p-3">
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

          <div class="mt-3 grid gap-2 sm:grid-cols-2">
            <div class="rounded border border-slate-800 bg-slate-900/30 p-3">
              <div class="text-xs text-slate-400">予算</div>
              <div class="mt-1 text-sm">
                {{ r.metrics.budgetUsed | number:'1.0-0' }} / {{
                  r.project.budget | number:'1.0-0'
                }}（{{ r.metrics.budgetPct }}%）
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

          <div class="mt-3">
            <details class="rounded-xl border border-slate-800 bg-slate-900/30 p-3" #coverageDetails>
              <summary
                class="ui-accordion__summary ui-focus-ring"
                [attr.aria-expanded]="coverageDetails.open"
                aria-controls="requirement-coverage-panel"
              >
                <span>要件カバー率</span>
                <span class="ui-accordion__meta">
                  <svg
                    class="ui-accordion__icon"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.06l3.71-3.83a.75.75 0 1 1 1.08 1.04l-4.24 4.37a.75.75 0 0 1-1.08 0L5.21 8.27a.75.75 0 0 1 .02-1.06Z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </span>
              </summary>
              <div id="requirement-coverage-panel" class="ui-accordion__content">
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
              </div>
            </details>
          </div>

          <div class="mt-3">
            <details class="rounded-xl border border-slate-800 bg-slate-900/30 p-3" #timelineDetails>
              <summary
                class="ui-accordion__summary ui-focus-ring"
                [attr.aria-expanded]="timelineDetails.open"
                aria-controls="future-timeline-panel"
              >
                <span>未来タイムライン</span>
                <span class="ui-accordion__meta">
                  <svg
                    class="ui-accordion__icon"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.06l3.71-3.83a.75.75 0 1 1 1.08 1.04l-4.24 4.37a.75.75 0 0 1-1.08 0L5.21 8.27a.75.75 0 0 1 .02-1.06Z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </span>
              </summary>
              <div id="future-timeline-panel" class="ui-accordion__content">
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
              </div>
            </details>
          </div>

          <div class="mt-3">
            <details class="rounded-xl border border-slate-800 bg-slate-900/30 p-3" #agentDetails>
              <summary
                class="ui-accordion__summary ui-focus-ring"
                [attr.aria-expanded]="agentDetails.open"
                aria-controls="agent-insights-panel"
              >
                <span>エージェント所見</span>
                <span class="ui-accordion__meta">
                  <svg
                    class="ui-accordion__icon"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.06l3.71-3.83a.75.75 0 1 1 1.08 1.04l-4.24 4.37a.75.75 0 0 1-1.08 0L5.21 8.27a.75.75 0 0 1 .02-1.06Z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </span>
              </summary>
              <div id="agent-insights-panel" class="ui-accordion__content">
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
                      <span class="text-indigo-300">{{ recommendedPlan()?.planType ?? '-' }}</span>
                    </div>
                    <div class="text-xs text-slate-300 mt-1">{{ r.agents.gunshi.note }}</div>
                  </div>
                </div>
              </div>
            </details>
          </div>

          <div class="mt-3">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="text-sm font-semibold">プラン選択</div>
                <div class="mt-1 text-xs text-slate-400">
                  AI推奨: Plan {{ recommendedPlan()?.planType ?? '-' }}
                </div>
              </div>
              @if (activePlanType(); as selected) {
                <span class="ui-pill border-indigo-500/40 bg-indigo-500/10 text-indigo-100">
                  選択中 Plan {{ selected }}
                </span>
              }
            </div>

            <div class="mt-3 grid gap-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
              @for (p of r.plans; track p.id) {
                <button
                  type="button"
                  class="relative text-left rounded-xl border bg-slate-900/30 px-3 pb-3 pt-8 transition hover:border-slate-500 ui-focus-ring"
                  [class.border-indigo-500/70]="activePlanType() === p.planType"
                  [class.bg-indigo-500/10]="activePlanType() === p.planType"
                  [class.border-slate-800]="activePlanType() !== p.planType"
                  [attr.aria-pressed]="activePlanType() === p.planType"
                  (click)="setActivePlan(p.planType)"
                >
                  @if (p.planType === recommendedPlan()?.planType) {
                    <div
                      class="absolute right-2 top-2 text-[10px] px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-200 font-bold"
                    >
                      AI推奨
                    </div>
                  }
                  @if (activePlanType() === p.planType) {
                    <div
                      class="absolute left-2 top-2 text-[10px] px-2 py-1 rounded-full bg-indigo-500/20 text-indigo-100 font-bold"
                    >
                      選択中
                    </div>
                  }
                  <div class="font-semibold text-slate-100 leading-tight">
                    Plan {{ p.planType }}
                  </div>
                  <div class="mt-1 text-xs text-slate-300 break-words">{{ p.summary }}</div>
                </button>
              }
            </div>

            @if (activePlan(); as plan) {
              <div class="mt-3 rounded-xl border border-slate-800 bg-slate-900/30 p-3">
                <div class="flex items-center justify-between gap-2">
                  <div class="font-semibold text-slate-100">
                    Plan {{ plan.planType }}: {{ plan.summary }}
                  </div>
                  @if (plan.planType === recommendedPlan()?.planType) {
                    <span
                      class="text-[10px] font-bold tracking-wider rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-emerald-200"
                    >
                      AI推奨
                    </span>
                  }
                </div>
                <div class="mt-2 text-xs text-slate-300">
                  pros: {{ plan.prosCons.pros.join(' / ') }}
                </div>
                <div class="mt-1 text-xs text-slate-300">
                  cons: {{ plan.prosCons.cons.join(' / ') }}
                </div>
              </div>
            } @else {
              <div class="mt-3 text-xs text-slate-400">プランがありません。</div>
            }
          </div>
        } @else {
          <app-empty-state
            kicker="Empty"
            title="結果はまだありません"
            description="案件を選択してください。メンバー未選択でも AI が編成案を提案します。"
          />
        }
      </section>
    </div>

    @if (overlayOpen()) {
      <div class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/70" (click)="closeOverlay()"></div>
        <div
          class="absolute inset-0 sm:inset-6 lg:inset-8 xl:inset-10 rounded-none sm:rounded-2xl overflow-hidden border border-slate-800 bg-slate-950/70 surface-overlay"
        >
          <app-neural-orb class="absolute inset-0 opacity-30 pointer-events-none"></app-neural-orb>

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
                @if (activePlanType(); as selected) {
                  <span class="ui-pill border-indigo-500/40 bg-indigo-500/10 text-indigo-100">
                    選択中 Plan {{ selected }}
                  </span>
                }
              </div>
              <button
                type="button"
                class="text-slate-300 hover:text-white text-2xl leading-none shrink-0"
                (click)="closeOverlay()"
              >
                ×
              </button>
            </div>

            <div class="flex-1 min-h-0 overflow-y-auto" data-overlay-scroll>
              <div
                class="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(320px,40%)] lg:gap-0 min-h-full"
              >
                <div
                  class="border-b lg:border-b-0 lg:border-r border-slate-800/80 flex flex-col min-h-0 overflow-visible lg:overflow-hidden"
                >
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
                    @if (validSimulationResult(); as r) {
                      <div class="mt-2 text-sm text-slate-200 font-semibold">
                        推奨 Plan {{ recommendedPlan()?.planType ?? '-' }}
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
                    <div
                      class="p-4 sm:p-5 space-y-2 font-mono text-xs min-h-0 lg:flex-1 lg:overflow-auto"
                    >
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
                          <span class="text-slate-200 flex-1 min-w-0 break-words">{{
                            l.text
                          }}</span>
                        </div>
                      }
                    </div>
                  </details>
                </div>

                <div class="flex flex-col min-h-0 overflow-visible lg:overflow-hidden">
                  @if (
                    store.streaming() ||
                    store.planProgressLog().length ||
                    store.planDiscussionLog().length
                  ) {
                    <div class="p-4 sm:p-5 border-b border-slate-800/80">
                      <ng-container [ngTemplateOutlet]="progressStreamTemplate"></ng-container>
                    </div>
                  }

                  <div class="p-4 sm:p-5 border-b border-slate-800/80">
                    <div class="ui-kicker">Step 2: 選ぶ</div>
                    <div class="text-sm font-bold text-slate-100">戦略プランの選択</div>
                    @if (validSimulationResult(); as r) {
                      <div class="mt-3 grid gap-3 grid-cols-1 sm:grid-cols-2">
                        @for (p of r.plans; track p.id) {
                          <button
                            type="button"
                            class="relative text-left rounded-xl border bg-slate-900/40 px-4 pb-4 pt-8 hover:bg-slate-900/55 status-plan ui-focus-ring"
                            [class.border-indigo-500]="activePlanType() === p.planType"
                            [class.bg-indigo-500/10]="activePlanType() === p.planType"
                            [class.border-slate-800]="activePlanType() !== p.planType"
                            [attr.aria-pressed]="activePlanType() === p.planType"
                            (click)="selectPlan(p.planType)"
                          >
                            @if (p.planType === recommendedPlan()?.planType) {
                              <div
                                class="absolute right-2 top-2 text-[10px] px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-200 font-bold"
                              >
                                AI推奨
                              </div>
                            }
                            @if (activePlanType() === p.planType) {
                              <div
                                class="absolute left-2 top-2 text-[10px] px-2 py-1 rounded-full bg-indigo-500/20 text-indigo-100 font-bold"
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
                          <div
                            class="text-[11px] text-slate-400 font-semibold uppercase tracking-wider"
                          >
                            サイハイくん
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
                        placeholder="指示を入力（空欄で承認）"
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
                        <button type="button" class="ui-button-primary" (click)="approvePlan()">
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
  private readonly api = inject(ApiClient);
  protected readonly planStreamLabelColors = PLAN_STREAM_LABEL_COLORS;
  protected readonly planStreamLabels = PLAN_STREAM_LABELS;

  protected readonly overlayOpen = signal(false);
  protected readonly overlayMode = signal<'alert' | 'manual'>('alert');
  protected readonly overlayKpiLabel = signal('RISK');
  protected readonly overlayKpiVal = signal('--%');
  protected readonly overlayKpiDesc = signal('');

  protected readonly overlayLog = signal<
    { agent: string; tone: 'pm' | 'hr' | 'risk' | 'gunshi'; text: string }[]
  >([]);
  protected readonly overlayChat = signal<ChatEntry[]>([]);
  protected readonly chatSending = signal(false);

  protected readonly selectedPlanId = signal<'A' | 'B' | 'C' | null>(null);
  private readonly approvedSimulationId = signal<string | null>(null);

  protected readonly validSimulationResult = computed<SimulationResult | null>(() => {
    const result = this.store.simulationResult();
    if (!result) return null;
    const projectId = this.store.selectedProjectId();
    if (!projectId || result.project.id !== projectId) return null;
    const selectedIds = this.store.selectedMemberIds();
    if (!selectedIds.length) return null;
    const teamIds = result.team.map((member) => member.id);
    if (teamIds.length !== selectedIds.length) return null;
    const teamSet = new Set(teamIds);
    for (const memberId of selectedIds) {
      if (!teamSet.has(memberId)) return null;
    }
    return result;
  });

  protected readonly steps = [
    { id: 1, label: '対象選択' },
    { id: 2, label: 'AI実行' },
    { id: 3, label: '結果確認' },
    { id: 4, label: '介入' },
  ];

  protected readonly currentStep = computed(() => {
    if (this.store.loading() || this.store.streaming()) return 2;
    if (this.store.teamSuggestions().length) return 2;
    if (this.validSimulationResult()) {
      return this.interventionCompleted() ? 5 : 4;
    }
    return 1;
  });

  protected readonly interventionCompleted = computed(() => {
    const result = this.validSimulationResult();
    if (!result) return false;
    return this.approvedSimulationId() === result.id;
  });

  protected readonly canRunSimulation = computed(() => {
    return Boolean(this.store.selectedProjectId());
  });

  protected readonly recommendedPlan = computed<SimulationPlan | null>(() => {
    const result = this.validSimulationResult();
    if (!result?.plans?.length) return null;
    const recommendedType = result.agents?.gunshi?.recommend ?? null;
    const recommended =
      recommendedType != null
        ? result.plans.find((p) => p.planType === recommendedType)
        : null;
    return recommended ?? result.plans[0] ?? null;
  });

  protected readonly activePlanType = computed<'A' | 'B' | 'C' | null>(() => {
    return this.selectedPlanId() ?? this.recommendedPlan()?.planType ?? null;
  });

  protected readonly activePlan = computed<SimulationPlan | null>(() => {
    const result = this.validSimulationResult();
    if (!result?.plans?.length) return null;
    const selected = this.activePlanType();
    return (
      result.plans.find((p) => p.planType === selected) ??
      this.recommendedPlan() ??
      result.plans[0] ??
      null
    );
  });

  protected readonly compressionActive = computed(() =>
    this.isCompressionActive(this.store.selectedMembers())
  );
  protected readonly budgetUsed = computed(() =>
    this.teamCost(this.store.selectedMembers(), true)
  );
  protected readonly budgetPct = computed(() => {
    const budget = this.store.selectedProject()?.budget ?? 0;
    if (!budget) return 0;
    return Math.min(100, Math.round((this.budgetUsed() / budget) * 100));
  });
  protected readonly budgetBarColor = computed(() =>
    this.budgetPct() >= 100 ? '#f43f5e' : '#06b6d4'
  );

  protected memberBadges(member: Member): MemberBadge[] {
    const analysis = member.analysis;
    const matchScore =
      analysis?.pmRiskScore != null ? Math.max(0, 100 - analysis.pmRiskScore) : null;
    const valueScore =
      analysis?.hrRiskScore != null ? Math.max(0, 100 - analysis.hrRiskScore) : null;
    const riskScore = analysis?.riskRiskScore != null ? analysis.riskRiskScore : null;

    return [
      {
        label: 'Match',
        value: matchScore == null ? '--' : this.matchLabel(matchScore),
        tone: matchScore == null ? 'neutral' : this.scoreTone(matchScore),
      },
      {
        label: 'Value',
        value: valueScore == null ? '--' : this.valueLabel(valueScore),
        tone: valueScore == null ? 'neutral' : this.scoreTone(valueScore),
      },
      {
        label: 'Risk',
        value: riskScore == null ? '--' : this.riskLabel(riskScore),
        tone: riskScore == null ? 'neutral' : this.riskTone(riskScore),
      },
    ];
  }

  protected memberRoleLabel(
    member: Member,
    team: Member[] = [],
    applyCompression: boolean = false
  ): string {
    const baseRole = member.role ?? 'Member';
    if (!applyCompression || !this.isCompressionActive(team)) return baseRole;
    if (this.memberHasTokens(member, VETERAN_NAME_TOKENS)) return 'Advisor';
    return baseRole;
  }

  protected currentRoleLabel(member: ProjectTeamMember): string {
    return member.assignment?.role ?? this.memberRoleLabel(member);
  }

  protected allocationLabel(rate?: number | null): string | null {
    if (rate == null) return null;
    return `${Math.round(rate * 100)}%`;
  }

  protected memberCostValue(
    member: Member,
    team: Member[] = [],
    applyCompression: boolean = false
  ): number {
    if (!applyCompression || !this.isCompressionActive(team)) return member.cost;
    if (this.memberHasTokens(member, VETERAN_NAME_TOKENS)) {
      return Math.min(member.cost, COMPRESSED_COST);
    }
    return member.cost;
  }

  protected memberCostAdjusted(member: Member, team: Member[] = []): boolean {
    return this.memberCostValue(member, team, true) !== member.cost;
  }

  private teamCost(members: Member[], applyCompression: boolean): number {
    if (!applyCompression) {
      return members.reduce((sum, member) => sum + member.cost, 0);
    }
    const compressionActive = this.isCompressionActive(members);
    return members.reduce((sum, member) => {
      if (compressionActive && this.memberHasTokens(member, VETERAN_NAME_TOKENS)) {
        return sum + Math.min(member.cost, COMPRESSED_COST);
      }
      return sum + member.cost;
    }, 0);
  }

  private isCompressionActive(members: Member[]): boolean {
    return (
      this.hasMemberTokens(members, LEADER_NAME_TOKENS)
      && this.hasMemberTokens(members, VETERAN_NAME_TOKENS)
    );
  }

  private hasMemberTokens(members: Member[], tokens: string[]): boolean {
    return members.some((member) => this.memberHasTokens(member, tokens));
  }

  private memberHasTokens(member: Member, tokens: string[]): boolean {
    const text = `${member.name ?? ''} ${member.role ?? ''}`.toLowerCase();
    return tokens.some((token) => text.includes(token.toLowerCase()));
  }

  private matchLabel(score: number): string {
    if (score >= 80) return 'Perfect';
    if (score >= 65) return 'Good';
    if (score >= 50) return 'Fair';
    return 'Low';
  }

  private valueLabel(score: number): string {
    const delta = Math.round((score - 50) * 2);
    return delta >= 0 ? `+${delta}%` : `${delta}%`;
  }

  private riskLabel(score: number): string {
    if (score >= 75) return 'High';
    if (score >= 50) return 'Mid';
    return 'Low';
  }

  private scoreTone(score: number): BadgeTone {
    if (score >= 70) return 'good';
    if (score >= 50) return 'warn';
    return 'risk';
  }

  private riskTone(score: number): BadgeTone {
    if (score >= 75) return 'risk';
    if (score >= 50) return 'warn';
    return 'good';
  }

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

  protected applySuggestion(suggestion: TeamSuggestion): void {
    void this.store.applyTeamSuggestion(suggestion);
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
      const project = p.get('project');
      const mode = p.get('mode');
      const key = `${demo ?? ''}|${mode ?? ''}|${project ?? ''}|${focus ?? ''}`;
      if (key === this.lastKey) return;
      this.lastKey = key;

      if (project && this.store.projects().some((entry) => entry.id === project)) {
        this.store.setProject(project);
      }
      if (mode === 'alert' || mode === 'manual') {
        void this.runAlertContext(mode, focus);
        return;
      }
      if (demo === 'alert' || demo === 'manual') {
        void this.runDemo(demo, focus);
        return;
      }
      if (focus) this.store.focusMember(focus);
    });
  }

  private async runAlertContext(mode: 'alert' | 'manual', focus: string | null): Promise<void> {
    const projectId = this.store.selectedProjectId();
    if (projectId) {
      await this.store.loadProjectTeam(projectId);
    }

    const currentTeamIds = this.store.currentTeam().map((m) => m.id);
    const selected = currentTeamIds.length ? [...currentTeamIds] : [];
    if (focus && this.store.members().some((m) => m.id === focus)) {
      if (!selected.includes(focus)) selected.push(focus);
    }
    if (!selected.length) {
      selected.push(...this.store.members().slice(0, 2).map((m) => m.id));
    }
    if (selected.length) {
      this.store.setSelectedMembers(selected);
    }

    await this.store.runSimulation();
    this.openOverlay(mode);
  }

  private async runDemo(mode: 'alert' | 'manual', focus: string | null): Promise<void> {
    const projectId = this.store.projects().some((x) => x.id === 'ec')
      ? 'ec'
      : this.store.projects()[0]?.id;
    if (projectId) this.store.setProject(projectId);

    if (mode === 'alert') {
      this.selectDemoMembers(['tanaka', '田中'], ['kobayashi', '小林'], focus);
    } else {
      this.selectDemoMembers(['yamada', '山田'], ['suzuki', '鈴木'], focus);
    }

    await this.store.runSimulation();
    this.openOverlay(mode);
  }

  private selectDemoMembers(primary: string[], secondary: string[], focus: string | null): void {
    const selected: string[] = [];
    const primaryId = this.findMemberIdByTokens(primary);
    if (primaryId) selected.push(primaryId);
    const secondaryId = this.findMemberIdByTokens(secondary);
    if (secondaryId) selected.push(secondaryId);
    if (focus && this.store.members().some((m) => m.id === focus)) {
      if (!selected.includes(focus)) selected.push(focus);
    }
    if (selected.length < 2) {
      selected.push(...this.store.members().slice(0, 2).map((m) => m.id));
    }
    this.store.setSelectedMembers(selected);
  }

  private findMemberIdByTokens(tokens: string[]): string | null {
    const lowered = tokens.map((token) => token.toLowerCase());
    const found = this.store.members().find((member) => {
      const name = (member.name ?? '').toLowerCase();
      return lowered.some((token) => name.includes(token));
    });
    return found?.id ?? null;
  }

  protected openOverlay(mode: 'alert' | 'manual'): void {
    const r = this.validSimulationResult();
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
    this.overlayMode.set(mode);
    this.overlayOpen.set(true);
    this.overlayLog.set([]);
    this.selectedPlanId.set(this.activePlanType());
    const recommendedLabel = this.recommendedPlan()?.planType ?? '-';

    const initialEmotion = this.emotionForOverlay(mode, r);
    this.overlayChat.set([
      {
        from: 'ai',
        emotion: initialEmotion,
        text: r
          ? `状況を整理しました。推奨プランは「${recommendedLabel}」です。プラン選択後、必要なら指示を追加し、最後に承認してください。`
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
              text: `結論: Plan ${recommendedLabel}（${r.agents.gunshi.note}）`,
            },
          ];
      this.playLog(script);
    }
  }

  protected closeOverlay(): void {
    this.overlayOpen.set(false);
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
  }

  protected setActivePlan(id: 'A' | 'B' | 'C'): void {
    this.selectedPlanId.set(id);
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
    const simulation = this.validSimulationResult();
    if (simulation) {
      this.approvedSimulationId.set(simulation.id);
    }
    this.overlayChat.update((curr) => [
      ...curr,
      { from: 'ai', emotion: 'relief', text: '承認されました。実行します。' },
    ]);
    const t = window.setTimeout(() => this.closeOverlay(), 900);
    this.timers.push(t);
  }

  protected async sendChat(text: string): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed) {
      this.approvePlan();
      return;
    }

    if (this.chatSending()) {
      this.overlayChat.update((curr) => [
        ...curr,
        { from: 'ai', emotion: 'effort', text: '送信中です。少し待ってください。' },
      ]);
      return;
    }

    this.overlayChat.update((curr) => [...curr, { from: 'user', text: trimmed }]);

    const simulation = this.validSimulationResult();
    const planType = this.activePlanType();
    if (simulation && planType) {
      this.chatSending.set(true);
      try {
        const response = await firstValueFrom(
          this.api.chatSimulationPlan(simulation.id, planType, { message: trimmed })
        );

        this.store.simulationResult.update((curr) => {
          if (!curr) return curr;
          const plans = curr.plans.map((p) =>
            p.planType === response.plan.planType ? response.plan : p
          );
          return { ...curr, plans };
        });

        this.overlayChat.update((curr) => [
          ...curr,
          {
            from: 'ai',
            emotion: this.emotionFromChatRequest(trimmed),
            text: response.message,
          },
        ]);
      } catch (e) {
        const detail =
          e instanceof HttpErrorResponse
            ? typeof e.error === 'object' && e.error && 'detail' in e.error
              ? String((e.error as { detail?: unknown }).detail ?? e.message)
              : e.message
            : e instanceof Error
              ? e.message
              : 'unknown error';

        this.overlayChat.update((curr) => [
          ...curr,
          { from: 'ai', emotion: 'haste', text: `送信に失敗しました: ${detail}` },
        ]);
      } finally {
        this.chatSending.set(false);
      }
      return;
    }
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
