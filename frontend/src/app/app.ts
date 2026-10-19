import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterOutlet } from '@angular/router';
import { timeout } from 'rxjs';

@Component({
  imports: [RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  protected readonly connectionState = signal<'checking' | 'available' | 'unavailable'>('checking');
  protected readonly connectionMessage = computed(() => {
    switch (this.connectionState()) {
      case 'available':
        return 'Servicio disponible';
      case 'unavailable':
        return 'No se pudo conectar con el servicio';
      default:
        return 'Comprobando conexión…';
    }
  });

  constructor() {
    inject(HttpClient)
      .get<{ status?: unknown } | null>('/health')
      .pipe(timeout(5000), takeUntilDestroyed())
      .subscribe({
        next: (response) =>
          this.connectionState.set(response?.status === 'ok' ? 'available' : 'unavailable'),
        error: () => this.connectionState.set('unavailable'),
      });
  }
}
