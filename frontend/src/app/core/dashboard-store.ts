import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiClient } from './api-client';
import {
  ApprovalDecisionResponse,
  ApprovalRequestResponse,
  DashboardAlert,
  DashboardKpi,
  DashboardPendingAction,
  DashboardProposal,
  DashboardTimelineEntry,
  HistoryEntry,
  Member,
} from './types';

@Injectable({ providedIn: 'root' })
export class DashboardStore {
  private readonly api: ApiClient;

  readonly kpis = signal<DashboardKpi[]>([]);
  readonly alerts = signal<DashboardAlert[]>([]);
  readonly members = signal<Member[]>([]);
  readonly proposals = signal<DashboardProposal[]>([]);
  readonly pendingActions = signal<DashboardPendingAction[]>([]);
  readonly watchdog = signal<DashboardTimelineEntry[]>([]);
  readonly checkpointWaiting = signal(false);
  readonly lastUpdatedAt = signal<Date | null>(null);
  readonly history = signal<HistoryEntry[]>([]);
  readonly historyStatusFilter = signal<string | null>(null);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  constructor(api: ApiClient) {
    this.api = api;
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const response = await firstValueFrom(this.api.getDashboardInitial());
      this.kpis.set(response.kpis ?? []);
      this.alerts.set(response.alerts ?? []);
      this.members.set(response.members ?? []);
      this.proposals.set(response.proposals ?? []);
      this.pendingActions.set(response.pendingActions ?? []);
      this.watchdog.set(response.watchdog ?? []);
      this.checkpointWaiting.set(Boolean(response.checkpointWaiting));
      this.lastUpdatedAt.set(new Date());
      try {
        await this.loadHistory();
      } catch (err) {
        if (!(err instanceof HttpErrorResponse)) {
          this.error.set(err instanceof Error ? err.message : 'failed to load history');
        }
      }
    } catch (e) {
      if (!(e instanceof HttpErrorResponse)) {
        this.error.set(e instanceof Error ? e.message : 'failed to load');
      }
    } finally {
      this.loading.set(false);
    }
  }

  async requestNemawashiApproval(actionId: number): Promise<ApprovalRequestResponse> {
    return firstValueFrom(this.api.requestNemawashiApproval(actionId));
  }

  async approveApproval(approvalId: string): Promise<ApprovalDecisionResponse> {
    return firstValueFrom(this.api.approveApproval(approvalId));
  }

  async rejectApproval(approvalId: string): Promise<{ status: string }> {
    return firstValueFrom(this.api.rejectApproval(approvalId));
  }

  async loadHistory(status?: string | null): Promise<void> {
    const targetStatus = status ?? this.historyStatusFilter();
    const entries = await firstValueFrom(
      this.api.getHistory({ status: targetStatus ?? undefined, limit: 50 })
    );
    this.history.set(entries ?? []);
  }

  async setHistoryFilter(status: string | null): Promise<void> {
    this.historyStatusFilter.set(status);
    try {
      await this.loadHistory(status);
    } catch (err) {
      if (!(err instanceof HttpErrorResponse)) {
        this.error.set(err instanceof Error ? err.message : 'failed to load history');
      }
    }
  }
}
