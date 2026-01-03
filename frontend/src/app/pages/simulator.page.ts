import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subscription } from 'rxjs';

import { NeuralOrbComponent } from '../components/neural-orb.component';
import { SimulatorStore } from '../core/simulator-store';
import { SimulationResult } from '../core/types';

type HaisaEmotion =
  | 'standard'
  | 'panic'
  | 'joy'
  | 'anxious'
  | 'relieved'
  | 'explosion'
  | 'energetic'
  | 'determined'
  | 'hopeful'
  | 'curious';

const HAISA_ASSET_DIR = '../../assets/haisaikun';
const HAISA_IMAGE_BY_EMOTION: Record<HaisaEmotion, string> = {
  standard: 'standard.png',
  panic: 'anxiety.png',
  joy: 'joy.png',
  anxious: 'anxiety.png',
  relieved: 'relief.png',
  explosion: 'explosion.png',
  energetic: 'energy.png',
  determined: 'effort.png',
  hopeful: 'hope.png',
  curious: 'haste.png',
};
const HAISA_DEFAULT_IMAGE = HAISA_IMAGE_BY_EMOTION.standard;

const HAISA_LABELS: Record<HaisaEmotion, string> = {
  standard: 'スタンダード',
  panic: '焦り',
  joy: '喜び',
  anxious: '不安',
  relieved: '安心',
  explosion: '爆発',
  energetic: 'エネルギー',
  determined: '決意',
  hopeful: '希望',
  curious: '好奇心',
};

interface ChatEntry {
  from: 'ai' | 'user';
  text: string;
  emotion?: HaisaEmotion;
}

@Component({
  imports: [NeuralOrbComponent],
  template: `
    <h2 class="text-2xl font-extrabold tracking-tight">戦術シミュレーター</h2>
    <p class="mt-1 text-sm text-slate-300">
      案件と候補者を選び、AIの「未来予測」と介入プランを確認します。
    </p>
    @if (store.error(); as err) {
      <div class="text-sm text-rose-300 mb-3">{{ err }}</div>
    }

    <div class="grid gap-4 lg:grid-cols-2">
      <section class="rounded-lg border border-slate-800 bg-slate-950/40 p-4 surface-panel">
        <div class="font-semibold mb-3">入力（対象の選択）</div>

        <label class="block text-sm text-slate-300 mb-2">案件</label>
        <select
          class="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2"
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
            class="text-xs px-2 py-1 rounded border border-slate-700 hover:border-slate-500"
            (click)="store.clearSelection()"
          >
            Clear
          </button>
        </div>

        <div class="mt-2 grid gap-2">
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
                  class="px-3 py-2 rounded-lg border border-slate-700 bg-white/5 hover:bg-white/10 text-sm font-semibold"
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
          class="mt-4 w-full rounded bg-indigo-600 hover:bg-indigo-500 px-3 py-2 font-semibold disabled:opacity-60"
          [disabled]="store.loading()"
          (click)="store.runSimulation()"
        >
          AI自動編成
        </button>
        @if (store.loading()) {
          <div class="text-xs text-slate-400 mt-2">running…</div>
        }
      </section>

      <section class="rounded-lg border border-slate-800 bg-slate-950/40 p-4 surface-panel">
        <div class="flex items-center justify-between gap-3 mb-3">
          <div class="font-semibold">結果</div>
          <button
            type="button"
            class="text-xs px-3 py-2 rounded-lg border border-slate-800 bg-white/5 hover:bg-white/10 text-slate-200 font-semibold disabled:opacity-60"
            [disabled]="!store.simulationResult()"
            (click)="openOverlay('manual')"
          >
            介入（HITL）を開く
          </button>
        </div>

        @if (store.simulationResult(); as r) {
          <div>
            <div class="text-sm text-slate-300">
              {{ r.project.name }} / pattern:
              <span class="text-slate-100 font-semibold">{{ r.pattern }}</span>
            </div>

            <div class="mt-3 grid gap-3 sm:grid-cols-2">
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
              <div class="text-sm font-semibold">要件カバー率</div>
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

            <div class="mt-4">
              <div class="text-sm font-semibold">未来タイムライン</div>
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

            <div class="mt-4">
              <div class="text-sm font-semibold">エージェント所見</div>
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
            </div>

            <div class="mt-4">
              <div class="text-sm font-semibold">3プラン（A/B/C）</div>
              <div class="mt-2 grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                @for (p of r.plans; track p.id) {
                  <div
                    class="relative rounded border border-slate-800 bg-slate-900/30 p-3 transition hover:border-slate-500"
                    [class.border-emerald-500]="p.recommended"
                    [class.border-slate-800]="!p.recommended"
                  >
                    @if (p.recommended) {
                      <span
                        class="absolute right-3 top-3 text-[10px] font-bold tracking-wider rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-emerald-200"
                      >
                        AI推奨
                      </span>
                    }
                    <div class="font-semibold text-slate-100 leading-tight pr-10">
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
            </div>
          </div>
        } @else {
          <div class="text-sm text-slate-400">
            案件とメンバーを選択して「AI自動編成」を押すと結果が表示されます。
          </div>
        }
      </section>
    </div>

    @if (overlayOpen()) {
      <div class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/70" (click)="closeOverlay()"></div>
        <div
          class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(1100px,calc(100vw-3rem))] h-[min(760px,calc(100vh-3rem))] rounded-2xl overflow-hidden border border-slate-800 bg-slate-950/70 surface-overlay"
        >
          <app-neural-orb class="absolute inset-0 opacity-30"></app-neural-orb>

          <div class="relative h-full flex flex-col">
            <div
              class="h-14 shrink-0 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur px-5 flex items-center justify-between"
            >
              <div class="flex items-center gap-3">
                <div
                  class="px-3 py-1 rounded-full text-xs font-extrabold tracking-wide text-white status-indicator"
                  [class.bg-rose-500]="overlayMode() === 'alert'"
                  [class.bg-indigo-600]="overlayMode() !== 'alert'"
                  [class.status-alert]="overlayMode() === 'alert'"
                  [class.status-stable]="overlayMode() !== 'alert'"
                >
                  {{ overlayMode() === 'alert' ? 'ALERT ACTIVE' : 'MANUAL MODE' }}
                </div>
                <div class="font-bold text-slate-100">介入チェックポイント</div>
              </div>
              <button
                type="button"
                class="text-slate-300 hover:text-white text-2xl leading-none"
                (click)="closeOverlay()"
              >
                ×
              </button>
            </div>

            <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 overflow-hidden">
              <div class="border-r border-slate-800/80 overflow-hidden flex flex-col">
                <div class="p-5 border-b border-slate-800/80 bg-white/5">
                  <div class="text-[11px] text-slate-400 font-bold uppercase tracking-wider">
                    {{ overlayKpiLabel() }}
                  </div>
                  <div
                    class="mt-1 text-4xl font-extrabold tracking-tight"
                    [class.text-rose-200]="overlayMode() === 'alert'"
                    [class.text-emerald-200]="overlayMode() !== 'alert'"
                  >
                    {{ overlayKpiVal() }}
                  </div>
                  <div class="mt-1 text-sm text-slate-300">{{ overlayKpiDesc() }}</div>
                </div>

                <div
                  class="px-5 py-3 text-[11px] text-slate-400 font-bold uppercase tracking-wider border-b border-slate-800/80"
                >
                  Agent Log
                </div>
                <div class="flex-1 overflow-auto p-5 space-y-2 font-mono text-xs">
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
                      <span class="text-slate-200">{{ l.text }}</span>
                    </div>
                  }
                </div>
              </div>

              <div class="overflow-hidden flex flex-col">
                <div class="p-5 border-b border-slate-800/80">
                  <div class="text-sm font-bold text-slate-100">戦略プランの選択</div>
                  @if (store.simulationResult(); as r) {
                    <div class="mt-3 grid gap-3 md:grid-cols-3">
                      @for (p of r.plans; track p.id) {
                        <button
                          type="button"
                          class="relative text-left rounded-xl border bg-slate-900/40 p-4 hover:bg-slate-900/55 status-plan"
                          [class.border-emerald-500]="p.recommended"
                          [class.border-slate-800]="!p.recommended"
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
                          <div class="font-extrabold text-slate-100">
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

                <div class="flex-1 overflow-hidden flex flex-col">
                  <div class="flex-1 overflow-auto p-5 space-y-3">
                    @for (m of overlayChat(); track $index) {
                      <div
                        class="haisa-chat-line"
                        [class.justify-end]="m.from === 'user'"
                        [class.justify-start]="m.from !== 'user'"
                      >
                        @if (m.from !== 'user') {
                          <div
                            class="haisa-avatar"
                            [style.background-image]="haisaAvatarImage(m.emotion ?? 'standard')"
                            [attr.data-emotion]="haisaEmotionLabel(m.emotion)"
                            aria-hidden="true"
                          ></div>
                        }
                        <div
                          class="max-w-[80%] rounded-2xl px-4 py-3 text-sm border haisa-bubble"
                          [class.bg-indigo-600]="m.from === 'user'"
                          [class.text-white]="m.from === 'user'"
                          [class.border-indigo-500/40]="m.from === 'user'"
                          [class.bg-slate-900/40]="m.from !== 'user'"
                          [class.text-slate-100]="m.from !== 'user'"
                          [class.border-slate-800]="m.from !== 'user'"
                          [class.haisa-bubble-ai]="m.from !== 'user'"
                        >
                          {{ m.text }}
                        </div>
                      </div>
                    }
                  </div>

                  <div class="p-5 border-t border-slate-800/80 flex gap-3 items-center">
                    <input
                      #chatInput
                      type="text"
                      class="flex-1 bg-slate-950/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-indigo-500/60"
                      placeholder="指示を入力（空欄で承認）"
                      (keydown.enter)="sendChat(chatInput.value); chatInput.value = ''"
                      autocomplete="off"
                    />
                    <button
                      type="button"
                      class="px-4 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm"
                      (click)="sendChat(chatInput.value); chatInput.value = ''"
                    >
                      実行
                    </button>
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

  ngOnDestroy(): void {
    this.timers.splice(0).forEach((t) => window.clearTimeout(t));
    this.querySub?.unsubscribe();
    this.querySub = null;
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
    const initialEmotion = this.emotionForOverlay(mode, r);
    this.overlayLog.set([]);
    this.overlayChat.set([
      {
        from: 'ai',
        emotion: initialEmotion,
        text: r
          ? `状況を分析しました。推奨プランは「${r.agents.gunshi.recommend}」です。承認（空欄）または指示を入力してください。`
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
    this.overlayChat.update((curr) => [
      ...curr,
      {
        from: 'ai',
        emotion: 'determined',
        text: `Plan ${id} が選択されました。条件を追加しますか？（空欄で承認）`,
      },
    ]);
  }

  protected sendChat(text: string): void {
    const trimmed = text.trim();
    if (!trimmed) {
      this.overlayChat.update((curr) => [
        ...curr,
        { from: 'ai', emotion: 'relieved', text: '承認されました。実行します。' },
      ]);
      const t = window.setTimeout(() => this.closeOverlay(), 900);
      this.timers.push(t);
      return;
    }

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
    return HAISA_LABELS[emotion ?? 'standard'];
  }

  protected haisaAvatarImage(emotion: HaisaEmotion = 'standard'): string {
    const file = HAISA_IMAGE_BY_EMOTION[emotion] ?? HAISA_DEFAULT_IMAGE;
    return `url('${HAISA_ASSET_DIR}/${file}')`;
  }

  private emotionForOverlay(
    mode: 'alert' | 'manual',
    result: SimulationResult | null
  ): HaisaEmotion {
    if (!result) return mode === 'alert' ? 'panic' : 'determined';
    if (mode === 'alert') {
      const risk = result.metrics.riskPct ?? 0;
      if (risk >= 85) return 'explosion';
      if (risk >= 70) return 'panic';
      if (risk >= 55) return 'anxious';
      return 'relieved';
    }
    const fit = result.metrics.careerFitPct ?? 0;
    if (fit >= 80) return 'hopeful';
    if (fit >= 65) return 'joy';
    if (fit >= 45) return 'energetic';
    return 'determined';
  }
  private emotionFromChatRequest(text: string): HaisaEmotion {
    if (text.includes('承認')) return 'relieved';
    if (text.includes('再計算')) return 'hopeful';
    if (text.includes('Plan')) return 'determined';
    if (text.includes('危険') || text.includes('爆発')) return 'panic';
    return 'energetic';
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
