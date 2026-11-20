import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  DestroyRef,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Comprobante } from '../comprobante/comprobante';
import {
  Cotizacion,
  ESTADOS_MENSUALIDAD,
  EstadoMensualidadRespuesta,
  METODOS_PAGO,
  MetodoPago,
  PagoDetalle,
  etiquetaMetodo,
} from '../models/pago';
import { PagosService } from '../services/pagos.service';
import { formatoPesos } from '../utils/dinero';
import { fechaCorta } from '../utils/fechas';
import { normalizarPlaca } from '../utils/placa';
import { MESES_MAXIMO, MESES_MINIMO, mensajeReferencia, reglaMeses } from '../utils/reglas';

/** La referencia depende del método: obligatoria en transferencia y tarjeta, vacía en efectivo. */
function reglaReferencia(grupo: AbstractControl): ValidationErrors | null {
  const mensaje = mensajeReferencia(
    String(grupo.get('metodo')?.value ?? ''),
    grupo.get('referencia')?.value,
  );
  return mensaje ? { referencia: mensaje } : null;
}

/** Inicio del mensaje 409 del backend cuando la tarifa cambió entre el resumen y la confirmación. */
const TARIFA_CAMBIO = 'La tarifa cambió';

/**
 * Registrar pago (HU-29 y HU-30). Ambos roles. Pasos: buscar la placa y ver el estado de su
 * mensualidad, elegir meses y método, revisar el resumen que calcula el servidor (RNF-27) y
 * confirmar. Al confirmar se envía el monto que se vio en el resumen (monto_confirmado): si la tarifa
 * cambió entretanto, el servidor no registra el pago y la pantalla muestra el resumen nuevo para
 * confirmar otra vez. El responsable es la cuenta de la sesión (lo pone el servidor).
 */
@Component({
  selector: 'app-pagos',
  imports: [ReactiveFormsModule, RouterLink, Comprobante],
  templateUrl: './pagos.html',
  styleUrls: ['../estilos/gestion.css', './pagos.css'],
})
export class Pagos {
  private readonly api = inject(PagosService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly busqueda = this.fb.nonNullable.group({ placa: [''] });
  readonly form = this.fb.group(
    {
      meses: this.fb.nonNullable.control(1, reglaMeses),
      metodo: this.fb.nonNullable.control<MetodoPago>('EFECTIVO'),
      referencia: this.fb.nonNullable.control(''),
    },
    { validators: reglaReferencia },
  );
  readonly opcionesMeses = Array.from(
    { length: MESES_MAXIMO - MESES_MINIMO + 1 },
    (_, i) => MESES_MINIMO + i,
  );
  readonly metodos = METODOS_PAGO;
  readonly estado = signal<EstadoMensualidadRespuesta | null>(null);
  readonly resumen = signal<Cotizacion | null>(null);
  readonly comprobante = signal<PagoDetalle | null>(null);
  readonly buscando = signal(false);
  readonly calculando = signal(false);
  readonly registrando = signal(false);
  readonly ocupado = computed(() => this.buscando() || this.calculando() || this.registrando());
  readonly errorBusqueda = signal('');
  readonly errorPago = signal('');
  readonly avisoTarifa = signal('');
  readonly enviado = signal(false);
  readonly pesos = formatoPesos;
  readonly fecha = fechaCorta;
  readonly metodo = etiquetaMetodo;
  readonly estados = ESTADOS_MENSUALIDAD;
  readonly referenciaVisible = computed(() => this.metodoActual() !== 'EFECTIVO');
  private readonly metodoActual = signal<MetodoPago>('EFECTIVO');
  private readonly tituloResumen = viewChild<ElementRef<HTMLElement>>('tituloResumen');

  constructor() {
    this.form.controls.metodo.valueChanges.pipe(takeUntilDestroyed()).subscribe((metodo) => {
      this.metodoActual.set(metodo);
      // En efectivo no hay referencia: se limpia para no enviar un dato que el servidor rechazaría.
      if (metodo === 'EFECTIVO') this.form.controls.referencia.setValue('');
    });
    // Desde otra pantalla se puede llegar con la placa: /pagos?placa=ABC123.
    const placa = inject(ActivatedRoute).snapshot.queryParamMap.get('placa');
    if (placa) {
      this.busqueda.setValue({ placa });
      this.buscar();
    }
  }

  buscar(): void {
    if (this.ocupado()) return;
    const placa = normalizarPlaca(this.busqueda.controls.placa.value);
    this.busqueda.controls.placa.setValue(placa);
    this.errorBusqueda.set('');
    this.errorPago.set('');
    this.resumen.set(null);
    this.comprobante.set(null);
    if (!placa) {
      this.estado.set(null);
      this.errorBusqueda.set('Escribe la placa del vehículo.');
      return;
    }
    this.cargarEstado(placa);
  }

  private cargarEstado(placa: string): void {
    this.buscando.set(true);
    this.api
      .estado(placa)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (estado) => {
          this.buscando.set(false);
          this.estado.set(estado);
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          this.estado.set(null);
          this.errorBusqueda.set(
            error.status === 404
              ? `La placa ${placa} no está registrada. Revísala o registra el vehículo en Vehículos.`
              : this.mensajeError(error),
          );
        },
      });
  }

  /** Mensaje del campo (los de la referencia vienen del validador del grupo). */
  error(campo: 'meses' | 'referencia'): string {
    if (!this.enviado()) return '';
    if (campo === 'meses') return String(this.form.controls.meses.errors?.['meses'] ?? '');
    return String(this.form.errors?.['referencia'] ?? '');
  }

  /** Paso 1: el servidor calcula el periodo y el monto. No se guarda nada (RNF-27). */
  revisar(): void {
    const estado = this.estado();
    if (!estado || this.ocupado()) return;
    this.enviado.set(true);
    this.errorPago.set('');
    this.avisoTarifa.set('');
    if (this.form.invalid) {
      this.errorPago.set('Revisa los campos señalados antes de continuar.');
      return;
    }
    this.pedirResumen(estado.placa);
  }

  private pedirResumen(placa: string, aviso = ''): void {
    this.calculando.set(true);
    this.api
      .cotizacion(placa, Number(this.form.controls.meses.value))
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (cotizacion) => {
          this.calculando.set(false);
          this.resumen.set(cotizacion);
          this.avisoTarifa.set(aviso);
          // El foco va al resumen para que se lea antes de confirmar.
          setTimeout(() => this.tituloResumen()?.nativeElement.focus());
        },
        error: (error: HttpErrorResponse) => {
          this.calculando.set(false);
          this.resumen.set(null);
          this.errorPago.set(this.mensajeError(error));
        },
      });
  }

  /** Volver al formulario sin registrar nada (caso PA-07). */
  volver(): void {
    if (this.registrando()) return;
    this.resumen.set(null);
    this.avisoTarifa.set('');
  }

  /** Paso 2: registrar con el monto que se vio en el resumen. */
  confirmar(): void {
    const resumen = this.resumen();
    if (!resumen || this.ocupado()) return;
    const valor = this.form.getRawValue();
    this.registrando.set(true);
    this.errorPago.set('');
    this.api
      .registrar({
        placa: resumen.placa,
        meses: resumen.meses,
        metodo: valor.metodo,
        referencia: valor.metodo === 'EFECTIVO' ? null : valor.referencia.trim(),
        monto_confirmado: resumen.monto,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (pago) => {
          this.registrando.set(false);
          this.resumen.set(null);
          this.avisoTarifa.set('');
          this.comprobante.set(pago);
          this.form.reset({ meses: 1, metodo: 'EFECTIVO', referencia: '' });
          this.enviado.set(false);
          this.recargarEstado(resumen.placa);
        },
        error: (error: HttpErrorResponse) => {
          this.registrando.set(false);
          const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
          if (error.status === 409 && detalle.startsWith(TARIFA_CAMBIO)) {
            // HU-30.2: no se registró nada. Se muestra el resumen con el monto nuevo para confirmar otra vez.
            this.pedirResumen(resumen.placa, detalle);
            return;
          }
          this.resumen.set(null);
          this.errorPago.set(this.mensajeError(error));
          this.recargarEstado(resumen.placa);
        },
      });
  }

  /** Registrar otro pago del mismo vehículo o de otro. */
  nuevoPago(): void {
    this.comprobante.set(null);
  }

  imprimir(): void {
    window.print();
  }

  private recargarEstado(placa: string): void {
    this.api
      .estado(placa)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (estado) => this.estado.set(estado), error: () => undefined });
  }

  /** 'Vence hoy', 'Falta 1 día', 'Faltan 12 días'. */
  diasRestantes(dias: number | null): string {
    if (dias === null) return '';
    if (dias === 0) return 'Vence hoy';
    return dias === 1 ? 'Falta 1 día' : `Faltan ${dias} días`;
  }

  meses(n: number): string {
    return n === 1 ? '1 mes' : `${n} meses`;
  }

  /** RNF-15: siempre un mensaje en español; el detalle técnico nunca llega a la pantalla. */
  private mensajeError(error: HttpErrorResponse): string {
    const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (error.status === 404) return 'El vehículo ya no existe. Vuelve a buscar la placa.';
    if (error.status === 409)
      return detalle || 'La operación entra en conflicto con los datos actuales.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para registrar pagos.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y vuelve a intentarlo.';
  }
}
