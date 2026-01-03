import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  APP_INITIALIZER,
  provideBrowserGlobalErrorListeners,
  provideZonelessChangeDetection,
} from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { App } from './app/app';
import { routes } from './app/app.routes';
import { AppConfigService } from './app/core/config/app-config.service';
import { apiErrorInterceptor } from './app/core/interceptors/api-error.interceptor';
import { authInterceptor } from './app/core/interceptors/auth.interceptor';

bootstrapApplication(App, {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideHttpClient(withInterceptors([authInterceptor, apiErrorInterceptor])),
    provideRouter(routes),
    {
      provide: APP_INITIALIZER,
      useFactory: (config: AppConfigService) => () => config.load(),
      deps: [AppConfigService],
      multi: true,
    },
  ],
}).catch((err) => console.error(err));
