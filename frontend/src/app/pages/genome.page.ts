import { Component, computed, inject, signal } from '@angular/core';

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
  imports: [NeuralOrbComponent],
  template: `
    <div class="flex items-start justify-between gap-6">
      <div class="min-w-0">
        <div class="text-[11px] text-slate-400 font-bold uppercase tracking-wider">Genome DB</div>
        <h2 class="mt-1 text-2xl font-extrabold tracking-tight">人材データベース</h2>
      </div>

      <div class="hidden xl:block w-[360px] shrink-0">
        <div
          class="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950/40"
        >
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
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <div class="flex items-center justify-between gap-3">
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
                    <button type="button" class="hover:text-white" (click)="toggleSkill(s)">
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

      <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <div class="text-sm font-bold text-slate-100">Filter</div>
        <div class="mt-3">
          <div class="text-xs text-slate-400 font-semibold">検索</div>
          <input
            type="text"
            class="mt-2 w-full bg-slate-950/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-indigo-500/60"
            placeholder="例: tanaka / angular / testing"
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
                class="px-3 py-2 rounded-full border text-xs font-bold"
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
            class="mt-3 text-xs text-slate-400 hover:text-white"
            (click)="clearFilters()"
          >
            Clear
          </button>
        </div>
      </div>
    </div>

    <div class="mt-6">
      <div class="flex items-center justify-between gap-3">
        <div class="text-sm font-bold text-slate-100">Member Cards</div>
        <div class="text-xs text-slate-400">表示: {{ filteredMembers().length }} 件</div>
      </div>

      <div class="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        @for (m of filteredMembers(); track m.id) {
          <div
            class="group perspective-1000 rounded-xl cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950/70"
            tabindex="0"
          >
            <div
              class="relative preserve-3d transition-transform duration-700 group-hover:[transform:rotateY(180deg)] group-focus-within:[transform:rotateY(180deg)]"
            >
              <div
                class="backface-hidden rounded-xl border border-slate-800 bg-slate-950/40 p-4 min-h-[260px] flex flex-col"
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
                  <div class="text-xs text-slate-400">Hover で詳細</div>
                </div>
              </div>

              <div
                class="backface-hidden absolute inset-0 rounded-xl border border-slate-800 bg-slate-950/60 p-4 pr-3 [transform:rotateY(180deg)] overflow-y-auto overflow-x-hidden"
              >
                <div class="text-sm font-extrabold text-slate-100">Notes</div>
                <div class="mt-2 text-xs text-slate-300 leading-relaxed break-words">
                  {{ m.notes }}
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
                <div class="mt-4 text-[11px] text-slate-400">
                  Tip: skills をクリックでフィルタできます。
                </div>
              </div>
            </div>
          </div>
        }
      </div>
    </div>
  `,
})
export class GenomePage {
  protected readonly store = inject(SimulatorStore);

  protected readonly query = signal('');
  protected readonly skillFilter = signal<string | null>(null);

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
