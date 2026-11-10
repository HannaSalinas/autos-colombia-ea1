import { AfterViewInit, Component, ElementRef, input, output, viewChild } from '@angular/core';

/**
 * Confirmación explícita de una acción sensible (RNF-21): siempre nombra el elemento afectado
 * (la persona o la celda) y no hace nada hasta que se pulsa el botón de confirmar.
 * Al aparecer, el foco va a "Cancelar", la opción segura.
 */
@Component({
  selector: 'app-confirmacion',
  template: `
    <section
      class="confirmacion"
      role="alertdialog"
      aria-modal="false"
      aria-labelledby="confirmacion-titulo"
      aria-describedby="confirmacion-mensaje"
    >
      <h2 id="confirmacion-titulo">{{ titulo() }}</h2>
      <p id="confirmacion-mensaje">{{ mensaje() }}</p>
      <div class="acciones">
        <button #cancelarBoton type="button" (click)="cancelar.emit()" [disabled]="ocupado()">
          Cancelar</button
        ><button type="button" class="peligro" (click)="confirmar.emit()" [disabled]="ocupado()">
          {{ ocupado() ? 'Procesando…' : textoConfirmar() }}
        </button>
      </div>
    </section>
  `,
  styles: `
    .confirmacion {
      padding: 22px 26px;
      margin-bottom: 24px;
      border: 1px solid #d4a899;
      background: #fffaf7;
      border-radius: 16px;
    }
    h2 {
      font-size: 19px;
      margin: 0 0 6px;
    }
    p {
      color: #586b60;
      line-height: 1.6;
      margin: 0 0 14px;
    }
    .acciones {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    button {
      font: inherit;
      font-size: 14px;
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid #c9d7ce;
      color: #214c43;
      background: #fff;
      cursor: pointer;
    }
    button.peligro {
      background: #a03930;
      border-color: #a03930;
      color: #fff;
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    button:focus-visible {
      outline: 3px solid #aa7b2e;
      outline-offset: 3px;
    }
  `,
})
export class Confirmacion implements AfterViewInit {
  readonly titulo = input.required<string>();
  /** Debe nombrar el elemento afectado, por ejemplo "¿Desactivar la cuenta de Diego Arango?". */
  readonly mensaje = input.required<string>();
  readonly textoConfirmar = input.required<string>();
  readonly ocupado = input(false);
  readonly confirmar = output<void>();
  readonly cancelar = output<void>();
  private readonly cancelarBoton =
    viewChild.required<ElementRef<HTMLButtonElement>>('cancelarBoton');

  ngAfterViewInit(): void {
    this.cancelarBoton().nativeElement.focus();
  }
}
