import { Component, input } from '@angular/core';
import { ESTADOS_PAGO, PagoDetalle, etiquetaMetodo } from '../models/pago';
import { formatoPesos } from '../utils/dinero';
import { fechaCorta, fechaHora } from '../utils/fechas';

/**
 * Comprobante de un pago (RF-36, RF-37). Lo usan la pantalla de Pagos, al registrar, y el detalle
 * del pago. Se puede imprimir (al imprimir solo se ve el comprobante). Registra un pago que ya
 * ocurrió: no es una factura electrónica (D16, D17).
 */
@Component({
  selector: 'app-comprobante',
  templateUrl: './comprobante.html',
  styleUrl: './comprobante.css',
})
export class Comprobante {
  readonly pago = input.required<PagoDetalle>();
  readonly pesos = formatoPesos;
  readonly fechaCorta = fechaCorta;
  readonly fechaHora = fechaHora;
  readonly metodo = etiquetaMetodo;
  readonly estados = ESTADOS_PAGO;
}
