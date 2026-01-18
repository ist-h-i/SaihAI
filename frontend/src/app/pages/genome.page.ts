import { Component, computed, inject, signal } from '@angular/core';

import { EmptyStateComponent } from '../components/empty-state.component';
import { NeuralOrbComponent } from '../components/neural-orb.component';
import { SimulatorStore } from '../core/simulator-store';
import { Member } from '../core/types';

function toLowerSafe(v: string): string {
  return (v ?? '').toLowerCase();
}

function hasAny(haystack: string, words: readonly string[]): boolean {
  return words.some((w) => haystack.includes(w));
}

const RISK_HINTS = ['疲労', '燃え尽き', '飽き', '対人トラブル', '噂', '炎上'] as const;

@Component({
  imports: [NeuralOrbComponent, EmptyStateComponent],
  template: `
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0">
        <div class="ui-kicker">Genome DB</div>
        <h2 class="mt-1 text-2xl font-extrabold tracking-tight">人材データベース</h2>
        <p class="mt-2 text-sm text-slate-300 max-w-2xl">
          スキル・メモ・リスク兆候を横断して、介入すべき候補を見つけます。
        </p>
      </div>

      <div class="w-full lg:w-[360px] shrink-0">
        <div class="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950/40">
          <app-neural-orb class="absolute inset-0 opacity-90"></app-neural-orb>
          <div class="relative p-4">
            <div class="text-xs text-slate-200 font-bold">Genome Scan</div>
            <div class="mt-1 text-sm text-slate-300">
              検索とフィルタで、最適な候補を絞り込みます。
            </div>
            <div class="mt-3 text-xs text-slate-300">
              MEMBERS:
              <span class="font-extrabold text-slate-100">{{ store.members().length }}</span>
            </div>
            <div class="mt-2 text-xs text-slate-400">
              フィルタ中: {{ activeFilterLabel() }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="ui-panel">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div class="text-sm font-bold text-slate-100">Skill Genome Matrix</div>
          <div class="text-xs text-slate-400">スキルをクリックでフィルタ</div>
        </div>
        <div class="mt-3 overflow-auto">
          <table class="min-w-full text-xs">
            <thead class="text-slate-400">
              <tr>
                <th class="text-left font-semibold pr-4 py-2">Member</th>
                @for (s of topSkills(); track s) {
                  <th class="text-left font-semibold pr-4 py-2">
                    <button
                      type="button"
                      class="hover:text-white ui-focus-ring"
                      (click)="toggleSkill(s)"
                    >
                      {{ s }}
                    </button>
                  </th>
                }
              </tr>
            </thead>
            <tbody>
              @for (m of filteredMembers(); track m.id) {
                <tr class="border-t border-slate-800/80">
                  <td class="py-2 pr-4">
                    <div class="font-semibold text-slate-100">{{ m.name }}</div>
                    <div class="text-[11px] text-slate-400">
                      ¥{{ m.cost }} / {{ m.availability }}%
                    </div>
                  </td>
                  @for (s of topSkills(); track s) {
                    <td class="py-2 pr-4">
                      <span
                        class="inline-block h-2.5 w-2.5 rounded-full"
                        [class.bg-indigo-400]="m.skills.includes(s)"
                        [class.bg-slate-700]="!m.skills.includes(s)"
                      ></span>
                    </td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </div>
      </div>

      <div class="ui-panel">
        <div class="text-sm font-bold text-slate-100">Filter</div>
        <div class="mt-3">
          <div class="text-xs text-slate-400 font-semibold">検索</div>
          <input
            type="text"
            class="mt-2 w-full bg-slate-950/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 ui-focus-ring"
            placeholder="例: U001 / angular / testing"
            [value]="query()"
            (input)="onQueryInput($event)"
          />
        </div>
        <div class="mt-4">
          <div class="text-xs text-slate-400 font-semibold">スキル</div>
          <div class="mt-2 flex flex-wrap gap-2">
            @for (s of topSkills(); track s) {
              <button
                type="button"
                class="px-3 py-2 rounded-full border text-xs font-bold ui-focus-ring"
                [class.border-indigo-500/50]="skillFilter() === s"
                [class.bg-indigo-500/15]="skillFilter() === s"
                [class.text-indigo-100]="skillFilter() === s"
                [class.border-slate-800]="skillFilter() !== s"
                [class.bg-white/5]="skillFilter() !== s"
                [class.text-slate-200]="skillFilter() !== s"
                (click)="toggleSkill(s)"
              >
                {{ s }}
              </button>
            }
          </div>
          <button
            type="button"
            class="mt-3 text-xs text-slate-400 hover:text-white ui-focus-ring"
            (click)="clearFilters()"
          >
            Clear
          </button>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div>
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div class="text-sm font-bold text-slate-100">Member Cards</div>
          <div class="text-xs text-slate-400">表示: {{ filteredMembers().length }} 件</div>
        </div>

        @if (filteredMembers().length) {
          <div class="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            @for (m of filteredMembers(); track m.id) {
              <button
                type="button"
                class="text-left ui-panel-interactive min-h-[240px] flex flex-col"
                [class.border-indigo-500/60]="selectedMemberId() === m.id"
                [class.bg-indigo-500/10]="selectedMemberId() === m.id"
                (click)="selectMember(m)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="font-extrabold text-slate-100 truncate">{{ m.name }}</div>
                    <div class="mt-1 text-xs text-slate-400 truncate">
                      {{ memberSkillsLabel(m) }}
                    </div>
                  </div>
                  <div class="text-right shrink-0">
                    <div class="text-sm text-slate-200 font-bold">¥{{ m.cost }}</div>
                    <div class="text-xs text-slate-400">{{ m.availability }}%</div>
                  </div>
                </div>

                <div class="mt-3 flex flex-wrap gap-2">
                  @for (s of previewSkills(m); track s) {
                    <span
                      class="text-[11px] px-2 py-1 rounded-full border border-slate-800 bg-white/5 text-slate-200 max-w-full break-words"
                      >{{ s }}</span
                    >
                  }
                </div>

                <div class="mt-auto flex items-center justify-between">
                  <div
                    class="text-[11px] px-2 py-1 rounded-full border font-bold"
                    [class.border-rose-500/40]="isRisky(m)"
                    [class.bg-rose-500/10]="isRisky(m)"
                    [class.text-rose-200]="isRisky(m)"
                    [class.border-emerald-500/40]="!isRisky(m)"
                    [class.bg-emerald-500/10]="!isRisky(m)"
                    [class.text-emerald-200]="!isRisky(m)"
                  >
                    {{ isRisky(m) ? 'RISK' : 'STABLE' }}
                  </div>
                  <div class="text-xs text-slate-400">
                    {{ selectedMemberId() === m.id ? '選択中' : '詳細を見る' }}
                  </div>
                </div>
              </button>
            }
          </div>
        } @else {
          <app-empty-state
            kicker="Empty"
            title="該当するメンバーがいません"
            description="検索条件やフィルタを調整してください。"
            primaryLabel="フィルタをクリア"
            (primary)="clearFilters()"
          />
        }
      </div>

      <aside class="ui-panel">
        @if (selectedMember(); as m) {
          <div class="flex items-center justify-between gap-2">
            <div>
              <div class="ui-kicker">Selected</div>
              <div class="text-base font-semibold text-slate-100">{{ m.name }}</div>
            </div>
            <button
              type="button"
              class="text-xs text-slate-400 hover:text-white ui-focus-ring"
              (click)="clearSelection()"
            >
              クリア
            </button>
          </div>
          <div class="mt-3">
            <div class="text-xs text-slate-400 font-semibold">Notes</div>
            <div class="mt-2 text-sm text-slate-200 leading-relaxed break-words">
              {{ m.notes }}
            </div>
          </div>
          <div class="mt-4">
            <div class="text-xs text-slate-400 font-semibold">Skills</div>
            <div class="mt-2 flex flex-wrap gap-2">
              @for (s of m.skills; track s) {
                <span
                  class="text-[11px] px-2 py-1 rounded-full border border-slate-800 bg-white/5 text-slate-200 max-w-full break-words"
                  >{{ s }}</span
                >
              }
            </div>
          </div>
          <div class="mt-4">
            <div class="text-xs text-slate-400 font-semibold">Profile</div>
            <div class="mt-2 text-xs text-slate-300">
              Role: {{ m.role ?? 'N/A' }} / Level: {{ m.skillLevel ?? '-' }}
            </div>
            @if (m.careerAspiration) {
              <div class="mt-1 text-xs text-slate-400">{{ m.careerAspiration }}</div>
            }
            @if (m.analysis) {
              <div class="mt-2 text-xs text-slate-300">
                Pattern: {{ m.analysis.patternName ?? m.analysis.patternId }}
              </div>
              <div class="text-xs text-slate-400">
                Decision: {{ m.analysis.finalDecision ?? 'N/A' }}
              </div>
            }
          </div>
        } @else {
          <app-empty-state
            kicker="Select"
            title="詳細を見るメンバーを選択"
            description="カードをクリックすると詳細がここに表示されます。"
          />
        }
      </aside>
    </div>
  `,
})
export class GenomePage {
  protected readonly store = inject(SimulatorStore);

  protected readonly query = signal('');
  protected readonly skillFilter = signal<string | null>(null);
  protected readonly selectedMemberId = signal<string | null>(null);

  protected readonly allSkills = computed(() => {
    const set = new Set<string>();
    for (const m of this.store.members()) for (const s of m.skills) set.add(s);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  });

  protected readonly topSkills = computed(() => {
    const counts = new Map<string, number>();
    for (const m of this.store.members())
      for (const s of m.skills) counts.set(s, (counts.get(s) ?? 0) + 1);
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 8)
      .map(([s]) => s);
  });

  protected readonly filteredMembers = computed(() => {
    const q = toLowerSafe(this.query().trim());
    const skill = this.skillFilter();
    return this.store.members().filter((m) => {
      if (skill && !m.skills.includes(skill)) return false;
      if (!q) return true;
      return (
        toLowerSafe(m.name).includes(q) ||
        toLowerSafe(m.notes).includes(q) ||
        m.skills.some((s) => toLowerSafe(s).includes(q))
      );
    });
  });

  protected readonly selectedMember = computed(() => {
    const id = this.selectedMemberId();
    if (!id) return null;
    const member = this.store.members().find((m) => m.id === id);
    if (!member) return null;
    const visible = this.filteredMembers().some((m) => m.id === id);
    return visible ? member : null;
  });

  protected readonly activeFilterLabel = computed(() => {
    const q = this.query().trim();
    const skill = this.skillFilter();
    if (q && skill) return `${skill} + keyword`;
    if (skill) return skill;
    if (q) return 'keyword';
    return 'なし';
  });

  constructor() {
    void this.store.loadOnce();
  }

  protected onQueryInput(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    this.query.set(target.value);
  }

  protected toggleSkill(skill: string): void {
    this.skillFilter.set(this.skillFilter() === skill ? null : skill);
  }

  protected clearFilters(): void {
    this.query.set('');
    this.skillFilter.set(null);
  }

  protected selectMember(member: Member): void {
    this.selectedMemberId.set(this.selectedMemberId() === member.id ? null : member.id);
  }

  protected clearSelection(): void {
    this.selectedMemberId.set(null);
  }

  protected isRisky(m: Member): boolean {
    if (m.analysis?.riskRiskScore != null) return m.analysis.riskRiskScore >= 70;
    return hasAny(m.notes ?? '', RISK_HINTS);
  }

  protected previewSkills(m: Member): readonly string[] {
    return m.skills.slice(0, 4);
  }

  protected memberSkillsLabel(m: Member): string {
    return m.skills.join(' / ');
  }
}
