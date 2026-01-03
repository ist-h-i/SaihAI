import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { ToastService } from '../toast.service';

export const apiErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const toast = inject(ToastService);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
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
