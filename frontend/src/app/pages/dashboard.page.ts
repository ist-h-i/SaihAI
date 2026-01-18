import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { EmptyStateComponent } from '../components/empty-state.component';
import { HaisaSpeechComponent } from '../components/haisa-speech.component';
import { NeuralOrbComponent } from '../components/neural-orb.component';
import { DashboardStore } from '../core/dashboard-store';
import { SimulatorStore } from '../core/simulator-store';
import {
  ApprovalRequestResponse,
  DashboardAlert,
  DashboardPendingAction,
  DashboardProposal,
  Member,
} from '../core/types';

const BURNOUT_WORDS = ['疲労', '飽き', '燃え尽き', '限界'] as const;
const RISK_WORDS = ['対人トラブル', '噂', '炎上', '不満'] as const;
const GROWTH_WORDS = ['挑戦', '伸びしろ', '育成', '学び'] as const;

function clampPct(v: number): number {
  return Math.max(0, Math.min(100, Math.round(v)));
}

function countHit(text: string, words: readonly string[]): number {
  return words.reduce((sum, w) => sum + (text.includes(w) ? 1 : 0), 0);
}

function scoreMember(m: Member): { motivation: number; performance: number; risk: number } {
  const notes = m.notes ?? '';
  const burnout = countHit(notes, BURNOUT_WORDS);
  const growth = countHit(notes, GROWTH_WORDS);
  const riskHits = countHit(notes, RISK_WORDS);

  const motivation = clampPct(55 + growth * 18 - burnout * 22);
  const performance = clampPct(35 + m.skills.length * 9 + m.availability * 0.35);
  const risk = clampPct(20 + riskHits * 25 + burnout * 30 + (m.availability < 50 ? 15 : 0));
  return { motivation, performance, risk };
}

interface MatrixPoint {
  id: string;
  name: string;
  initial: string;
  x: number;
  yTop: number;
  border: string;
  bg: string;
  risk: boolean;
}

interface ExpandedMember {
  member: MatrixPoint;
  fan: { left: number; top: number };
}

interface MatrixVisual {
  id: string;
  x: number;
  yTop: number;
  count: number;
  members: MatrixPoint[];
  expandedMembers: ExpandedMember[];
  border: string;
  bg: string;
  risk: boolean;
  tooltip: string;
}

interface ClusterAccumulator {
  sumX: number;
  sumY: number;
  members: MatrixPoint[];
  risk: boolean;
}

interface ProposalGroup {
  projectId: string;
  projectName: string;
  proposals: DashboardProposal[];
  primary: DashboardProposal | null;
  secondary: DashboardProposal[];
}

@Component({
  imports: [NeuralOrbComponent, HaisaSpeechComponent, EmptyStateComponent],
  template: `
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0">
        <div class="ui-kicker">Shadow Dashboard</div>
        <h2 class="mt-1 text-2xl font-extrabold tracking-tight">経営ダッシュボード</h2>
        <p class="mt-2 text-sm text-slate-300 max-w-2xl">
          影のAIが予兆と提案を整理し、判断だけに集中できます。
        </p>
      </div>

      <div class="w-full lg:w-[360px] shrink-0">
        <div class="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950/40">
          <app-neural-orb class="absolute inset-0 opacity-90"></app-neural-orb>
          <div class="relative p-4">
            <div class="ui-kicker">Next Action</div>
            @if (activeAlert(); as alert) {
              <div class="mt-2 text-sm font-semibold text-rose-200">緊急アラート</div>
              <div class="mt-1 text-xs text-slate-300">{{ alert.title }}</div>
              <div class="mt-2 flex items-center gap-2 text-xs text-slate-400">
                <span class="ui-pill border-rose-500/40 bg-rose-500/15 text-rose-200">RISK</span>
                <span class="text-rose-100 font-semibold">{{ alert.risk }}%</span>
              </div>
              <div class="mt-3">
                <button type="button" class="ui-button-primary" (click)="openAlert(alert)">
                  介入へ
                </button>
              </div>
            } @else if (primaryProposal(); as proposal) {
              <div class="mt-2 text-sm font-semibold text-slate-100">推奨提案を確認</div>
              <div class="mt-1 text-xs text-slate-300">Plan {{ proposal.planType }}</div>
              <div class="text-xs text-slate-400">
                プロジェクト: {{ proposalProjectName(proposal) }}
              </div>
              <div class="mt-3">
                <button type="button" class="ui-button-primary" (click)="goSimulator()">
                  介入へ
                </button>
              </div>
            } @else if (dashboard.pendingActions().length) {
              <div class="mt-2 text-sm font-semibold text-slate-100">承認待ちを確認</div>
              <div class="mt-1 text-xs text-slate-300">{{ dashboard.pendingActions().length }} 件の承認待ち</div>
              <div class="mt-3">
                <button type="button" class="ui-button-primary" (click)="goSimulator()">
                  承認フローへ
                </button>
              </div>
            } @else {
              <div class="mt-2 text-sm font-semibold text-slate-100">最新状況を確認</div>
              <div class="mt-1 text-xs text-slate-300">新しい動きがないか更新します。</div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button type="button" class="ui-button-primary" (click)="goSimulator()">
                  シミュレーターへ
                </button>
                <button type="button" class="ui-button-ghost" (click)="reload()">
                  再読み込み
                </button>
              </div>
            }
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 flex items-center justify-between gap-3">
      <div class="ui-kicker">KPIモニタリング</div>
      <div class="text-xs text-slate-400">
        更新: {{ lastUpdatedLabel() }} / {{ refreshIntervalSec }}s
      </div>
    </div>

    <div class="mt-3 grid gap-4 grid-cols-1 md:grid-cols-4">
      @for (k of kpis(); track k.label) {
        <div class="ui-panel-muted">
          <div class="ui-kicker">{{ k.label }}</div>
          <div class="mt-2 flex items-end gap-2">
            <div class="text-3xl font-extrabold tracking-tight" [style.color]="k.color">
              {{ k.value }}
            </div>
            <div class="text-sm text-slate-400 pb-1">{{ k.suffix }}</div>
          </div>
          <div class="mt-2 text-xs" [style.color]="k.deltaColor">{{ k.delta }}</div>
        </div>
      }
    </div>

    <div class="mt-6">
      <div class="ui-kicker">緊急アラートフィード</div>
      @if (alertFeed().length) {
        <div class="mt-2 space-y-3">
          @for (alert of alertFeed(); track alert.id) {
            <div class="ui-panel flex flex-col gap-3 sm:flex-row sm:items-center">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                  <span
                    class="ui-pill"
                    [class.border-rose-500/40]="alert.category !== 'career_mismatch'"
                    [class.bg-rose-500/10]="alert.category !== 'career_mismatch'"
                    [class.text-rose-200]="alert.category !== 'career_mismatch'"
                    [class.border-indigo-500/40]="alert.category === 'career_mismatch'"
                    [class.bg-indigo-500/10]="alert.category === 'career_mismatch'"
                    [class.text-indigo-200]="alert.category === 'career_mismatch'"
                  >
                    {{ alertCategoryLabel(alert) }}
                  </span>
                  @if (alertFocusName(alert); as focusName) {
                    <span class="text-slate-400">対象: {{ focusName }}</span>
                  }
                </div>
                <div class="mt-2 text-sm font-semibold text-slate-100">{{ alert.title }}</div>
                <div class="text-xs text-slate-400 truncate">{{ alert.subtitle }}</div>
              </div>
              <div class="flex items-center gap-4 sm:ml-auto">
                <div class="text-right">
                  <div class="text-[10px] text-slate-400 font-semibold">RISK</div>
                  <div class="text-lg font-extrabold text-rose-200">{{ alert.risk }}%</div>
                </div>
                <button type="button" class="ui-button-secondary" (click)="openAlert(alert)">
                  詳細を開く
                </button>
              </div>
            </div>
          }
        </div>
      } @else {
        <app-empty-state
          kicker="Empty"
          title="緊急アラートはありません"
          description="新しいアラートが検知されるとここに表示します。"
        />
      }
    </div>

    <div class="mt-6">
      <div class="ui-kicker">Today Focus</div>
      @if (activeAlert(); as alert) {
        <div class="mt-2 w-full text-left ui-panel border-rose-500/30 bg-rose-500/10">
          <div class="flex flex-col sm:flex-row sm:items-center gap-4">
            <div
              class="h-12 w-12 rounded-xl bg-rose-500/15 border border-rose-500/30 grid place-items-center text-rose-200 font-black"
            >
              !
            </div>
            <div class="min-w-0">
              <div class="text-base font-bold truncate">{{ alert.title }}</div>
              <div class="text-sm text-slate-300 truncate">{{ alert.subtitle }}</div>
            </div>
            <div class="sm:ml-auto text-left sm:text-right">
              <div class="text-xs text-slate-400 font-semibold">RISK</div>
              <div class="text-lg font-extrabold text-rose-200">{{ alert.risk }}%</div>
            </div>
          </div>
        </div>
      } @else if (primaryProposal(); as proposal) {
        <div class="mt-2 ui-panel">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="ui-kicker">AI Recommendation</div>
              <div class="text-base font-semibold text-slate-100">Plan {{ proposal.planType }}</div>
              <div class="mt-1 text-xs text-slate-400">
                プロジェクト: {{ proposalProjectName(proposal) }}
              </div>
              <div class="mt-2 text-sm text-slate-300 whitespace-pre-line">
                {{ proposalSummary(proposal) }}
              </div>
            </div>
          </div>
          @if (proposalDetail(proposal); as detail) {
            <details class="mt-3 rounded-lg border border-slate-800 bg-slate-900/30 p-3">
              <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                詳細
              </summary>
              <div class="mt-2 text-xs text-slate-300 whitespace-pre-line">{{ detail }}</div>
            </details>
          }
        </div>
      } @else {
        <app-empty-state
          kicker="Empty"
          title="意思決定ポイントはありません"
          description="新しいアラートや提案が届いたら表示します。"
        />
      }
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-2">
      <div class="ui-panel">
        <div class="flex items-center justify-between gap-3">
          <div class="ui-section-title">AI 提案</div>
        </div>
        @if (proposalGroups().length) {
          <div class="mt-3 space-y-4">
            @for (group of proposalGroups(); track group.projectId) {
              <div
                class="rounded-lg border border-slate-800/70 bg-slate-950/30 p-3"
                [attr.data-project-id]="group.projectId"
              >
                <div class="text-[11px] text-slate-400 font-semibold">プロジェクト</div>
                <div class="text-sm font-semibold text-slate-100">{{ group.projectName }}</div>
                <div class="mt-3 space-y-3">
                  @if (group.primary; as p) {
                    <app-haisa-speech
                      [tone]="p.isRecommended ? 'success' : 'info'"
                      [title]="'Plan ' + p.planType"
                [tag]="p.isRecommended ? '推奨' : undefined"
                      [meta]="proposalMeta(p)"
                      [message]="proposalSummary(p)"
                      [compact]="true"
                      [showAvatar]="true"
                      [reserveAvatarSpace]="true"
                      [highlight]="p.isRecommended"
                    />
                    @if (proposalDetail(p); as detail) {
                      <details class="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                        <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                          詳細
                        </summary>
                        <div class="mt-2 text-xs text-slate-300 whitespace-pre-line">
                          {{ detail }}
                        </div>
                      </details>
                    }
                  }

                  @if (group.secondary.length) {
                    <details class="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                      <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                        他の提案（{{ group.secondary.length }}）
                      </summary>
                      <div class="mt-3 space-y-3">
                        @for (p of group.secondary; track p.id) {
                          <app-haisa-speech
                            [tone]="p.isRecommended ? 'success' : 'info'"
                            [title]="'Plan ' + p.planType"
                      [tag]="p.isRecommended ? '推奨' : undefined"
                            [meta]="proposalMeta(p)"
                            [message]="proposalSummary(p)"
                            [compact]="true"
                            [showAvatar]="false"
                            [reserveAvatarSpace]="true"
                          />
                          @if (proposalDetail(p); as detail) {
                            <details class="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                              <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                                詳細
                              </summary>
                              <div class="mt-2 text-xs text-slate-300 whitespace-pre-line">
                                {{ detail }}
                              </div>
                            </details>
                          }
                        }
                      </div>
                    </details>
                  }
                </div>
              </div>
            }
          </div>
        } @else {
          <app-empty-state
            kicker="Empty"
            title="提案を準備中"
            description="新しい提案が届いたら表示します。"
          />
        }
      </div>

      <div class="ui-panel">
        <div class="flex items-center justify-between gap-3">
          <div class="ui-section-title">承認待ち</div>
          <span
            class="ui-pill"
            [class.border-emerald-500/40]="dashboard.pendingActions().length === 0"
            [class.bg-emerald-500/10]="dashboard.pendingActions().length === 0"
            [class.text-emerald-200]="dashboard.pendingActions().length === 0"
            [class.border-amber-500/40]="dashboard.pendingActions().length > 0"
            [class.bg-amber-500/10]="dashboard.pendingActions().length > 0"
            [class.text-amber-200]="dashboard.pendingActions().length > 0"
          >
            {{ pendingLabel() }}
          </span>
        </div>
        @if (dashboard.pendingActions().length) {
          <div class="mt-3">
            <div class="text-sm text-slate-300">要対応 {{ dashboard.pendingActions().length }} 件</div>
            <details class="mt-3 rounded-lg border border-slate-800 bg-slate-900/30 p-3">
              <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                詳細を開く
              </summary>
              <div class="mt-3 space-y-2">
                @for (action of dashboard.pendingActions(); track action.id) {
                  <div class="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                    <div class="flex items-center justify-between gap-3">
                      <div class="text-sm font-semibold">{{ action.title }}</div>
                      <div class="text-[11px] text-slate-400">{{ action.actionType }}</div>
                    </div>
                    <div class="mt-2 flex items-center justify-between gap-3">
                      <div class="text-xs text-slate-400">status: {{ action.status }}</div>
                      <button
                        type="button"
                        class="ui-button-secondary"
                        (click)="openNemawashi(action)"
                      >
                        下書き/承認
                      </button>
                    </div>
                  </div>
                }
              </div>
            </details>
          </div>
        } @else {
          <app-empty-state
            kicker="Empty"
            title="承認待ちはありません"
            description="新しい承認が発生したら通知します。"
          />
        }
      </div>
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="lg:col-span-2 ui-panel">
        <div class="flex items-center justify-between gap-4">
          <div>
            <div class="ui-kicker">Talent Matrix</div>
            <div class="text-sm text-slate-200 font-semibold mt-1">組織人材マップ</div>
          </div>
          <div class="text-xs text-slate-400">MOTIVATION → / PERFORMANCE ↑</div>
        </div>

        <div
          class="mt-3 relative h-[340px] rounded-xl overflow-hidden border border-slate-800 bg-slate-950/30"
        >
          <div class="absolute inset-0 grid grid-cols-2 grid-rows-2">
            <div class="border-b border-r border-slate-800/80 p-3">
              <div class="text-xs font-bold text-rose-200">Risk</div>
              <div class="text-[11px] text-slate-400">離職予備軍</div>
            </div>
            <div class="border-b border-slate-800/80 p-3">
              <div class="text-xs font-bold text-indigo-200">Star</div>
              <div class="text-[11px] text-slate-400">エース</div>
            </div>
            <div class="border-r border-slate-800/80 p-3">
              <div class="text-xs font-bold text-violet-200">Stagnant</div>
              <div class="text-[11px] text-slate-400">停滞</div>
            </div>
            <div class="p-3">
              <div class="text-xs font-bold text-emerald-200">Growth</div>
              <div class="text-[11px] text-slate-400">成長株</div>
            </div>
          </div>

          <div
            class="absolute inset-0 opacity-60"
            style="background: radial-gradient(circle at center, rgba(99,102,241,0.20), transparent 55%)"
          ></div>

          @for (visual of matrixVisuals(); track visual.id) {
            <button
              type="button"
              class="absolute z-30 h-10 w-10 rounded-xl border border-white/20 bg-slate-900/70 hover:bg-slate-800/70 matrix-cluster-base backdrop-blur grid place-items-center text-sm font-extrabold"
              [style.left.%]="visual.x"
              [style.top.%]="visual.yTop"
              [style.borderColor]="visual.border"
              [style.background]="visual.bg"
              [title]="visual.tooltip"
              (click)="
                visual.count === 1
                  ? goSimulator('manual', visual.members[0].id)
                  : toggleCluster(visual.id)
              "
            >
              @if (visual.count === 1) {
                <span>{{ visual.members[0].initial }}</span>
              }
              @if (visual.count > 1) {
                <span class="text-[11px] leading-tight">+{{ visual.count }}</span>
              }
            </button>
            @if (openedClusterId() === visual.id && visual.count > 1) {
              @for (exp of visual.expandedMembers; track exp.member.id) {
                <button
                  type="button"
                  class="absolute z-40 h-8 w-8 rounded-xl border border-white/30 bg-slate-900/80 hover:bg-slate-800/80 backdrop-blur text-[10px] font-extrabold"
                  [style.left.%]="exp.fan.left"
                  [style.top.%]="exp.fan.top"
                  [style.borderColor]="visual.border"
                  [style.background]="visual.bg"
                  (click)="goSimulator('manual', exp.member.id)"
                  [title]="exp.member.name"
                >
                  {{ exp.member.initial }}
                </button>
              }
            }
          }
        </div>
      </div>

      <div class="ui-panel">
        <div class="ui-kicker">AI Watchdog</div>
        @if (watchdog().length) {
          <div class="mt-3">
            <div class="text-xs text-slate-400">最新</div>
            <div class="mt-1 text-sm text-slate-200">{{ watchdog()[0].text }}</div>
          </div>
          <details class="mt-3 rounded-lg border border-slate-800 bg-slate-900/30 p-3">
            <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
              ログを開く
            </summary>
            <div class="mt-3 space-y-3 text-sm">
              @for (row of watchdog(); track row.t) {
                <div class="flex items-start gap-3">
                  <span class="mt-1 h-2 w-2 rounded-full" [style.background]="row.dot"></span>
                  <div class="min-w-0">
                    <div class="text-xs text-slate-500 font-semibold">{{ row.t }}</div>
                    <div class="text-sm text-slate-200">{{ row.text }}</div>
                  </div>
                </div>
              }
            </div>
          </details>
        } @else {
          <div class="mt-3 text-xs text-slate-500">ログはまだありません。</div>
        }

        @if (store.simulationResult(); as r) {
          <div class="mt-4 rounded-lg border border-slate-800 bg-white/5 p-3">
            <div class="text-xs text-slate-400 font-semibold">直近シミュレーション</div>
            <div class="mt-1 text-sm text-slate-200 font-semibold">{{ r.project.name }}</div>
            <div class="mt-1 text-xs text-slate-300">
              pattern: {{ r.pattern }} / risk {{ r.metrics.riskPct }}%
            </div>
          </div>
        }
      </div>
    </div>

    <div class="mt-6 ui-panel">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="ui-section-title">History</div>
        <select
          class="rounded-md border border-slate-800 bg-slate-900/50 px-2 py-1 text-xs text-slate-200"
          (change)="updateHistoryFilter($event)"
          [value]="historyStatusFilter() ?? ''"
        >
          <option value="">All</option>
          <option value="approval_pending">Approval Pending</option>
          <option value="approved">Approved</option>
          <option value="executing">Executing</option>
          <option value="executed">Executed</option>
          <option value="failed">Failed</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      @if (historyEntries().length) {
        <div class="mt-3 space-y-3">
          @for (entry of historyEntries(); track entry.thread_id) {
            <details class="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
              <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                <span class="text-slate-100">Action #{{ entry.action_id }}</span>
                <span class="text-slate-400">
                  / {{ entry.status || 'unknown' }} / {{ formatHistoryTime(entry.updated_at) }}
                </span>
              </summary>
              <div class="mt-2 text-xs text-slate-300 whitespace-pre-wrap">
                {{ entry.summary || 'No summary available.' }}
              </div>
              @if (entry.events.length) {
                <div class="mt-3 space-y-2 text-[11px] text-slate-400">
                  @for (evt of entry.events; track evt.created_at) {
                    <div>
                      <span class="text-slate-500">{{ formatHistoryTime(evt.created_at) }}</span>
                      <span class="text-slate-300"> {{ evt.event_type }}</span>
                      @if (evt.actor) { <span class="text-slate-500"> by {{ evt.actor }}</span> }
                    </div>
                  }
                </div>
              }
            </details>
          }
        </div>
      } @else {
        <app-empty-state
          kicker="Empty"
          title="履歴はまだありません"
          description="承認や実行が発生するとここに履歴が表示されます。"
        />
      }
    </div>

    @if (nemawashiOpen() && nemawashiAction(); as action) {
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-950/70" (click)="closeNemawashi()"></div>
        <div class="relative w-full max-w-2xl rounded-xl border border-slate-800 bg-slate-950 p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="ui-kicker">Nemawashi</div>
              <div class="mt-1 text-sm font-semibold text-slate-100">Action #{{ action.id }}</div>
              <div class="mt-1 text-xs text-slate-400">
                type: {{ action.actionType }} / status: {{ action.status }}
              </div>
            </div>
            <button type="button" class="ui-button-ghost" (click)="closeNemawashi()">Close</button>
          </div>

          @if (nemawashiError(); as err) {
            <div class="mt-3 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-100">
              {{ err }}
            </div>
          }

          <div class="mt-3 rounded-lg border border-slate-800 bg-slate-900/40 p-3">
            <div class="text-xs text-slate-400 font-semibold">Draft</div>
            <pre class="mt-2 text-xs text-slate-200 whitespace-pre-wrap">{{ action.title }}</pre>
          </div>

          @if (nemawashiApproval(); as approval) {
            <div class="mt-3 text-xs text-slate-400">
              approval: {{ approval.approval_request_id }} / {{ approval.status }}
            </div>
          }

          <div class="mt-4 flex flex-wrap justify-end gap-2">
            @if (!nemawashiApproval() && action.status !== 'approval_pending') {
              <button
                type="button"
                class="ui-button-primary"
                [disabled]="nemawashiWorking()"
                (click)="requestNemawashiApproval()"
              >
                承認依頼
              </button>
            } @else if (nemawashiApproval(); as approval) {
              <button
                type="button"
                class="ui-button-primary"
                [disabled]="nemawashiWorking()"
                (click)="approveNemawashi(approval.approval_request_id)"
              >
                承認
              </button>
              <button
                type="button"
                class="ui-button-secondary"
                [disabled]="nemawashiWorking()"
                (click)="rejectNemawashi(approval.approval_request_id)"
              >
                却下
              </button>
            } @else {
              <button
                type="button"
                class="ui-button-secondary"
                [disabled]="nemawashiWorking()"
                (click)="refreshNemawashiApproval()"
              >
                承認情報を取得
              </button>
            }
          </div>
        </div>
      </div>
    }
  `,
})
export class DashboardPage implements OnDestroy {
  protected readonly store = inject(SimulatorStore);
  protected readonly dashboard = inject(DashboardStore);
  private readonly router = inject(Router);

  protected readonly kpis = computed(() => this.dashboard.kpis());
  protected readonly alertFeed = computed(() => {
    return [...this.dashboard.alerts()].sort((a, b) => b.risk - a.risk);
  });
  protected readonly refreshIntervalSec = 30;
  protected readonly lastUpdatedLabel = computed(() => {
    const updatedAt = this.dashboard.lastUpdatedAt();
    if (!updatedAt) return '--:--';
    return updatedAt.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  });

  protected readonly activeAlert = computed(() => {
    return this.alertFeed()[0] ?? null;
  });

  private readonly dedupedProposals = computed(() => {
    return this.dedupeProposals(this.dashboard.proposals());
  });

  protected readonly primaryProposal = computed(() => {
    const proposals = this.dedupedProposals();
    if (!proposals.length) return null;
    return proposals.find((p) => p.isRecommended) ?? proposals[0] ?? null;
  });

  protected readonly proposalGroups = computed<ProposalGroup[]>(() => {
    return this.groupProposals(this.dedupedProposals());
  });

  protected readonly pendingLabel = computed(() => {
    const count = this.dashboard.pendingActions().length;
    return count ? `${count}件` : '0件';
  });

  private pollTimer: number | null = null;

  protected readonly nemawashiOpen = signal(false);
  protected readonly nemawashiAction = signal<DashboardPendingAction | null>(null);
  protected readonly nemawashiApproval = signal<ApprovalRequestResponse | null>(null);
  protected readonly nemawashiWorking = signal(false);
  protected readonly nemawashiError = signal<string | null>(null);

  protected readonly matrixPoints = computed(() => {
    return this.dashboard.members().map((m) => {
      const s = scoreMember(m);
      const x = clampPct(10 + s.motivation * 0.8);
      const yTop = clampPct(100 - (10 + s.performance * 0.8));
      const risky = s.risk >= 70;
      return {
        id: m.id,
        name: m.name,
        initial: (m.name || '?').trim().slice(0, 1),
        x,
        yTop,
        border: risky ? 'rgba(244,63,94,0.9)' : 'rgba(148,163,184,0.35)',
        bg: risky ? 'rgba(16,185,129,0.35)' : 'rgba(99,102,241,0.18)',
        risk: risky,
      };
    });
  });

  protected readonly matrixVisuals = computed<MatrixVisual[]>(() => {
    const cellSize = 6;
    const buckets = new Map<string, ClusterAccumulator>();
    for (const point of this.matrixPoints()) {
      const bucket = this.clusterKey(point.x, point.yTop, cellSize);
      const entry = buckets.get(bucket);
      if (entry) {
        entry.sumX += point.x;
        entry.sumY += point.yTop;
        entry.members.push(point);
        entry.risk = entry.risk || point.risk;
      } else {
        buckets.set(bucket, {
          sumX: point.x,
          sumY: point.yTop,
          members: [point],
          risk: point.risk,
        });
      }
    }

    const visuals: MatrixVisual[] = [];
    for (const [key, entry] of buckets) {
      const count = entry.members.length;
      const avgX = entry.sumX / count;
      const avgY = entry.sumY / count;
      const fanPositions = this.createFanPositions(avgX, avgY, count);
      const tooltip =
        count === 1
          ? entry.members[0].name
          : `${count}名 · ${entry.members.map((m) => m.name).join(' / ')}`;
      visuals.push({
        id: key,
        x: avgX,
        yTop: avgY,
        count,
        members: entry.members,
        expandedMembers: entry.members.map((member, idx) => ({
          member,
          fan: fanPositions[idx],
        })),
        border: entry.risk ? 'rgba(244,63,94,0.9)' : 'rgba(148,163,184,0.35)',
        bg: entry.risk ? 'rgba(16,185,129,0.35)' : 'rgba(99,102,241,0.18)',
        risk: entry.risk,
        tooltip,
      });
    }

    return visuals;
  });

  protected readonly openedClusterId = signal<string | null>(null);

  protected readonly watchdog = computed(() => {
    return this.dashboard.watchdog();
  });

  protected readonly historyEntries = computed(() => {
    return this.dashboard.history();
  });

  protected readonly historyStatusFilter = computed(() => {
    return this.dashboard.historyStatusFilter();
  });

  protected proposalSummary(p: DashboardProposal): string {
    const { summary } = this.splitProposal(p.description);
    if (p.predictedFutureImpact) {
      return `理由: ${summary}\n影響予測: ${p.predictedFutureImpact}`;
    }
    return `理由: ${summary}`;
  }

  protected proposalProjectName(p: DashboardProposal): string {
    const name = (p.projectName ?? '').trim();
    return name || p.projectId;
  }

  protected proposalMeta(p: DashboardProposal): string {
    return `${this.proposalProjectName(p)} / score ${p.recommendationScore}`;
  }

  protected proposalDetail(p: DashboardProposal): string | null {
    const detail = this.splitProposal(p.description).detail;
    if (p.predictedFutureImpact) {
      if (detail) {
        return `${detail}\n影響予測: ${p.predictedFutureImpact}`;
      }
      return `影響予測: ${p.predictedFutureImpact}`;
    }
    return detail;
  }

  private dedupeProposals(proposals: DashboardProposal[]): DashboardProposal[] {
    if (!proposals.length) return [];
    const seenByProject = new Map<string, Set<number>>();
    const unique: DashboardProposal[] = [];
    for (const proposal of proposals) {
      const projectId = proposal.projectId;
      let seen = seenByProject.get(projectId);
      if (!seen) {
        seen = new Set<number>();
        seenByProject.set(projectId, seen);
      }
      if (seen.has(proposal.id)) continue;
      seen.add(proposal.id);
      unique.push(proposal);
    }
    return unique;
  }

  private groupProposals(proposals: DashboardProposal[]): ProposalGroup[] {
    if (!proposals.length) return [];
    const groups = new Map<string, { name: string; proposals: DashboardProposal[] }>();
    for (const proposal of proposals) {
      const projectId = proposal.projectId;
      const projectName = this.proposalProjectName(proposal);
      const entry = groups.get(projectId);
      if (entry) {
        if (entry.name === projectId && projectName !== projectId) {
          entry.name = projectName;
        }
        entry.proposals.push(proposal);
      } else {
        groups.set(projectId, { name: projectName, proposals: [proposal] });
      }
    }

    return Array.from(groups.entries()).map(([projectId, group]) => {
      const primary = group.proposals.find((p) => p.isRecommended) ?? group.proposals[0] ?? null;
      const secondary = primary ? group.proposals.filter((p) => p !== primary) : [];
      return {
        projectId,
        projectName: group.name,
        proposals: group.proposals,
        primary,
        secondary,
      };
    });
  }

  private splitProposal(description: string): { summary: string; detail: string | null } {
    const normalized = description.replace(/\s+/g, ' ').trim();
    if (!normalized) return { summary: '状況を確認中です。', detail: null };
    const parts = normalized.split('。').map((s) => s.trim()).filter(Boolean);
    const summaryParts = parts.slice(0, 2);
    const summary = summaryParts.join(' / ');
    if (parts.length <= 2) return { summary, detail: null };
    const detail = parts.slice(2).join('。') + '。';
    return { summary, detail };
  }

  private clusterKey(x: number, yTop: number, cellSize: number): string {
    const col = Math.round(x / cellSize);
    const row = Math.round(yTop / cellSize);
    return `${col}:${row}`;
  }

  private createFanPositions(
    centerX: number,
    centerY: number,
    count: number
  ): { left: number; top: number }[] {
    if (count <= 1) {
      return [{ left: clampPct(centerX), top: clampPct(centerY) }];
    }
    const radius = Math.min(12, 4 + count * 1.2);
    const offset = Math.PI / 4;
    return Array.from({ length: count }, (_, idx) => {
      const angle = (idx / count) * Math.PI * 2 + offset;
      return {
        left: clampPct(centerX + Math.cos(angle) * radius),
        top: clampPct(centerY + Math.sin(angle) * radius),
      };
    });
  }

  protected toggleCluster(clusterId: string): void {
    this.openedClusterId.set(this.openedClusterId() === clusterId ? null : clusterId);
  }

  protected openNemawashi(action: DashboardPendingAction): void {
    this.nemawashiError.set(null);
    this.nemawashiApproval.set(null);
    this.nemawashiAction.set(action);
    this.nemawashiOpen.set(true);

    if (action.status === 'approval_pending') {
      void this.refreshNemawashiApproval();
    }
  }

  protected closeNemawashi(): void {
    this.nemawashiOpen.set(false);
    this.nemawashiAction.set(null);
    this.nemawashiApproval.set(null);
    this.nemawashiError.set(null);
  }

  protected async requestNemawashiApproval(): Promise<void> {
    const action = this.nemawashiAction();
    if (!action) return;

    this.nemawashiWorking.set(true);
    this.nemawashiError.set(null);
    try {
      const approval = await this.dashboard.requestNemawashiApproval(action.id);
      this.nemawashiApproval.set(approval);

      await this.dashboard.load();
      this.nemawashiAction.set(this.findPendingAction(action.id) ?? action);
    } catch (e) {
      this.nemawashiError.set(this.describeError(e));
    } finally {
      this.nemawashiWorking.set(false);
    }
  }

  protected async refreshNemawashiApproval(): Promise<void> {
    const action = this.nemawashiAction();
    if (!action) return;

    this.nemawashiWorking.set(true);
    this.nemawashiError.set(null);
    try {
      const approval = await this.dashboard.requestNemawashiApproval(action.id);
      this.nemawashiApproval.set(approval);

      await this.dashboard.load();
      this.nemawashiAction.set(this.findPendingAction(action.id) ?? action);
    } catch (e) {
      this.nemawashiError.set(this.describeError(e));
    } finally {
      this.nemawashiWorking.set(false);
    }
  }

  protected async approveNemawashi(approvalId: string): Promise<void> {
    this.nemawashiWorking.set(true);
    this.nemawashiError.set(null);
    try {
      await this.dashboard.approveApproval(approvalId);
      await this.dashboard.load();
      this.closeNemawashi();
    } catch (e) {
      this.nemawashiError.set(this.describeError(e));
    } finally {
      this.nemawashiWorking.set(false);
    }
  }

  protected async rejectNemawashi(approvalId: string): Promise<void> {
    this.nemawashiWorking.set(true);
    this.nemawashiError.set(null);
    try {
      await this.dashboard.rejectApproval(approvalId);
      await this.dashboard.load();
      this.closeNemawashi();
    } catch (e) {
      this.nemawashiError.set(this.describeError(e));
    } finally {
      this.nemawashiWorking.set(false);
    }
  }

  private findPendingAction(actionId: number): DashboardPendingAction | undefined {
    return this.dashboard.pendingActions().find((a) => a.id === actionId);
  }

  private describeError(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const detail =
        typeof error.error === 'string'
          ? error.error
          : typeof error.error?.detail === 'string'
            ? error.error.detail
            : null;
      if (detail) return `${detail}`;
      return error.message || `${error.status} ${error.statusText}`.trim() || 'request failed';
    }
    if (error instanceof Error) return error.message;
    return 'request failed';
  }

  constructor() {
    void this.dashboard.load();
    this.startPolling();
  }

  ngOnDestroy(): void {
    if (this.pollTimer !== null) {
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private startPolling(): void {
    if (this.pollTimer !== null) return;
    this.pollTimer = window.setInterval(() => {
      void this.dashboard.load();
    }, this.refreshIntervalSec * 1000);
  }

  protected reload(): void {
    void this.dashboard.load();
  }

  protected updateHistoryFilter(event: Event): void {
    const value = (event.target as HTMLSelectElement | null)?.value ?? '';
    void this.dashboard.setHistoryFilter(value ? value : null);
  }

  protected formatHistoryTime(value?: string | null): string {
    if (!value) return '--';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString('ja-JP', { hour12: false });
  }

  protected openAlert(alert: DashboardAlert): void {
    const mode = alert.category === 'career_mismatch' ? 'manual' : 'alert';
    this.openedClusterId.set(null);
    void this.router.navigate(['/simulator'], {
      queryParams: {
        ...(alert.projectId ? { project: alert.projectId } : {}),
        ...(alert.focusMemberId ? { focus: alert.focusMemberId } : {}),
        mode,
      },
    });
  }

  protected goSimulator(demo?: 'alert' | 'manual', focusMemberId?: string): void {
    this.openedClusterId.set(null);
    void this.router.navigate(['/simulator'], {
      queryParams: {
        ...(demo ? { demo } : {}),
        ...(focusMemberId ? { focus: focusMemberId } : {}),
      },
    });
  }

  protected alertCategoryLabel(alert: DashboardAlert): string {
    if (alert.category === 'career_mismatch') return 'Career';
    if (alert.category === 'burnout') return 'Burnout';
    return 'Alert';
  }

  protected alertFocusName(alert: DashboardAlert): string | null {
    const focusId = alert.focusMemberId;
    if (!focusId) return null;
    return this.dashboard.members().find((m) => m.id === focusId)?.name ?? null;
  }
}
