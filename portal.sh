#!/usr/bin/env bash
# Gestión del Portal de Propietarios desde la terminal.
# Uso: ./portal.sh <comando>
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK="$RAIZ/backend"
FRONT="$RAIZ/frontend"
VENV="$BACK/.venv"
PY="$VENV/bin/python"
PUERTO="${PUERTO:-8000}"

verde() { printf '\033[32m%s\033[0m\n' "$*"; }
rojo()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }

requiere() {
  command -v "$1" >/dev/null 2>&1 || { rojo "Falta '$1'. Instálelo o use un Codespace de GitHub (ya lo trae)."; exit 1; }
}

instalar() {
  requiere python3; requiere node; requiere npm
  verde "1/3 Entorno de Python"
  [ -d "$VENV" ] || python3 -m venv "$VENV"
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r "$BACK/requirements.txt"
  verde "2/3 Dependencias del frontend"
  (cd "$FRONT" && npm install --silent --no-audit --no-fund)
  verde "3/3 Compilando el frontend"
  (cd "$FRONT" && npm run build --silent)
  verde "Instalación completa."
}

demo() {
  verde "Creando base de datos con datos de demostración (borra la actual)…"
  (cd "$BACK" && "$PY" seed.py)
}

probar() {
  (cd "$BACK" && "$PY" -m pytest -q)
}

compilar() {
  (cd "$FRONT" && npm run build --silent) && verde "Frontend compilado en frontend/dist"
}

iniciar() {
  [ -d "$FRONT/dist" ] || compilar
  [ -f "$BACK/copropiedad.db" ] || [ -n "${DATABASE_URL:-}" ] || demo
  verde "Portal en http://localhost:$PUERTO   (Ctrl+C para detener)"
  [ -n "${CODESPACE_NAME:-}" ] && verde "En Codespaces: https://${CODESPACE_NAME}-${PUERTO}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  cd "$BACK" && exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PUERTO"
}

desarrollo() {
  verde "Backend en :$PUERTO con recarga automática y frontend Vite en :5173"
  (cd "$BACK" && "$PY" -m uvicorn app.main:app --reload --port "$PUERTO") &
  PID=$!
  trap 'kill $PID 2>/dev/null' EXIT
  cd "$FRONT" && npm run dev -- --host
}

admin() {
  [ $# -ge 2 ] || { rojo 'Uso: ./portal.sh admin correo@dominio.co "Nombre Completo"'; exit 1; }
  (cd "$BACK" && "$PY" crear_admin.py "$1" "$2")
}

respaldo() {
  local destino="$RAIZ/respaldos"; mkdir -p "$destino"
  local f="$destino/respaldo_$(date +%Y%m%d_%H%M%S).tar.gz"
  tar -czf "$f" -C "$BACK" $( [ -f "$BACK/copropiedad.db" ] && echo copropiedad.db ) uploads
  verde "Respaldo creado: $f"
}

api() {
  # Llama la API desde la terminal: ./portal.sh api correo clave GET /api/admin/dashboard
  [ $# -ge 4 ] || { rojo 'Uso: ./portal.sh api <correo> <clave> <GET|POST> <ruta> [json]'; exit 1; }
  local token
  token=$(curl -s -X POST "http://localhost:$PUERTO/api/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" | "$PY" -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))')
  [ -n "$token" ] || { rojo "No se pudo ingresar con ese correo y clave."; exit 1; }
  curl -s -X "$3" "http://localhost:$PUERTO$4" -H "Authorization: Bearer $token" \
    ${5:+-H 'Content-Type: application/json' -d "$5"} | "$PY" -m json.tool --no-ensure-ascii
}

ayuda() {
  cat <<'EOF'
Portal de Propietarios — comandos

  ./portal.sh instalar      Instala Python, dependencias y compila el frontend
  ./portal.sh demo          Crea la base con datos de prueba (clave de todos: Demo2026*)
  ./portal.sh probar        Ejecuta las 15 pruebas automáticas
  ./portal.sh iniciar       Arranca el portal completo en el puerto 8000
  ./portal.sh desarrollo    Backend con recarga + frontend Vite (para modificar código)
  ./portal.sh compilar      Vuelve a compilar el frontend
  ./portal.sh admin <correo> "<nombre>"   Crea el primer administrador real
  ./portal.sh respaldo      Copia la base de datos y los archivos subidos
  ./portal.sh api <correo> <clave> <GET|POST> <ruta> [json]
                            Consulta la API sin abrir el navegador. Ej.:
                            ./portal.sh api admin@conjunto.co 'Demo2026*' GET /api/admin/dashboard
EOF
}

cmd="${1:-ayuda}"; shift || true
case "$cmd" in
  instalar|demo|probar|compilar|iniciar|desarrollo|admin|respaldo|api|ayuda) "$cmd" "$@" ;;
  *) rojo "Comando desconocido: $cmd"; ayuda; exit 1 ;;
esac
