import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  APP_INITIALIZER,
  ErrorHandler,
  provideBrowserGlobalErrorListeners,
  provideZonelessChangeDetection,
} from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { App } from './app/app';
import { routes } from './app/app.routes';
import { AppConfigService } from './app/core/config/app-config.service';
import { GlobalErrorHandler } from './app/core/global-error-handler';
import { apiErrorInterceptor } from './app/core/interceptors/api-error.interceptor';
import { authInterceptor } from './app/core/interceptors/auth.interceptor';
import { httpLoggingInterceptor } from './app/core/interceptors/http-logging.interceptor';
import { requestIdInterceptor } from './app/core/interceptors/request-id.interceptor';
import { LoggerService } from './app/core/logger.service';
import { ThemeService } from './app/core/theme.service';

bootstrapApplication(App, {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideHttpClient(
      withInterceptors([requestIdInterceptor, authInterceptor, httpLoggingInterceptor, apiErrorInterceptor])
    ),
    provideRouter(routes),
    { provide: ErrorHandler, useClass: GlobalErrorHandler },
    {
      provide: APP_INITIALIZER,
      useFactory: (config: AppConfigService, logger: LoggerService) => async () => {
        await config.load();
        logger.setMinLevel(config.logLevel ?? 'info');
        logger.configureServer({
          enabled: config.logToServer,
          apiBaseUrl: config.apiBaseUrl,
          minLevel: config.serverLogLevel ?? 'error',
        });
      },
      deps: [AppConfigService, LoggerService],
      multi: true,
    },
    {
      provide: APP_INITIALIZER,
      useFactory: (theme: ThemeService) => () => theme.init(),
      deps: [ThemeService],
      multi: true,
    },
  ],
}).catch((err) => console.error(err));
