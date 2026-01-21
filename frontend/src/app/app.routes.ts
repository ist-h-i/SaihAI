import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'login',
    loadComponent: () => import('./pages/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'dashboard',
    loadComponent: () => import('./pages/dashboard.page').then((m) => m.DashboardPage),
    canActivate: [authGuard],
  },
  {
    path: 'simulator',
    loadComponent: () => import('./pages/simulator.page').then((m) => m.SimulatorPage),
    canActivate: [authGuard],
  },
  {
    path: 'saved-plans',
    loadComponent: () => import('./pages/saved-plans.page').then((m) => m.SavedPlansPage),
    canActivate: [authGuard],
  },
  {
    path: 'genome',
    loadComponent: () => import('./pages/genome.page').then((m) => m.GenomePage),
    canActivate: [authGuard],
  },
];
