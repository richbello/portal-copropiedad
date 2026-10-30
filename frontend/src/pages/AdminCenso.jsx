import { useState } from 'react'
import { descargar, fecha } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'
import { CensoUnidad } from './MiUnidad'

export default function AdminCenso() {
  const { usuario } = useSesion()
  const esAdmin = usuario.rol === 'administrador'
  const { datos: r, recargar: recargarR } = useDatos('/api/censo/resumen')
  const { datos: filas, error, recargar } = useDatos(esAdmin ? '/api/censo/unidades' : null)
  const [filtro, setFiltro] = useState('todas')
  const [torre, setTorre] = useState('')
  const [abierta, setAbierta] = useState(null)
  const { datos: mascotas, recargar: recargarM } = useDatos(esAdmin ? '/api/censo/mascotas' : null)
  const [busca, setBusca] = useState('')
  const ESPECIE = { perro: 'Perro', gato: 'Gato', otro: 'Otra' }

  const torres = [...new Set((filas || []).map(f => f.torre))]
  const visibles = (filas || []).filter(f => (!torre || f.torre === torre) &&
    (filtro === 'todas' || (filtro === 'pendientes' && !f.vigente) || (filtro === 'alertas' && f.alertas.length)))

  const porTorre = torres.map(t => {
    const fs = (filas || []).filter(f => f.torre === t)
    const suma = k => fs.reduce((s, f) => s + f[k], 0)
    return { torre: t, unidades: fs.length, personas: suma('personas'), menores: suma('menores'),
      perros: suma('perros'), gatos: suma('gatos'), otras: suma('otras_mascotas') }
  })
  const q = busca.trim().toLowerCase()
  const mascotasVisibles = (mascotas || []).filter(m => (!torre || m.torre === torre) &&
    (!q || [m.nombre, m.raza, m.color, m.unidad].some(x => (x || '').toLowerCase().includes(q))))

  return (
    <>
      <Encabezado titulo="Censo de residentes" descripcion={r && `Cada unidad debe confirmar su censo al menos cada ${r.meses_vigencia} meses.`}>
        {esAdmin && <button className="secundario" onClick={() => descargar('/api/censo/exportar.csv')}>Exportar a Excel (CSV)</button>}
      </Encabezado>
      {r && <div className="rejilla rejilla-4" style={{ marginBottom: 16 }}>
        <div className="panel indicador"><div className="suave">Censo al día</div>
          <div className="valor">{r.unidades_confirmadas} de {r.unidades}</div>
          <div className="detalle">{r.unidades - r.unidades_confirmadas} unidades por confirmar</div></div>
        <div className="panel indicador"><div className="suave">Personas</div><div className="valor">{r.personas}</div>
          <div className="detalle">{r.menores} menores de edad</div></div>
        <div className="panel indicador"><div className="suave">Mascotas</div><div className="valor">{r.perros + r.gatos + r.otras_mascotas}</div>
          <div className="detalle">{r.perros} perros, {r.gatos} gatos{r.otras_mascotas ? `, ${r.otras_mascotas} otras` : ''}</div>
          {r.alertas_mascotas > 0 && <div className="detalle" style={{ color: 'var(--rojo)' }}>{r.alertas_mascotas} con póliza o vacuna pendiente</div>}</div>
        <div className="panel indicador"><div className="suave">Vehículos</div><div className="valor">{r.carros + r.motos + r.bicicletas}</div>
          <div className="detalle">{r.carros} carros, {r.motos} motos, {r.bicicletas} bicicletas</div></div>
      </div>}
      {!esAdmin && <p className="aviso info">Por protección de datos personales, el detalle por unidad solo lo ve la administración.</p>}
      {esAdmin && filas && <section className="panel">
        <h2 style={{ marginTop: 0 }}>Personas y mascotas por torre</h2>
        <div className="tabla-scroll"><table>
          <thead><tr><th>Torre</th><th className="derecha">Unidades</th><th className="derecha">Personas</th><th className="derecha">Menores</th>
            <th className="derecha">Perros</th><th className="derecha">Gatos</th><th className="derecha">Otras</th><th className="derecha">Total mascotas</th></tr></thead>
          <tbody>{porTorre.map(t => <tr key={t.torre} className="clic" onClick={() => setTorre(t.torre)}>
            <td><strong>Torre {t.torre}</strong></td><td className="derecha">{t.unidades}</td>
            <td className="derecha">{t.personas}</td><td className="derecha">{t.menores}</td>
            <td className="derecha">{t.perros}</td><td className="derecha">{t.gatos}</td><td className="derecha">{t.otras}</td>
            <td className="derecha"><strong>{t.perros + t.gatos + t.otras}</strong></td></tr>)}
            <tr><td><strong>Total</strong></td>
              {['unidades', 'personas', 'menores', 'perros', 'gatos', 'otras'].map(k =>
                <td key={k} className="derecha"><strong>{porTorre.reduce((s, t) => s + t[k], 0)}</strong></td>)}
              <td className="derecha"><strong>{porTorre.reduce((s, t) => s + t.perros + t.gatos + t.otras, 0)}</strong></td></tr>
          </tbody>
        </table></div>
      </section>}
      {esAdmin && mascotas && <section className="panel">
        <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Mascotas registradas ({mascotasVisibles.length})</h2>
          <input placeholder="Buscar por nombre, raza o unidad" value={busca} onChange={e => setBusca(e.target.value)} style={{ maxWidth: 280 }} />
        </div>
        {mascotasVisibles.length === 0 ? <p className="suave">No hay mascotas registradas{torre ? ` en la torre ${torre}` : ''}.</p> :
          <div className="tabla-scroll"><table>
            <thead><tr><th>Unidad</th><th>Nombre</th><th>Especie</th><th>Raza / color</th><th>Vacuna antirrábica</th><th>Raza peligrosa</th></tr></thead>
            <tbody>{mascotasVisibles.map(m => <tr key={m.id} className="clic" onClick={() => setAbierta({ unidad_id: m.unidad_id, unidad: m.unidad })}>
              <td style={{ whiteSpace: 'nowrap' }}>{m.unidad}</td><td><strong>{m.nombre}</strong></td><td>{ESPECIE[m.especie] || m.especie}</td>
              <td>{[m.raza, m.color].filter(Boolean).join(' · ')}</td>
              <td style={{ color: m.vacuna_al_dia ? undefined : 'var(--rojo)' }}>{m.vacuna_vence ? (m.vacuna_al_dia ? `Al día hasta ${fecha(m.vacuna_vence)}` : `Vencida (${fecha(m.vacuna_vence)})`) : 'Sin registrar'}</td>
              <td>{m.potencialmente_peligrosa ? (m.poliza ? `Sí · póliza ${m.poliza}` : <span style={{ color: 'var(--rojo)' }}>Sí · sin póliza</span>) : 'No'}</td>
            </tr>)}</tbody>
          </table></div>}
      </section>}
      {esAdmin && <div className="panel">
        <div className="fila" style={{ marginBottom: 12 }}>
          <select value={torre} onChange={e => setTorre(e.target.value)} style={{ width: 'auto' }} aria-label="Torre">
            <option value="">Todas las torres</option>{torres.map(t => <option key={t} value={t}>Torre {t}</option>)}</select>
          <div className="pestanas" style={{ margin: 0, border: 'none' }}>
            {[['todas', 'Todas'], ['pendientes', 'Sin confirmar'], ['alertas', 'Con alertas']].map(([k, n]) =>
              <button key={k} className={filtro === k ? 'activa' : ''} onClick={() => setFiltro(k)}>{n}</button>)}
          </div>
        </div>
        <Aviso>{error}</Aviso>
        <div className="tabla-scroll"><table>
          <thead><tr><th>Unidad</th><th className="derecha">Personas</th><th className="derecha">Mascotas</th><th className="derecha">Vehículos</th><th>Confirmado</th><th>Alertas</th></tr></thead>
          <tbody>{visibles.map(f => (
            <tr key={f.unidad_id} className="clic" onClick={() => setAbierta(f)}>
              <td style={{ whiteSpace: 'nowrap' }}><strong>{f.unidad}</strong></td>
              <td className="derecha">{f.personas}{f.menores ? <span className="peq suave"> ({f.menores} men.)</span> : ''}</td>
              <td className="derecha">{f.perros + f.gatos + f.otras_mascotas || ''}</td>
              <td className="derecha">{f.carros + f.motos + f.bicicletas || ''}</td>
              <td>{f.confirmado ? <span style={{ color: f.vigente ? undefined : 'var(--ocre)' }}>{fecha(f.confirmado)}</span>
                : <span style={{ color: 'var(--rojo)' }}>Nunca</span>}</td>
              <td className="peq" style={{ color: 'var(--rojo)' }}>{f.alertas.join('. ')}</td>
            </tr>))}</tbody>
        </table></div>
        {visibles.length === 0 && <p className="vacio">No hay unidades con ese filtro.</p>}
      </div>}
      {abierta && <Modal titulo={`Censo ${abierta.unidad}`} onCerrar={() => setAbierta(null)}>
        <CensoUnidad unidadId={abierta.unidad_id} onCambio={() => { recargar(); recargarR(); recargarM() }} />
      </Modal>}
    </>
  )
}
