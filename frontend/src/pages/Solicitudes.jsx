import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fecha, NOMBRES } from '../api'
import { Aviso, Encabezado, useDatos, useSesion } from '../App'

export function Semaforo({ s }) {
  if (s.color === 'gris') return <span className="semaforo gris">Atendida</span>
  const d = s.dias_restantes
  const txt = d < 0 ? `Vencida hace ${-d} día${d === -1 ? '' : 's'} hábil${d === -1 ? '' : 'es'}`
    : d === 0 ? 'Vence hoy' : `${d} día${d === 1 ? '' : 's'} hábil${d === 1 ? '' : 'es'}`
  return <span className={`semaforo ${s.color}`}>{txt}</span>
}

export default function Solicitudes() {
  const { usuario } = useSesion()
  const nav = useNavigate()
  const [estado, setEstado] = useState('')
  const [tipo, setTipo] = useState('')
  const [q, setQ] = useState('')
  const params = new URLSearchParams()
  if (estado) params.set('estado', estado)
  if (tipo) params.set('tipo', tipo)
  if (q.length > 2) params.set('q', q)
  const { datos, error } = useDatos(`/api/solicitudes?${params}`)
  const puedeRadicar = !['consejo', 'revisor_fiscal'].includes(usuario.rol)

  return (
    <>
      <Encabezado titulo="Solicitudes"
        descripcion="Cada solicitud tiene número de radicado y fecha límite de respuesta en días hábiles.">
        {puedeRadicar && <Link className="boton" to="/solicitudes/nueva">Radicar una solicitud</Link>}
      </Encabezado>
      <div className="panel">
        <div className="formulario-2" style={{ marginBottom: 16 }}>
          <label>Buscar<input value={q} onChange={e => setQ(e.target.value)} placeholder="Asunto o radicado" /></label>
          <label>Estado
            <select value={estado} onChange={e => setEstado(e.target.value)}>
              <option value="">Todos</option>
              {Object.entries(NOMBRES.estados).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>Tipo
            <select value={tipo} onChange={e => setTipo(e.target.value)}>
              <option value="">Todos</option>
              {Object.entries(NOMBRES.tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>
        <Aviso>{error}</Aviso>
        {datos && datos.length === 0 && <p className="vacio">No hay solicitudes con esos filtros.</p>}
        {datos && datos.length > 0 &&
          <div className="tabla-scroll"><table>
            <thead><tr><th>Radicado</th><th>Asunto</th><th>Estado</th><th>Plazo de respuesta</th><th>Radicada</th></tr></thead>
            <tbody>{datos.map(s => (
              <tr key={s.id} className="clic" onClick={() => nav(`/solicitudes/${s.id}`)}>
                <td className="num" style={{ whiteSpace: 'nowrap' }}>{s.radicado}</td>
                <td><strong>{s.asunto}</strong>
                  <div className="peq suave">{NOMBRES.tipos[s.tipo]}{s.unidad && ` · ${s.unidad}`}{usuario.rol !== 'propietario' && ` · ${s.solicitante}`}</div></td>
                <td><span className={`estado ${s.estado}`}>{NOMBRES.estados[s.estado]}</span></td>
                <td><Semaforo s={s} /><div className="peq suave">Límite {fecha(s.fecha_limite)}</div></td>
                <td style={{ whiteSpace: 'nowrap' }}>{fecha(s.fecha_radicado)}</td>
              </tr>))}
            </tbody>
          </table></div>}
      </div>
    </>
  )
}
