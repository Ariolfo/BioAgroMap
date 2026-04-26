#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEMGREP_BIN="$ROOT_DIR/.venv-semgrep/bin/semgrep"

usage() {
  cat <<'EOF'
Uso:
  scripts/semgrep.sh [backend|frontend|all]

Opciones:
  backend   Escanea solo backend (OWASP + Python)
  frontend  Escanea solo frontend (OWASP + JavaScript)
  all       Escanea backend y frontend (OWASP + Python + JavaScript)

Si no se pasa argumento, usa: all
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

TARGET="${1:-all}"

if [[ ! -x "$SEMGREP_BIN" ]]; then
  echo "Error: no se encontró semgrep aislado en $SEMGREP_BIN"
  echo "Instálalo primero con:"
  echo "  python3 -m venv .venv-semgrep"
  echo "  ./.venv-semgrep/bin/pip install semgrep"
  exit 1
fi

cd "$ROOT_DIR"

case "$TARGET" in
  backend)
    "$SEMGREP_BIN" scan --config p/owasp-top-ten --config p/python backend
    ;;
  frontend)
    "$SEMGREP_BIN" scan --config p/owasp-top-ten --config p/javascript frontend
    ;;
  all)
    "$SEMGREP_BIN" scan --config p/owasp-top-ten --config p/python --config p/javascript backend frontend
    ;;
  *)
    echo "Error: opción inválida '$TARGET'"
    usage
    exit 2
    ;;
esac
