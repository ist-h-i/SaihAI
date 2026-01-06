import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { EmptyStateComponent } from '../components/empty-state.component';
import { HaisaSpeechComponent } from '../components/haisa-speech.component';
import { NeuralOrbComponent } from '../components/neural-orb.component';
import { DashboardStore } from '../core/dashboard-store';
import { SimulatorStore } from '../core/simulator-store';
import { DashboardProposal, Member } from '../core/types';

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

@Component({
  imports: [NeuralOrbComponent, HaisaSpeechComponent, EmptyStateComponent],
  template: `
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0">
        <div class="ui-kicker">Shadow Dashboard</div>
        <h2 class="mt-1 text-2xl font-extrabold tracking-tight">経営ダッシュボード</h2>
        <p class="mt-2 text-sm text-slate-300 max-w-2xl">
          影で回るAIが「予兆検知 → 根回し準備」まで済ませます。あなたは最後の直感で介入し、
          1クリックで決裁します。
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
              <div class="mt-3 flex gap-2">
                <button type="button" class="ui-button-primary" (click)="goSimulator('alert')">
                  介入へ
                </button>
                <button type="button" class="ui-button-secondary" (click)="goSimulator()">
                  シミュレーター
                </button>
              </div>
            } @else if (primaryProposal(); as proposal) {
              <div class="mt-2 text-sm font-semibold text-slate-100">推奨提案を確認</div>
              <div class="mt-1 text-xs text-slate-300">Plan {{ proposal.planType }} を起点に介入</div>
              <div class="mt-3 flex gap-2">
                <button type="button" class="ui-button-primary" (click)="goSimulator()">
                  介入へ
                </button>
                <button type="button" class="ui-button-secondary" (click)="goSimulator('manual')">
                  デモ
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
              <div class="mt-2 text-sm font-semibold text-slate-100">状況を確認</div>
              <div class="mt-1 text-xs text-slate-300">最新状況を更新して判断材料を補強します。</div>
              <div class="mt-3 flex gap-2">
                <button type="button" class="ui-button-primary" (click)="reload()">
                  再読み込み
                </button>
                <button type="button" class="ui-button-secondary" (click)="goSimulator()">
                  シミュレーターへ
                </button>
              </div>
            }
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-4 grid-cols-1 md:grid-cols-4">
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
      <div class="ui-kicker">Today Focus</div>
      @if (activeAlert(); as alert) {
        <button
          type="button"
          class="mt-2 w-full text-left ui-panel-interactive border-rose-500/30 bg-rose-500/10"
          (click)="goSimulator('alert')"
        >
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
        </button>
      } @else if (primaryProposal(); as proposal) {
        <div class="mt-2 ui-panel">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="ui-kicker">AI Recommendation</div>
              <div class="text-base font-semibold text-slate-100">Plan {{ proposal.planType }}</div>
              <div class="mt-2 text-sm text-slate-300 whitespace-pre-line">
                {{ proposalSummary(proposal) }}
              </div>
            </div>
            <button type="button" class="ui-button-primary" (click)="goSimulator()">
              介入へ
            </button>
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
          description="新しいアラートや提案が届いたらここに集約されます。"
          primaryLabel="再読み込み"
          secondaryLabel="シミュレーターへ"
          (primary)="reload()"
          (secondary)="goSimulator()"
        />
      }
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-2">
      <div class="ui-panel">
        <div class="flex items-center justify-between gap-3">
          <div class="ui-section-title">AI 提案</div>
          <button type="button" class="ui-button-ghost text-xs" (click)="goSimulator()">
            シミュレーターへ
          </button>
        </div>
        @if (dashboard.proposals().length) {
          <div class="mt-3 space-y-3">
            @if (primaryProposal(); as p) {
              <app-haisa-speech
                [tone]="'success'"
                [title]="'Plan ' + p.planType"
                [tag]="'推奨'"
                [meta]="'score ' + p.recommendationScore"
                [message]="proposalSummary(p)"
                [compact]="true"
                [showAvatar]="true"
                [reserveAvatarSpace]="true"
                [highlight]="true"
              />
              @if (proposalDetail(p); as detail) {
                <details class="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                  <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                    詳細
                  </summary>
                  <div class="mt-2 text-xs text-slate-300 whitespace-pre-line">{{ detail }}</div>
                </details>
              }
            }

            @if (secondaryProposals().length) {
              <details class="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                <summary class="cursor-pointer list-none text-xs font-semibold text-slate-300">
                  他の提案（{{ secondaryProposals().length }}）
                </summary>
                <div class="mt-3 space-y-3">
                  @for (p of secondaryProposals(); track p.id) {
                    <app-haisa-speech
                      [tone]="'info'"
                      [title]="'Plan ' + p.planType"
                      [meta]="'score ' + p.recommendationScore"
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
                        <div class="mt-2 text-xs text-slate-300 whitespace-pre-line">{{ detail }}</div>
                      </details>
                    }
                  }
                </div>
              </details>
            }
          </div>
        } @else {
          <app-empty-state
            kicker="Empty"
            title="提案を準備中"
            description="新しい提案が届いたらここに表示します。"
            primaryLabel="再読み込み"
            secondaryLabel="シミュレーターへ"
            (primary)="reload()"
            (secondary)="goSimulator()"
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
                    <div class="mt-1 text-xs text-slate-400">status: {{ action.status }}</div>
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
            primaryLabel="シミュレーターへ"
            (primary)="goSimulator()"
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
  `,
})
export class DashboardPage {
  protected readonly store = inject(SimulatorStore);
  protected readonly dashboard = inject(DashboardStore);
  private readonly router = inject(Router);

  protected readonly kpis = computed(() => this.dashboard.kpis());

  protected readonly activeAlert = computed(() => {
    const alerts = [...this.dashboard.alerts()].sort((a, b) => b.risk - a.risk);
    return alerts[0] ?? null;
  });

  protected readonly primaryProposal = computed(() => {
    const proposals = this.dashboard.proposals();
    if (!proposals.length) return null;
    return proposals.find((p) => p.isRecommended) ?? proposals[0] ?? null;
  });

  protected readonly secondaryProposals = computed(() => {
    const primary = this.primaryProposal();
    return this.dashboard.proposals().filter((p) => p !== primary);
  });

  protected readonly pendingLabel = computed(() => {
    const count = this.dashboard.pendingActions().length;
    return count ? `${count}件` : '0件';
  });

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

  protected proposalSummary(p: DashboardProposal): string {
    const { summary } = this.splitProposal(p.description);
    const nextAction = '次: 介入プランを確認';
    return `理由: ${summary}\n${nextAction}`;
  }

  protected proposalDetail(p: DashboardProposal): string | null {
    return this.splitProposal(p.description).detail;
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

  constructor() {
    void this.dashboard.load();
  }

  protected reload(): void {
    void this.dashboard.load();
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
}
