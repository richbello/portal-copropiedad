import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, fecha, NOMBRES } from '../api'
import { Aviso, useDatos, useSesion } from '../App'
import Recibo from './Recibo'
import { textoCuando } from './Calendario'

export default function Inicio() {
  const { usuario } = useSesion()
  const nav = useNavigate()
  const [cuentas, setCuentas] = useState([])
  const [error, setError] = useState('')
  const { datos: solicitudes } = useDatos('/api/solicitudes')
  const { datos: eventos } = useDatos('/api/eventos')
  const ahora = new Date()
  const proximos = (eventos || []).filter(e => new Date(e.fin || e.inicio) >= ahora).slice(0, 3)

  useEffect(() => {
    Promise.all(usuario.unidades.map(u => api.get(`/api/unidades/${u.id}/estado-cuenta`)))
      .then(setCuentas).catch(e => setError(e.message))
  }, [usuario])

  const abiertas = (solicitudes || []).filter(s => !['respondida', 'cerrada'].includes(s.estado))
  const recientes = (solicitudes || []).slice(0, 5)

  return (
    <>
      <div className="encabezado">
        <div>
          <h1>Hola, {usuario.nombre.split(' ')[0]}</h1>
          {usuario.unidades.length === 0 && <p>Su usuario aún no tiene una unidad asignada. Comuníquese con la administración.</p>}
        </div>
        <Link className="boton" to="/solicitudes/nueva">Radicar una solicitud</Link>
      </div>
      <Aviso>{error}</Aviso>
      <div className="pila">
        {cuentas.map(ec => <Recibo key={ec.unidad_id} ec={ec} />)}
      </div>

      {proximos.length > 0 && <section className="panel" style={{ marginTop: 16 }}>
        <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Próximos eventos</h2>
          <Link to="/calendario">Ver calendario</Link>
        </div>
        <div className="rejilla rejilla-4">
          {proximos.map(e => <div key={e.id} className={`evento cat-borde-${e.categoria}`}>
            <strong>{e.titulo}</strong><div className="peq">{textoCuando(e)}</div>{e.lugar && <div className="peq suave">{e.lugar}</div>}
          </div>)}
        </div>
      </section>}

      <div className="rejilla rejilla-2" style={{ marginTop: 16 }}>
        <section className="panel">
          <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Mis solicitudes</h2>
            <Link to="/solicitudes">Ver todas</Link>
          </div>
          <p className="suave peq" style={{ marginBottom: 8 }}>
            {abiertas.length === 0 ? 'No tiene solicitudes pendientes.' : `${abiertas.length} en curso.`}
          </p>
          {recientes.length === 0 ? <p className="vacio">Aquí verá el avance de lo que radique ante la administración.</p> :
            <table><tbody>
              {recientes.map(s => (
                <tr key={s.id} className="clic" onClick={() => nav(`/solicitudes/${s.id}`)}>
                  <td><strong>{s.asunto}</strong><div className="peq suave">{s.radicado} · {NOMBRES.tipos[s.tipo]}</div></td>
                  <td className="derecha"><span className={`estado ${s.estado}`}>{NOMBRES.estados[s.estado]}</span></td>
                </tr>))}
            </tbody></table>}
        </section>
        <section className="panel">
          <h2>Movimientos recientes</h2>
          {cuentas.length === 0 ? <p className="vacio">Sin movimientos.</p> :
            <table><tbody>
              {cuentas.flatMap(ec => ec.movimientos.slice(-6).reverse().map(m => (
                <tr key={`${ec.unidad_id}-${m.tipo}-${m.id}`}>
                  <td>{m.concepto}<div className="peq suave">{fecha(m.fecha)}{cuentas.length > 1 ? ` · ${ec.unidad}` : ''}</div></td>
                  <td className="derecha" style={{ color: m.credito ? 'var(--verde)' : undefined, whiteSpace: 'nowrap' }}>
                    {m.credito ? `− ${Number(m.credito).toLocaleString('es-CO')}` : Number(m.debito).toLocaleString('es-CO')}
                  </td>
                </tr>)))}
            </tbody></table>}
          <p style={{ marginTop: 12 }}><Link to="/estado-cuenta">Ver estado de cuenta completo</Link></p>
        </section>
      </div>
    </>
  )
}
