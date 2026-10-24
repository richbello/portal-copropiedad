import { useEffect, useState } from 'react'
import { api, fecha, NOMBRES } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

export default function AdminParqueaderos() {
  const { usuario } = useSesion()
  const esAdmin = usuario.rol === 'administrador'
  const [tipo, setTipo] = useState('carro')
  const [estado, setEstado] = useState('todos')
  const { datos, error, recargar } = useDatos('/api/parqueaderos')
  const { datos: espera, recargar: recargarEspera } = useDatos(`/api/parqueaderos/espera/${tipo}`)
  const [asignar, setAsignar] = useState(null)
  const [generar, setGenerar] = useState(false)
  const [sorteo, setSorteo] = useState(false)
  const todo = () => { recargar(); recargarEspera() }

  async function liberar(p) {
    if (!confirm(`¿Liberar ${p.codigo}, asignado a ${p.unidad}?`)) return
    await api.put(`/api/parqueaderos/${p.id}/liberar`); todo()
  }

  const res = datos?.resumen?.[tipo]
  const filas = (datos?.parqueaderos || []).filter(p => p.tipo === tipo &&
    (estado === 'todos' || (estado === 'libres' && !p.unidad_id && !p.visitantes) || (estado === 'asignados' && p.unidad_id) || (estado === 'visitantes' && p.visitantes)))

  return (
    <>
      <Encabezado titulo="Parqueaderos" descripcion="Asignación de parqueaderos de carros, motos y bicicletas. Las unidades entran a la lista de espera al registrar su vehículo en el censo.">
        {esAdmin && <>
          <button className="secundario" onClick={() => setGenerar(true)}>Crear parqueaderos</button>
          <button onClick={() => setSorteo(true)}>Hacer sorteo</button>
        </>}
      </Encabezado>
      <div className="pestanas">
        {Object.entries(NOMBRES.vehiculos).map(([k, v]) =>
          <button key={k} className={tipo === k ? 'activa' : ''} onClick={() => setTipo(k)}>{v}s</button>)}
      </div>
      <Aviso>{error}</Aviso>
      {res && <div className="rejilla rejilla-4" style={{ marginBottom: 16 }}>
        <div className="panel indicador"><div className="suave">Asignados</div><div className="valor">{res.asignados} de {res.total}</div></div>
        <div className="panel indicador"><div className="suave">Libres</div><div className="valor">{res.libres}</div></div>
        <div className="panel indicador"><div className="suave">En lista de espera</div><div className="valor">{res.en_espera}</div>
          <div className="detalle">Unidades con {NOMBRES.vehiculos[tipo].toLowerCase()} y sin parqueadero</div></div>
        <div className="panel indicador"><div className="suave">Para visitantes</div><div className="valor">{res.visitantes}</div></div>
      </div>}
      <div className="rejilla detalle-rejilla">
        <section className="panel">
          <div className="pestanas" style={{ marginTop: -6 }}>
            {[['todos', 'Todos'], ['asignados', 'Asignados'], ['libres', 'Libres'], ['visitantes', 'Visitantes']].map(([k, n]) =>
              <button key={k} className={estado === k ? 'activa' : ''} onClick={() => setEstado(k)}>{n}</button>)}
          </div>
          {filas.length === 0 ? <p className="vacio">No hay parqueaderos en esta vista.{esAdmin && datos?.parqueaderos.length === 0 && ' Créelos con el botón "Crear parqueaderos".'}</p> :
            <div className="tabla-scroll"><table>
              <thead><tr><th>Código</th><th>Asignado a</th><th>Vehículo</th><th>Desde</th><th></th></tr></thead>
              <tbody>{filas.map(p => (
                <tr key={p.id}>
                  <td><strong>{p.codigo}</strong><div className="peq suave">{p.ubicacion}</div></td>
                  <td>{p.visitantes ? <span className="suave">Visitantes</span> : p.unidad || <span className="estado radicada">Libre</span>}</td>
                  <td className="peq">{p.vehiculo ? `${p.vehiculo.placa || ''} ${p.vehiculo.marca || ''}` : ''}</td>
                  <td className="peq">{p.asignado_desde && `${fecha(p.asignado_desde)}${p.forma_asignacion === 'sorteo' ? ', por sorteo' : ''}`}</td>
                  <td className="derecha" style={{ whiteSpace: 'nowrap' }}>{esAdmin && !p.visitantes && (p.unidad_id
                    ? <button className="texto" onClick={() => liberar(p)}>Liberar</button>
                    : <button className="texto" onClick={() => setAsignar(p)}>Asignar</button>)}</td>
                </tr>))}</tbody>
            </table></div>}
        </section>
        <aside className="panel">
          <h2>Lista de espera</h2>
          <p className="peq suave" style={{ marginBottom: 8 }}>En el orden en que registraron el vehículo. El sorteo no depende de este orden.</p>
          {!espera ? null : espera.length === 0 ? <p className="suave">Nadie en espera.</p> :
            <table><tbody>{espera.map(e => <tr key={e.unidad_id}><td><strong>{e.unidad}</strong>
              <div className="peq suave">{e.vehiculo.placa} {e.vehiculo.marca}</div></td></tr>)}</tbody></table>}
        </aside>
      </div>
      {asignar && <Asignar p={asignar} onCerrar={() => setAsignar(null)} onListo={() => { setAsignar(null); todo() }} />}
      {generar && <Generar tipo={tipo} onCerrar={() => setGenerar(false)} onListo={() => { setGenerar(false); todo() }} />}
      {sorteo && <Sorteo tipo={tipo} onCerrar={() => { setSorteo(false); todo() }} />}
    </>
  )
}

function Asignar({ p, onCerrar, onListo }) {
  const { datos: unidades } = useDatos('/api/admin/unidades')
  const [unidad, setUnidad] = useState('')
  const { datos: censo } = useDatos(unidad ? `/api/censo/unidades/${unidad}` : null)
  const [vehiculo, setVehiculo] = useState('')
  const [error, setError] = useState('')
  const vehiculos = (censo?.vehiculos || []).filter(v => v.tipo === p.tipo)
  async function guardar(e) {
    e.preventDefault(); setError('')
    try { await api.put(`/api/parqueaderos/${p.id}/asignar`, { unidad_id: Number(unidad), vehiculo_id: vehiculo ? Number(vehiculo) : null }); onListo() }
    catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo={`Asignar ${p.codigo}`} onCerrar={onCerrar}>
      <form className="formulario" onSubmit={guardar}>
        <label>Unidad<select required value={unidad} onChange={e => { setUnidad(e.target.value); setVehiculo('') }}>
          <option value="">Seleccione…</option>{(unidades || []).map(u => <option key={u.id} value={u.id}>{u.etiqueta}</option>)}</select></label>
        {unidad && <label>Vehículo<select value={vehiculo} onChange={e => setVehiculo(e.target.value)}>
          <option value="">Sin especificar</option>
          {vehiculos.map(v => <option key={v.id} value={v.id}>{v.placa || 'Bicicleta'} {v.marca}</option>)}</select>
          {censo && vehiculos.length === 0 && <span className="ayuda">Esta unidad no tiene registrado ningún vehículo de este tipo en el censo.</span>}</label>}
        <Aviso>{error}</Aviso>
        <div><button>Asignar parqueadero</button></div>
      </form>
    </Modal>
  )
}

function Generar({ tipo, onCerrar, onListo }) {
  const pref = { carro: 'C', moto: 'M', bicicleta: 'B' }[tipo]
  const [f, setF] = useState({ tipo, prefijo: pref, desde: 1, cantidad: 10, ubicacion: '', visitantes: false })
  const [error, setError] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  async function guardar(e) {
    e.preventDefault(); setError('')
    try {
      await api.post('/api/parqueaderos/generar', { ...f, desde: Number(f.desde), cantidad: Number(f.cantidad), ubicacion: f.ubicacion || null })
      onListo()
    } catch (err) { setError(err.message) }
  }
  const ultimo = Number(f.desde) + Number(f.cantidad) - 1
  return (
    <Modal titulo="Crear parqueaderos" onCerrar={onCerrar}>
      <form className="formulario" onSubmit={guardar}>
        <div className="formulario-2">
          <label>Tipo<select value={f.tipo} onChange={set('tipo')}>
            {Object.entries(NOMBRES.vehiculos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Prefijo del código<input required maxLength={4} value={f.prefijo} onChange={set('prefijo')} /></label>
          <label>Desde el número<input type="number" min="1" value={f.desde} onChange={set('desde')} /></label>
          <label>Cantidad<input type="number" min="1" max="1000" value={f.cantidad} onChange={set('cantidad')} /></label>
        </div>
        <label>Ubicación<input value={f.ubicacion} onChange={set('ubicacion')} placeholder="Sótano, bicicletero torre 3…" /></label>
        <label className="casilla"><input type="checkbox" checked={f.visitantes} onChange={set('visitantes')} /> Son para visitantes (no se asignan a unidades)</label>
        <p className="peq suave">Se crearán {f.prefijo.toUpperCase()}-{String(f.desde).padStart(3, '0')} a {f.prefijo.toUpperCase()}-{String(ultimo).padStart(3, '0')}. Los códigos que ya existan se omiten.</p>
        <Aviso>{error}</Aviso>
        <div><button>Crear parqueaderos</button></div>
      </form>
    </Modal>
  )
}

function Sorteo({ tipo, onCerrar }) {
  const [t, setT] = useState(tipo)
  const [previo, setPrevio] = useState(null)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')
  const revisar = async nuevo => {
    setT(nuevo); setPrevio(null); setError('')
    try { setPrevio(await api.post('/api/parqueaderos/sorteo', { tipo: nuevo })) } catch (e) { setError(e.message) }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { revisar(tipo) }, [])
  async function hacer() {
    setError('')
    try { setResultado(await api.post('/api/parqueaderos/sorteo', { tipo: t, confirmar: true })) } catch (e) { setError(e.message) }
  }
  return (
    <Modal titulo="Sorteo de parqueaderos" onCerrar={onCerrar}>
      {!resultado ? <div className="formulario">
        <label>Tipo<select value={t} onChange={e => revisar(e.target.value)}>
          {Object.entries(NOMBRES.vehiculos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        {previo && <p className="aviso info">
          Participan <strong>{previo.participantes}</strong> unidades por <strong>{previo.cupos}</strong> parqueaderos libres.
          {previo.quedan_en_espera > 0 && ` ${previo.quedan_en_espera} seguirán en espera.`}
          {' '}Cada unidad recibe máximo un parqueadero. El resultado notifica a los ganadores y queda en la auditoría con su semilla, para que se pueda verificar.</p>}
        <Aviso>{error}</Aviso>
        <div><button disabled={!previo || !previo.participantes || !previo.cupos} onClick={hacer}>Realizar sorteo</button></div>
      </div> : <div className="pila">
        <p className="aviso ok">Sorteo realizado. Semilla de verificación: <strong className="num">{resultado.semilla}</strong></p>
        <table><thead><tr><th>Unidad</th><th>Parqueadero</th></tr></thead>
          <tbody>{resultado.asignados.map(a => <tr key={a.parqueadero}><td>{a.unidad}</td><td><strong>{a.parqueadero}</strong></td></tr>)}</tbody></table>
        {resultado.sin_cupo.length > 0 && <p className="peq">Siguen en espera: {resultado.sin_cupo.join(', ')}</p>}
        <div><button onClick={onCerrar}>Cerrar</button></div>
      </div>}
    </Modal>
  )
}
