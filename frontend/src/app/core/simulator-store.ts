import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiClient } from './api-client';
import { Member, Project, SimulationResult } from './types';

@Injectable({ providedIn: 'root' })
export class SimulatorStore {
  private readonly api: ApiClient;

  readonly projects = signal<Project[]>([]);
  readonly members = signal<Member[]>([]);

  readonly selectedProjectId = signal<string | null>(null);
  readonly selectedMemberIds = signal<string[]>([]);
  readonly simulationResult = signal<SimulationResult | null>(null);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  private readonly loaded = signal(false);

  readonly selectedProject = computed(() => {
    const id = this.selectedProjectId();
    return this.projects().find((p) => p.id === id) ?? null;
  });

  readonly selectedMembers = computed(() => {
    const wanted = new Set(this.selectedMemberIds());
    return this.members().filter((m) => wanted.has(m.id));
  });

  constructor(api: ApiClient) {
    this.api = api;
  }

  async loadOnce(): Promise<void> {
    if (this.loaded()) return;
    this.loaded.set(true);

    this.loading.set(true);
    this.error.set(null);
    try {
      const [projects, members] = await Promise.all([
        firstValueFrom(this.api.getProjects()),
        firstValueFrom(this.api.getMembers()),
      ]);
      this.projects.set(projects);
      this.members.set(members);
      if (!this.selectedProjectId() && projects.length) this.selectedProjectId.set(projects[0].id);
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.error.set(e instanceof Error ? e.message : 'failed to load');
      }
    } finally {
      this.loading.set(false);
    }
  }

  setProject(projectId: string): void {
    if (this.selectedProjectId() === projectId) return;
    this.selectedProjectId.set(projectId);
    this.selectedMemberIds.set([]);
    this.simulationResult.set(null);
  }

  toggleMember(memberId: string): void {
    const current = this.selectedMemberIds();
    const next = current.includes(memberId)
      ? current.filter((id) => id !== memberId)
      : [...current, memberId];
    this.selectedMemberIds.set(next);
  }

  focusMember(memberId: string): void {
    const current = this.selectedMemberIds();
    if (current.includes(memberId)) return;
    this.selectedMemberIds.set([...current, memberId]);
  }

  clearSelection(): void {
    this.selectedMemberIds.set([]);
    this.simulationResult.set(null);
  }

  async runSimulation(): Promise<void> {
    const projectId = this.selectedProjectId();
    if (!projectId) {
      this.error.set('案件を選択してください');
      return;
    }
    const memberIds = this.selectedMemberIds();
    if (!memberIds.length) {
      this.error.set('メンバーを1人以上選択してください');
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    try {
      const result = await firstValueFrom(this.api.simulate({ projectId, memberIds }));
      this.simulationResult.set(result);
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.error.set(e instanceof Error ? e.message : 'simulate failed');
      }
    } finally {
      this.loading.set(false);
    }
  }
}
