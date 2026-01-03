import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { AuthTokenStore } from '../auth-token.store';
import { AppConfigService } from '../config/app-config.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const config = inject(AppConfigService);
  const tokenStore = inject(AuthTokenStore);
  const token = tokenStore.token();
  if (!token) return next(req);
  if (!req.url.startsWith(config.apiBaseUrl)) return next(req);
  if (req.headers.has('Authorization')) return next(req);

  const headerValue = token.startsWith('Bearer ') ? token : `Bearer ${token}`;
  return next(req.clone({ setHeaders: { Authorization: headerValue } }));
};
