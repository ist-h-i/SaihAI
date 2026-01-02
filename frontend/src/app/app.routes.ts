import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    loadComponent: () => import('./pages/dashboard.page').then((m) => m.DashboardPage),
  },
  {
    path: 'simulator',
    loadComponent: () => import('./pages/simulator.page').then((m) => m.SimulatorPage),
  },
  { path: 'genome', loadComponent: () => import('./pages/genome.page').then((m) => m.GenomePage) },
];
