import { useState } from 'react'
import { descargar, fecha, pesos } from '../api'

const EDADES = [
  ['al_dia', 'Por vencer'], ['1_30', '1 a 30 días'], ['31_60', '31 a 60 días'],
  ['61_90', '61 a 90 días'], ['mas_90', 'Más de 90 días'],
]

// La pieza central del portal: cuánto debo y qué tan vencido está.
export default function Recibo({ ec, acciones = true }) {
  const [error, setError] = useState('')
  const vencido = EDADES.slice(1).reduce((s, [k]) => s + ec.edades[k], 0)
  const total = EDADES.reduce((s, [k]) => s + ec.edades[k], 0)
  const clase = ec.saldo <= 0 ? 'a-favor' : vencido > 0 ? 'en-mora' : ''
  const leyenda = ec.saldo < 0 ? `Tiene un saldo a favor de ${pesos(-ec.saldo)}.`
    : ec.saldo === 0 ? 'Está al día. Puede descargar su paz y salvo.'
    : vencido > 0 ? `${pesos(vencido)} ya están vencidos. Ponerse al día evita más intereses de mora.`
    : 'Su saldo aún no está vencido.'

  const bajar = async (ruta, nombre) => {
    setError('')
    try { await descargar(ruta, nombre) } catch (e) { setError(e.message) }
  }

  return (
    <section className="recibo" aria-label={`Saldo de ${ec.unidad}`}>
      <div className="recibo-cuerpo">
        <div>
          <div className="recibo-unidad">{ec.unidad}, corte al {fecha(ec.fecha_corte)}</div>
          <div className={`recibo-saldo ${clase}`}>{pesos(Math.max(ec.saldo, 0))}</div>
          <p className="recibo-leyenda">{leyenda}</p>
          {error && <p className="aviso error peq" style={{ marginTop: 10 }}>{error}</p>}
        </div>
        {acciones && (
          <div className="recibo-acciones">
            <button className="secundario" onClick={() => bajar(`/api/unidades/${ec.unidad_id}/estado-cuenta.pdf`, 'estado_cuenta.pdf')}>
              Descargar estado de cuenta
            </button>
            <button disabled={!ec.puede_paz_y_salvo} title={ec.puede_paz_y_salvo ? '' : 'Disponible cuando el saldo esté en cero'}
              onClick={() => bajar(`/api/unidades/${ec.unidad_id}/paz-y-salvo.pdf`, 'paz_y_salvo.pdf')}>
              Descargar paz y salvo
            </button>
          </div>
        )}
      </div>
      {total > 0 && <>
        <div className="edades" role="img" aria-label="Distribución del saldo por antigüedad">
          {EDADES.map(([k]) => ec.edades[k] > 0 &&
            <span key={k} className={`edad-${k}`} style={{ width: `${ec.edades[k] / total * 100}%` }} />)}
        </div>
        <div className="edades-leyenda">
          {EDADES.map(([k, n]) => ec.edades[k] > 0 &&
            <span key={k}><i className={`edad-${k}`} />{n}: <strong className="num">{pesos(ec.edades[k])}</strong></span>)}
        </div>
      </>}
    </section>
  )
}
