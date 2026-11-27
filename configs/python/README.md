# Configuración de CI Python para repositorios consumidores.
#
# Se invoca desde el workflow ci-python.yml mediante `workflow_call` con
# valores por defecto. Cada repositorio puede sobreescribir cualquiera de las
# entradas `inputs` al llamar al workflow.
#
# Entradas principales (ver workflow):
#   - python-version: versión a usar (default: 3.12)
#   - dependency-mode: uv | pip | requirements | poetry | none (default: uv)
#   - ruff-lint / ruff-format: activar/desactivar (default: true)
#   - pytest: auto | true | false (default: auto)
#   - extra-checks: script bash para comandos adicionales
#
# Ejemplo de llamada en el repo consumidor:
#
#   jobs:
#     ci-python:
#       uses: ruuuberth/engineering-standards/.github/workflows/ci-python.yml@v1.0.0
#       with:
#         python-version: "3.11"
#         dependency-mode: uv
#         ruff-lint: true
#         pytest: true
#       secrets:
#         PYPI_INDEX_TOKEN: ${{ secrets.PYPI_INDEX_TOKEN }}