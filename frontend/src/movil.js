// En el celular, las tablas con encabezado se muestran como tarjetas.
// Este observador copia el título de cada columna a sus celdas (data-label),
// así no hay que repetir los nombres de columna en cada pantalla.
function etiquetar(tabla) {
  const ths = [...tabla.querySelectorAll('thead th')].map(th => th.textContent.trim())
  if (!ths.length) return
  tabla.classList.add('tarjetas')
  for (const fila of tabla.querySelectorAll('tbody tr, tfoot tr')) {
    let col = 0
    for (const td of fila.children) {
      const etiqueta = ths[col] || ''
      if (td.dataset.label !== etiqueta) td.dataset.label = etiqueta
      col += td.colSpan || 1
    }
  }
}

export function activarTablasMoviles() {
  let pendiente = false
  const revisar = () => {
    pendiente = false
    document.querySelectorAll('table').forEach(etiquetar)
  }
  new MutationObserver(() => {
    if (!pendiente) { pendiente = true; requestAnimationFrame(revisar) }
  }).observe(document.body, { childList: true, subtree: true, characterData: true })
}
