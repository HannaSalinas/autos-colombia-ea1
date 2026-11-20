/**
 * Texto visible de un elemento para las pruebas: une los nodos de texto con un espacio para que
 * "Monto a pagar" (dt) y "$ 120.000" (dd) no queden pegados.
 */
export const textoDe = (el: HTMLElement): string => {
  const partes: string[] = [];
  const recorrido = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  while (recorrido.nextNode()) partes.push(recorrido.currentNode.textContent ?? '');
  return partes.join(' ').replace(/\s+/g, ' ');
};
