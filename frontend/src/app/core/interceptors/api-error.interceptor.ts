import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthTokenStore } from '../auth-token.store';
import { LoggerService } from '../logger.service';
import { ToastService } from '../toast.service';

export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const toast = inject(ToastService);
  const tokenStore = inject(AuthTokenStore);
  const router = inject(Router);
  const logger = inject(LoggerService);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        logger.error('API request failed', {
          method: req.method,
          url: req.url,
          status: error.status,
          statusText: error.statusText,
          requestId: error.headers?.get('X-Request-ID') ?? req.headers.get('X-Request-ID') ?? undefined,
        });
        if (error.status === 401) {
          tokenStore.clearToken();
          if (!router.url.startsWith('/login')) {
            void router.navigate(['/login'], { queryParams: { redirect: router.url } });
          }
          return throwError(() => error);
        }
        toast.error(buildApiErrorMessage(error));
      }
      return throwError(() => error);
    })
  );
};

const buildApiErrorMessage = (error: HttpErrorResponse): string => {
  const statusLabel = error.status ? `APIエラー (${error.status})` : 'APIエラー (接続失敗)';
  const detail = extractErrorDetail(error);
  return detail ? `${statusLabel}: ${detail}` : statusLabel;
};

const extractErrorDetail = (error: HttpErrorResponse): string | undefined => {
  if (typeof error.error === 'string') return error.error;
  if (error.error && typeof error.error === 'object') {
    const payload = error.error as { detail?: string; message?: string };
    if (payload.detail) return payload.detail;
    if (payload.message) return payload.message;
  }
  if (error.statusText) return error.statusText;
  return undefined;
};
