import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { authInterceptor } from './auth/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Iteración 2: el interceptor agrega el token y reacciona a la sesión vencida (401).
    provideHttpClient(withInterceptors([authInterceptor])),
    provideRouter(routes),
  ],
};
