import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfigService } from './config/app-config.service';

export interface LoginRequest {
  userId: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

@Injectable({ providedIn: 'root' })
export class AuthClient {
  private readonly http = inject(HttpClient);
  private readonly config = inject(AppConfigService);

  login(payload: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(this.buildUrl('/auth/login'), payload);
  }

  private buildUrl(path: string): string {
    return `${this.config.apiBaseUrl}${path}`;
  }
}
