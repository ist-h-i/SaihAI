import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiClient } from './api-client';
import { AuthTokenStore } from './auth-token.store';
import { AppConfigService } from './config/app-config.service';
import {
  Member,
  PlanStreamComplete,
  PlanStreamLog,
  PlanStreamProgress,
  ProjectTeamMember,
  Project,
  SimulationPlan,
  SimulationResult,
  TeamSuggestion,
  TeamSuggestionsResponse,
} from './types';

@Injectable({ providedIn: 'root' })
export class SimulatorStore {
  private readonly api: ApiClient;
  private readonly config: AppConfigService;
  private readonly tokenStore: AuthTokenStore;

  readonly projects = signal<Project[]>([]);
  readonly members = signal<Member[]>([]);

  readonly selectedProjectId = signal<string | null>(null);
  readonly selectedMemberIds = signal<string[]>([]);
  readonly currentTeam = signal<ProjectTeamMember[]>([]);
  readonly currentTeamLoading = signal(false);
  readonly currentTeamError = signal<string | null>(null);
  readonly simulationResult = signal<SimulationResult | null>(null);
  readonly teamSuggestionsResponse = signal<TeamSuggestionsResponse | null>(null);
  readonly planProgress = signal<PlanStreamProgress | null>(null);
  readonly planProgressLog = signal<PlanStreamProgress[]>([]);
  readonly planDiscussionLog = signal<PlanStreamLog[]>([]);
  readonly streaming = signal(false);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  private readonly loaded = signal(false);
  private planStream: EventSource | null = null;
  private readonly streamLineLimit = 2000;

  readonly selectedProject = computed(() => {
    const id = this.selectedProjectId();
    return this.projects().find((p) => p.id === id) ?? null;
  });

  readonly selectedMembers = computed(() => {
    const wanted = new Set(this.selectedMemberIds());
    return this.members().filter((m) => wanted.has(m.id));
  });

  readonly teamSuggestions = computed<TeamSuggestion[]>(() => {
    return this.teamSuggestionsResponse()?.suggestions ?? [];
  });

  constructor(api: ApiClient, config: AppConfigService, tokenStore: AuthTokenStore) {
    this.api = api;
    this.config = config;
    this.tokenStore = tokenStore;
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
      if (!this.selectedProjectId() && projects.length) {
        this.selectedProjectId.set(projects[0].id);
      }
      if (this.selectedProjectId()) {
        await this.loadProjectTeam(this.selectedProjectId() as string);
      }
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
    this.teamSuggestionsResponse.set(null);
    this.resetProgress();
    void this.loadProjectTeam(projectId);
  }

  toggleMember(memberId: string): void {
    const current = this.selectedMemberIds();
    const next = current.includes(memberId)
      ? current.filter((id) => id !== memberId)
      : [...current, memberId];
    this.selectedMemberIds.set(next);
    this.teamSuggestionsResponse.set(null);
  }

  setSelectedMembers(memberIds: string[]): void {
    const unique = Array.from(new Set(memberIds));
    this.selectedMemberIds.set(unique);
    this.teamSuggestionsResponse.set(null);
  }

  focusMember(memberId: string): void {
    const current = this.selectedMemberIds();
    if (current.includes(memberId)) return;
    this.selectedMemberIds.set([...current, memberId]);
  }

  clearSelection(): void {
    this.selectedMemberIds.set([]);
    this.simulationResult.set(null);
    this.teamSuggestionsResponse.set(null);
    this.resetProgress();
  }

  async runSimulation(): Promise<void> {
    const projectId = this.selectedProjectId();
    if (!projectId) {
      this.error.set('案件を選択してください');
      return;
    }
    const memberIds = this.selectedMemberIds();
    if (!memberIds.length) {
      await this.loadTeamSuggestions(projectId);
      return;
    }

    await this.runSimulationWithMembers(projectId, memberIds);
  }

  async applyTeamSuggestion(suggestion: TeamSuggestion): Promise<void> {
    const projectId = this.selectedProjectId();
    if (!projectId) {
      this.error.set('案件を選択してください');
      return;
    }
    if (!suggestion.applyable || !suggestion.memberIds.length) {
      this.error.set('この案は適用できません');
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    this.simulationResult.set(null);
    this.resetProgress();
    try {
      await firstValueFrom(
        this.api.applyTeamSuggestion({
          projectId,
          memberIds: suggestion.memberIds,
          minAvailability: this.teamSuggestionsResponse()?.minAvailability,
        })
      );
      this.setSelectedMembers(suggestion.memberIds);
      this.teamSuggestionsResponse.set(null);
      await this.runSimulationWithMembers(projectId, suggestion.memberIds, { keepLoading: true });
      return;
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.error.set(e instanceof Error ? e.message : 'failed to apply suggestion');
      }
    } finally {
      this.streaming.set(false);
      this.loading.set(false);
    }
  }

  private async runSimulationWithMembers(
    projectId: string,
    memberIds: string[],
    options?: { keepLoading?: boolean }
  ): Promise<void> {
    if (!options?.keepLoading) {
      this.loading.set(true);
      this.error.set(null);
      this.simulationResult.set(null);
      this.resetProgress();
    }
    try {
      const evaluation = await firstValueFrom(this.api.evaluateSimulation({ projectId, memberIds }));
      const plans = await this.streamPlans(evaluation.id);
      const result: SimulationResult = { ...evaluation, plans };
      this.simulationResult.set(result);
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.error.set(e instanceof Error ? e.message : 'simulate failed');
      }
    } finally {
      this.streaming.set(false);
      if (!options?.keepLoading) {
        this.loading.set(false);
      }
    }
  }

  closePlanStream(): void {
    if (this.planStream) {
      this.planStream.close();
      this.planStream = null;
    }
  }

  private resetProgress(): void {
    this.closePlanStream();
    this.planProgress.set(null);
    this.planProgressLog.set([]);
    this.planDiscussionLog.set([]);
    this.streaming.set(false);
  }

  private async loadTeamSuggestions(projectId: string): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    this.simulationResult.set(null);
    this.teamSuggestionsResponse.set(null);
    this.resetProgress();
    try {
      const response = await firstValueFrom(this.api.getTeamSuggestions({ projectId }));
      this.teamSuggestionsResponse.set(response);
      if (!response.suggestions?.length) {
        this.error.set('候補プールから編成案を作れませんでした');
      }
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.error.set(e instanceof Error ? e.message : 'failed to suggest team');
      }
    } finally {
      this.loading.set(false);
    }
  }

  async loadProjectTeam(projectId: string): Promise<void> {
    this.currentTeamLoading.set(true);
    this.currentTeamError.set(null);
    try {
      const response = await firstValueFrom(this.api.getProjectTeam(projectId));
      this.currentTeam.set(response.members ?? []);
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.currentTeamError.set(e instanceof Error ? e.message : 'failed to load team');
      }
      this.currentTeam.set([]);
    } finally {
      this.currentTeamLoading.set(false);
    }
  }

  private async streamPlans(simulationId: string): Promise<SimulationPlan[]> {
    if (typeof EventSource === 'undefined') {
      return firstValueFrom(this.api.generatePlans(simulationId));
    }
    return new Promise((resolve, reject) => {
      this.closePlanStream();
      const url = this.buildStreamUrl(simulationId);
      const source = new EventSource(url);
      this.planStream = source;
      this.streaming.set(true);
      let done = false;

      source.addEventListener('progress', (event) => {
        if (done) return;
        const data = this.parseEvent<PlanStreamProgress>(event);
        if (!data) return;
        this.planProgress.set(data);
        const entries = this.splitStreamLines(data.message).map((message) => ({ ...data, message }));
        if (!entries.length) return;
        this.planProgressLog.update((curr) => this.capStreamLines([...curr, ...entries]));
      });

      source.addEventListener('log', (event) => {
        if (done) return;
        const data = this.parseEvent<PlanStreamLog>(event);
        if (!data) return;
        const entries = this.splitStreamLines(data.message).map((message) => ({ ...data, message }));
        if (!entries.length) return;
        this.planDiscussionLog.update((curr) => this.capStreamLines([...curr, ...entries]));
      });

      source.addEventListener('complete', (event) => {
        const data = this.parseEvent<PlanStreamComplete>(event);
        if (!data?.plans?.length) return;
        done = true;
        const finalProgress: PlanStreamProgress = {
          phase: 'complete',
          message: 'completed',
          progress: 100,
        };
        this.planProgress.set(finalProgress);
        this.planProgressLog.update((curr) => [...curr, finalProgress]);
        this.streaming.set(false);
        this.closePlanStream();
        resolve(data.plans);
      });

      source.addEventListener('error', () => {
        if (done) return;
        void this.handleStreamError(simulationId, resolve, reject);
      });
    });
  }

  private parseEvent<T>(event: Event): T | null {
    if (!(event instanceof MessageEvent)) return null;
    try {
      return JSON.parse(String(event.data)) as T;
    } catch {
      return null;
    }
  }

  private async handleStreamError(
    simulationId: string,
    resolve: (plans: SimulationPlan[]) => void,
    reject: (reason?: unknown) => void
  ): Promise<void> {
    this.closePlanStream();
    this.streaming.set(false);
    try {
      const fallback = await firstValueFrom(this.api.generatePlans(simulationId));
      resolve(fallback);
    } catch (error) {
      reject(error);
    }
  }

  private buildStreamUrl(simulationId: string): string {
    const endpoint = `${this.config.apiBaseUrl.replace(/\/+$/, '')}/simulations/${simulationId}/plans/stream`;
    const url = new URL(endpoint, window.location.origin);
    const token = this.tokenStore.token();
    if (token) {
      url.searchParams.set('token', token);
    }
    return url.toString();
  }

  private splitStreamLines(message: string): string[] {
    const lines = String(message ?? '')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    return lines;
  }

  private capStreamLines<T>(entries: T[]): T[] {
    if (entries.length <= this.streamLineLimit) return entries;
    return entries.slice(-this.streamLineLimit);
  }
}
