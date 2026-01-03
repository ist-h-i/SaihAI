import { HttpErrorResponse, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs';

import { AppConfigService } from '../config/app-config.service';
import { LoggerService } from '../logger.service';

const REQUEST_ID_HEADER = 'X-Request-ID';

export const httpLoggingInterceptor: HttpInterceptorFn = (req, next) => {
  const config = inject(AppConfigService);
  const logger = inject(LoggerService);

  if (!req.url.startsWith(config.apiBaseUrl)) return next(req);

  const started = nowMs();
  const requestId = req.headers.get(REQUEST_ID_HEADER) ?? undefined;

  logger.debug('HTTP ->', {
    method: req.method,
    url: req.urlWithParams,
    requestId,
  });

  return next(req).pipe(
    tap({
      next: (event) => {
        if (!(event instanceof HttpResponse)) return;
        const elapsedMs = nowMs() - started;
        logger.debug('HTTP <-', {
          method: req.method,
          url: req.urlWithParams,
          status: event.status,
          elapsedMs: Math.round(elapsedMs),
          requestId: event.headers.get(REQUEST_ID_HEADER) ?? requestId,
        });
      },
      error: (error: unknown) => {
        const elapsedMs = nowMs() - started;
        if (error instanceof HttpErrorResponse) {
          logger.debug('HTTP <- error', {
            method: req.method,
            url: req.urlWithParams,
            status: error.status,
            statusText: error.statusText,
            elapsedMs: Math.round(elapsedMs),
            requestId: error.headers?.get(REQUEST_ID_HEADER) ?? requestId,
          });
          return;
        }
        logger.debug('HTTP <- error', {
          method: req.method,
          url: req.urlWithParams,
          elapsedMs: Math.round(elapsedMs),
          error: String(error),
          requestId,
        });
      },
    })
  );
};

const nowMs = (): number => {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
};

