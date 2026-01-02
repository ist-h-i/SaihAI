import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { NeuralOrbComponent } from '../components/neural-orb.component';
import { SimulatorStore } from '../core/simulator-store';
import { Member } from '../core/types';

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
  imports: [NeuralOrbComponent],
  template: `
    <div class="flex items-start justify-between gap-6">
      <div class="min-w-0">
        <div class="text-[11px] text-slate-400 font-bold uppercase tracking-wider">
          Shadow Dashboard
        </div>
        <h2 class="mt-1 text-2xl font-extrabold tracking-tight">経営ダッシュボード</h2>
        <p class="mt-2 text-sm text-slate-300 max-w-2xl">
          影で回るAIが「予兆検知 →
          根回し準備」まで済ませます。あなたは最後の「直感」で介入し、ワンクリックで決裁します。
        </p>
      </div>

      <div class="hidden xl:block w-[360px] shrink-0">
        <div
          class="relative h-[160px] rounded-xl overflow-hidden border border-slate-800 bg-slate-950/40"
        >
          <app-neural-orb class="absolute inset-0 opacity-90"></app-neural-orb>
          <div class="relative p-4">
            <div class="text-xs text-slate-200 font-bold">24/7 Shadow Monitoring</div>
            <div class="mt-1 text-sm text-slate-300">兆候を検知したら即、介入プランへ。</div>
            <div class="mt-4 flex gap-2">
              <button
                type="button"
                class="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm"
                (click)="goSimulator()"
              >
                介入へ
              </button>
              <button
                type="button"
                class="px-3 py-2 rounded-lg border border-slate-800 bg-white/5 hover:bg-white/10 text-slate-200 font-semibold text-sm"
                (click)="goSimulator('alert')"
              >
                デモ
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-4 grid-cols-1 md:grid-cols-4">
      @for (k of kpis(); track k.label) {
        <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
          <div class="text-[11px] text-slate-400 font-bold uppercase tracking-wider">
            {{ k.label }}
          </div>
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

    @if (activeAlert(); as alert) {
      <div class="mt-4">
        <div class="text-sm font-semibold text-slate-200">アクティブなアラート</div>
        <button
          type="button"
          class="mt-2 w-full text-left rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/15 p-4 flex items-center gap-4"
          (click)="goSimulator('alert', alert.id)"
        >
          <div
            class="h-12 w-12 rounded-xl bg-rose-500/15 border border-rose-500/30 grid place-items-center text-rose-200 font-black"
          >
            !
          </div>
          <div class="min-w-0">
            <div class="text-base font-bold truncate">{{ alert.title }}</div>
            <div class="text-sm text-slate-300 truncate">{{ alert.subtitle }}</div>
          </div>
          <div class="ml-auto text-right">
            <div class="text-xs text-slate-400 font-semibold">RISK</div>
            <div class="text-lg font-extrabold text-rose-200">{{ alert.risk }}%</div>
          </div>
        </button>
      </div>
    }

    <div class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <div class="flex items-center justify-between gap-4">
          <div>
            <div class="text-[11px] text-slate-400 font-bold uppercase tracking-wider">
              Talent Matrix
            </div>
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

      <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <div class="text-[11px] text-slate-400 font-bold uppercase tracking-wider">
          AI Watchdog Log
        </div>
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
  private readonly router = inject(Router);

  protected readonly kpis = computed(() => {
    const members = this.store.members();
    const scored = members.map((m) => ({ m, s: scoreMember(m) }));
    const avgRisk = scored.length
      ? scored.reduce((sum, x) => sum + x.s.risk, 0) / scored.length
      : 0;
    const avgMotivation = scored.length
      ? scored.reduce((sum, x) => sum + x.s.motivation, 0) / scored.length
      : 0;
    const highRiskCount = scored.filter((x) => x.s.risk >= 70).length;

    const engagement = clampPct(100 - avgRisk * 0.6);
    const careerFit = clampPct(avgMotivation);
    const margin = clampPct(96 + (avgMotivation - 50) * 0.35 - avgRisk * 0.1);

    return [
      {
        label: 'エンゲージメント',
        value: engagement,
        suffix: '%',
        color: '#10b981',
        delta: '▲ 2.4pt',
        deltaColor: '#10b981',
      },
      {
        label: 'キャリア適合率',
        value: careerFit,
        suffix: '%',
        color: '#d946ef',
        delta: '介入で「成長機会」を再設計',
        deltaColor: '#94a3b8',
      },
      {
        label: '離職リスク (High)',
        value: highRiskCount,
        suffix: '名',
        color: '#f43f5e',
        delta: highRiskCount ? '※要対応' : '平常運転',
        deltaColor: highRiskCount ? '#f43f5e' : '#10b981',
      },
      {
        label: '予測粗利益率',
        value: margin,
        suffix: '%',
        color: '#f59e0b',
        delta: '自動根回しで調整コスト削減',
        deltaColor: '#94a3b8',
      },
    ];
  });

  protected readonly activeAlert = computed(() => {
    const worst = this.store
      .members()
      .map((m) => ({ m, s: scoreMember(m) }))
      .sort((a, b) => b.s.risk - a.s.risk)[0];
    if (!worst || worst.s.risk < 70) return null;
    return {
      id: worst.m.id,
      risk: worst.s.risk,
      title: `要介入: ${worst.m.name}`,
      subtitle: '週報/面談ログより「燃え尽き」シグナルを検知。クリックして介入プランを確認。',
    };
  });

  protected readonly matrixPoints = computed(() => {
    return this.store.members().map((m) => {
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
    const rows = [
      { t: '09:00', text: '全社解析完了（週報/勤怠/チャット）', dot: '#6366f1' },
      { t: '10:15', text: '1on1候補の自動調整を開始', dot: '#06b6d4' },
    ];
    const alert = this.activeAlert();
    if (alert)
      rows.push({ t: '10:30', text: `${alert.title} / RISK=${alert.risk}%`, dot: '#f43f5e' });
    rows.push({ t: '11:00', text: '新規案件マッチング中…', dot: '#10b981' });
    return rows;
  });

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
    void this.store.loadOnce();
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
