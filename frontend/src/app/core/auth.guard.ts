import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';

import { AuthTokenStore } from './auth-token.store';

export const authGuard: CanActivateFn = (_route, state) => {
  const tokenStore = inject(AuthTokenStore);
  const router = inject(Router);
  if (tokenStore.token()) return true;

  return router.createUrlTree(['/login'], {
    queryParams: { redirect: state.url },
  });
};
