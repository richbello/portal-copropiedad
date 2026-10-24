import { useState } from 'react'
import { api, NOMBRES } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

export default function AdminUsuarios() {
  const { usuario } = useSesion()
  const [q, setQ] = useState('')
  const { datos, error, recargar } = useDatos(`/api/admin/usuarios${q.length > 1 ? `?q=${encodeURIComponent(q)}` : ''}`)
  const { datos: unidades } = useDatos('/api/admin/unidades')
  const [crear, setCrear] = useState(false)
  const [clave, setClave] = useState(null)
  const [editar, setEditar] = useState(null)
  const esAdmin = usuario.rol === 'administrador'

  async function restablecer(u) {
    if (!confirm(`¿Generar una nueva clave temporal para ${u.nombre}?`)) return
    const r = await api.post(`/api/admin/usuarios/${u.id}/restablecer-clave`)
    setClave({ nombre: u.nombre, email: u.email, clave: r.clave_temporal })
  }
  async function alternarActivo(u) {
    await api.patch(`/api/admin/usuarios/${u.id}`, { activo: !u.activo }); recargar()
  }

  return (
    <>
      <Encabezado titulo="Propietarios y usuarios" descripcion="Cree usuarios, asígneles unidades y entregue la clave temporal. En el primer ingreso deberán cambiarla y autorizar el tratamiento de datos.">
        {esAdmin && <button onClick={() => setCrear(true)}>Crear usuario</button>}
      </Encabezado>
      <div className="panel">
        <input placeholder="Buscar por nombre o correo" value={q} onChange={e => setQ(e.target.value)} style={{ maxWidth: 360, marginBottom: 12 }} />
        <Aviso>{error}</Aviso>
        <div className="tabla-scroll"><table>
          <thead><tr><th>Nombre</th><th>Rol</th><th>Unidades</th><th>Datos</th><th></th></tr></thead>
          <tbody>{(datos || []).map(u => (
            <tr key={u.id} style={{ opacity: u.activo ? 1 : 0.5 }}>
              <td><strong>{u.nombre}</strong><div className="peq suave">{u.email}{u.telefono && `, ${u.telefono}`}</div></td>
              <td>{NOMBRES.roles[u.rol]}{!u.activo && <div className="peq" style={{ color: 'var(--rojo)' }}>Inactivo</div>}</td>
              <td className="peq">{u.unidades.map(x => <div key={x.id}>{x.etiqueta}{x.relacion !== 'propietario' && ` (${x.relacion})`}</div>)}</td>
              <td className="peq">{u.acepto_tratamiento_datos ? 'Autorizó' : <span style={{ color: 'var(--ocre)' }}>Pendiente</span>}</td>
              <td className="derecha" style={{ whiteSpace: 'nowrap' }}>{esAdmin && u.id !== usuario.id && <>
                <button className="texto" onClick={() => setEditar(u)}>Unidades</button>
                <button className="texto" onClick={() => restablecer(u)}>Nueva clave</button>
                <button className="texto" onClick={() => alternarActivo(u)}>{u.activo ? 'Desactivar' : 'Activar'}</button>
              </>}</td>
            </tr>))}
          </tbody>
        </table></div>
      </div>
      {crear && <CrearUsuario unidades={unidades} onCerrar={() => setCrear(false)}
        onCreado={r => { setCrear(false); setClave({ nombre: r.usuario.nombre, email: r.usuario.email, clave: r.clave_temporal }); recargar() }} />}
      {clave && <Modal titulo="Clave temporal" onCerrar={() => setClave(null)}>
        <div className="pila">
          <p>Entregue esta clave a <strong>{clave.nombre}</strong> ({clave.email}). Solo se muestra una vez; deberá cambiarla en su primer ingreso.</p>
          <div className="clave-temporal">{clave.clave}</div>
          <button onClick={() => navigator.clipboard?.writeText(clave.clave)}>Copiar clave</button>
        </div>
      </Modal>}
      {editar && <AsignarUnidades u={editar} unidades={unidades} onCerrar={() => { setEditar(null); recargar() }} />}
    </>
  )
}

function CrearUsuario({ unidades, onCerrar, onCreado }) {
  const [f, setF] = useState({ nombre: '', email: '', rol: 'propietario', documento: '', telefono: '', unidad_id: '', relacion: 'propietario' })
  const [error, setError] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.value })
  async function enviar(e) {
    e.preventDefault()
    try { onCreado(await api.post('/api/admin/usuarios', { ...f, unidad_id: f.unidad_id ? Number(f.unidad_id) : null })) }
    catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo="Crear usuario" onCerrar={onCerrar}>
      <form className="formulario" onSubmit={enviar}>
        <label>Nombre completo<input required value={f.nombre} onChange={set('nombre')} /></label>
        <div className="formulario-2">
          <label>Correo<input type="email" required value={f.email} onChange={set('email')} /></label>
          <label>Rol<select value={f.rol} onChange={set('rol')}>{Object.entries(NOMBRES.roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Documento<input value={f.documento} onChange={set('documento')} /></label>
          <label>Celular<input value={f.telefono} onChange={set('telefono')} /></label>
          <label>Unidad<select value={f.unidad_id} onChange={set('unidad_id')}>
            <option value="">Ninguna</option>{(unidades || []).map(u => <option key={u.id} value={u.id}>{u.etiqueta}</option>)}</select></label>
          <label>Relación<select value={f.relacion} onChange={set('relacion')}><option value="propietario">Propietario</option><option value="residente">Residente o arrendatario</option></select></label>
        </div>
        <Aviso>{error}</Aviso>
        <div><button>Crear y generar clave</button></div>
      </form>
    </Modal>
  )
}

function AsignarUnidades({ u, unidades, onCerrar }) {
  const [actual, setActual] = useState(u)
  const [unidad, setUnidad] = useState('')
  const [relacion, setRelacion] = useState('propietario')
  const [error, setError] = useState('')
  async function asignar(e) {
    e.preventDefault(); setError('')
    try { setActual(await api.post(`/api/admin/usuarios/${u.id}/unidades`, { unidad_id: Number(unidad), relacion })) } catch (err) { setError(err.message) }
  }
  async function quitar(uid) {
    await api.del(`/api/admin/usuarios/${u.id}/unidades/${uid}`)
    setActual({ ...actual, unidades: actual.unidades.filter(x => x.id !== uid) })
  }
  return (
    <Modal titulo={`Unidades de ${u.nombre}`} onCerrar={onCerrar}>
      <div className="pila">
        {actual.unidades.length === 0 && <p className="suave">Sin unidades asignadas.</p>}
        {actual.unidades.map(x => <div key={x.id} className="fila" style={{ justifyContent: 'space-between' }}>
          <span>{x.etiqueta} ({x.relacion})</span><button className="texto" onClick={() => quitar(x.id)}>Quitar</button></div>)}
        <form className="fila" onSubmit={asignar}>
          <select required value={unidad} onChange={e => setUnidad(e.target.value)} style={{ flex: 1 }}>
            <option value="">Agregar unidad…</option>{(unidades || []).map(x => <option key={x.id} value={x.id}>{x.etiqueta}</option>)}</select>
          <select value={relacion} onChange={e => setRelacion(e.target.value)} style={{ width: 'auto' }}>
            <option value="propietario">Propietario</option><option value="residente">Residente</option></select>
          <button>Asignar</button>
        </form>
        <Aviso>{error}</Aviso>
      </div>
    </Modal>
  )
}
