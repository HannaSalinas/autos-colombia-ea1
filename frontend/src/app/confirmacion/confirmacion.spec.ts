import { TestBed } from '@angular/core/testing';
import { Confirmacion } from './confirmacion';

describe('Confirmación de acciones sensibles (RNF-21)', () => {
  const montar = () => {
    const fixture = TestBed.createComponent(Confirmacion);
    fixture.componentRef.setInput('titulo', 'Desactivar cuenta');
    fixture.componentRef.setInput(
      'mensaje',
      '¿Desactivar la cuenta de Diego Arango (diego.arango)?',
    );
    fixture.componentRef.setInput('textoConfirmar', 'Sí, desactivar');
    fixture.detectChanges();
    return fixture;
  };
  const botones = (el: HTMLElement) => [...el.querySelectorAll('button')];

  it('nombra el elemento y pone el foco en Cancelar', () => {
    const fixture = montar();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role="alertdialog"]')?.textContent).toContain(
      'Diego Arango (diego.arango)',
    );
    expect(document.activeElement?.textContent?.trim()).toBe('Cancelar');
  });

  it('solo confirma al pulsar el botón de confirmar', () => {
    const fixture = montar();
    const eventos: string[] = [];
    fixture.componentInstance.confirmar.subscribe(() => eventos.push('confirmar'));
    fixture.componentInstance.cancelar.subscribe(() => eventos.push('cancelar'));
    const [cancelar, confirmar] = botones(fixture.nativeElement);
    cancelar.click();
    confirmar.click();
    expect(eventos).toEqual(['cancelar', 'confirmar']);
  });

  it('mientras procesa no permite pulsar de nuevo', () => {
    const fixture = montar();
    fixture.componentRef.setInput('ocupado', true);
    fixture.detectChanges();
    expect(botones(fixture.nativeElement).every((b) => b.disabled)).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Procesando…');
  });
});
