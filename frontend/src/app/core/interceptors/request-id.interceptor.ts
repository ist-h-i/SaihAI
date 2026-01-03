import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { AppConfigService } from '../config/app-config.service';

const REQUEST_ID_HEADER = 'X-Request-ID';

export const requestIdInterceptor: HttpInterceptorFn = (req, next) => {
  const config = inject(AppConfigService);
  if (!req.url.startsWith(config.apiBaseUrl)) return next(req);
  if (req.headers.has(REQUEST_ID_HEADER)) return next(req);

  const requestId = createRequestId();
  return next(req.clone({ setHeaders: { [REQUEST_ID_HEADER]: requestId } }));
};

const createRequestId = (): string => {
  const maybeCrypto = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (maybeCrypto?.randomUUID) return maybeCrypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

