#!/usr/bin/env bash
# Corre la suite de tests dentro de un container con todas las deps disponibles.
#
# Uso:
#   ./scripts/run_tests.sh                  # corre los tests nuevos (sprint actual)
#   ./scripts/run_tests.sh --all            # también incluye tests viejos (45 fallan pre-sprint)
#   ./scripts/run_tests.sh tests/test_jsonlogic.py    # un archivo específico
#   ./scripts/run_tests.sh -k jsonlogic     # filtro pytest
#
# Requiere: docker compose stack levantado (para los tests de integración).
# Los tests unit no necesitan los services up — pero usamos el container `plans`
# como entorno de ejecución porque ya tiene shared/ + services/ importables.

set -euo pipefail

cd "$(dirname "$0")/.."

CONTAINER="xtask-plans"
TESTS_DIR="tests"

# 1. Verificar que el container está vivo
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container ${CONTAINER} no está corriendo."
    echo "   Levantá el stack: docker compose up -d"
    exit 1
fi

# 2. Copiar los tests más recientes del host al container
#    (porque la imagen se buildea sin tests/ típicamente)
echo "→ syncing tests/ to ${CONTAINER}..."
docker cp tests/. "${CONTAINER}:/app/tests/"

# 3. Asegurar que pytest esté instalado (se persiste en el FS del container hasta restart)
if ! docker exec "${CONTAINER}" python -c "import pytest" 2>/dev/null; then
    echo "→ installing pytest in container..."
    docker exec "${CONTAINER}" pip install --quiet pytest==9.1.0 pytest-asyncio==1.4.0
fi

# 4. Decidir scope
# Tests nuevos del sprint actual — pasan limpios.
NEW_TESTS=(
    "tests/test_jsonlogic.py"
    "tests/test_okr_math.py"
    "tests/test_contracts_state_machine.py"
    "tests/test_integration_docgen.py"
    "tests/test_gateway_security.py"
)

if [[ "${1:-}" == "--all" ]]; then
    shift
    echo "→ running ALL tests (incluye los pre-sprint con bugs conocidos)..."
    docker exec "${CONTAINER}" bash -c "cd /app && python -m pytest ${TESTS_DIR} -v $*"
elif [[ $# -gt 0 ]] && [[ "${1}" != -* ]]; then
    # Pasaron un archivo o ruta concreta
    docker exec "${CONTAINER}" bash -c "cd /app && python -m pytest $*"
else
    # Default: solo los nuevos
    echo "→ running new test suite (sprint actual)..."
    docker exec "${CONTAINER}" bash -c "cd /app && python -m pytest ${NEW_TESTS[*]} -v $*"
fi
