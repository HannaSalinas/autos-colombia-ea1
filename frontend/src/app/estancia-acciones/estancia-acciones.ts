import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { Celda } from '../models/celda';
import {
  Correccion,
  DESCRIPCION_MAXIMA,
  MOTIVO_MAXIMO,
  Novedad,
  TIPOS_NOVEDAD,
  TipoNovedad,
} from '../models/estancia';
import { EstanciasService } from '../services/estancias.service';

const nonBlank: ValidatorFn = (c) =>
  typeof c.value === 'string' && c.value.trim() ? null : { required: true };
const limpiar = (texto: string) => texto.split(/\s+/).filter(Boolean).join(' ');

/**
 * Iteración 1, Fase 3: acciones sobre una estancia abierta.
 * - Corregir la celda cuando el conductor parqueó en otra (solo libre y compatible, con motivo).
 * - Registrar novedades del vehículo (rayón, golpe, objeto olvidado, otro).
 * El operador es el que se eligió en la consulta de Control de acceso.
 */
@Component({
  selector: 'app-estancia-acciones',
  imports: [ReactiveFormsModule],
  templateUrl: './estancia-acciones.html',
  styleUrl: './estancia-acciones.css',
})
export class EstanciaAcciones implements OnInit {
  private readonly api = inject(EstanciasService);
  private readonly fb = inject(FormBuilder);
  private readonly destroy = inject(DestroyRef);

  readonly estanciaId = input.required<number>();
  readonly celdaActual = input.required<string>();
  readonly operadorId = input<number | null>(null);
  /** Avisa al padre para que vuelva a consultar el vehículo con la celda nueva. */
  readonly corregida = output<Correccion>();

  readonly tipos = TIPOS_NOVEDAD;
  readonly motivoMaximo = MOTIVO_MAXIMO;
  readonly descripcionMaxima = DESCRIPCION_MAXIMA;
  readonly correccion = this.fb.group({
    celda_id: this.fb.control<number | null>(null, Validators.required),
    motivo: this.fb.nonNullable.control('', [nonBlank, Validators.maxLength(MOTIVO_MAXIMO)]),
  });
  readonly novedad = this.fb.group({
    tipo: this.fb.nonNullable.control<TipoNovedad | ''>('', Validators.required),
    descripcion: this.fb.nonNullable.control('', [
      nonBlank,
      Validators.maxLength(DESCRIPCION_MAXIMA),
    ]),
  });

  readonly disponibles = signal<Celda[]>([]);
  readonly correcciones = signal<Correccion[]>([]);
  readonly novedades = signal<Novedad[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly loadError = signal('');
  readonly errorCorreccion = signal('');
  readonly errorNovedad = signal('');
  readonly exitoNovedad = signal('');

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    const id = this.estanciaId();
    this.loading.set(true);
    this.loadError.set('');
    forkJoin({
      disponibles: this.api.celdasDisponibles(id),
      correcciones: this.api.correcciones(id),
      novedades: this.api.novedades(id),
    })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.disponibles.set(data.disponibles);
          this.correcciones.set(data.correcciones);
          this.novedades.set(data.novedades);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.loadError.set(this.mensaje(error));
        },
      });
  }

  corregir(): void {
    if (this.busy()) return;
    this.correccion.markAllAsTouched();
    const operador = this.operadorId();
    if (operador === null) {
      this.errorCorreccion.set('Selecciona el operador en la consulta antes de corregir la celda.');
      return;
    }
    if (this.correccion.invalid) return;
    const raw = this.correccion.getRawValue();
    this.saving.set(true);
    this.errorCorreccion.set('');
    this.api
      .corregirCelda(this.estanciaId(), {
        celda_id: raw.celda_id!,
        operador_id: operador,
        motivo: limpiar(raw.motivo),
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.corregida.emit(result);
        },
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          this.errorCorreccion.set(this.mensaje(error));
          // La lista pudo cambiar (otra portería ocupó la celda): se vuelve a cargar.
          if (error.status === 409) this.cargar();
        },
      });
  }

  registrarNovedad(): void {
    if (this.busy()) return;
    this.novedad.markAllAsTouched();
    const operador = this.operadorId();
    if (operador === null) {
      this.errorNovedad.set('Selecciona el operador en la consulta antes de registrar la novedad.');
      return;
    }
    if (this.novedad.invalid) return;
    const raw = this.novedad.getRawValue();
    this.saving.set(true);
    this.errorNovedad.set('');
    this.exitoNovedad.set('');
    this.api
      .registrarNovedad(this.estanciaId(), {
        tipo: raw.tipo as TipoNovedad,
        descripcion: limpiar(raw.descripcion),
        operador_id: operador,
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.novedades.update((lista) => [...lista, result]);
          this.novedad.reset();
          this.exitoNovedad.set('Novedad registrada.');
        },
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          this.errorNovedad.set(this.mensaje(error));
        },
      });
  }

  etiqueta(tipo: string): string {
    return this.tipos.find((t) => t.valor === tipo)?.etiqueta ?? tipo;
  }

  fecha(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(value));
  }

  private mensaje(error: HttpErrorResponse): string {
    if ([404, 409].includes(error.status) && typeof error.error?.detail === 'string')
      return error.error.detail;
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Consulta de nuevo antes de reintentar.';
  }
}
