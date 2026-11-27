# Configuración de CI Rust para repositorios consumidores.
#
# Se invoca desde el workflow ci-rust.yml mediante `workflow_call` con
# valores por defecto. Cada repositorio puede sobreescribir cualquiera de las
# entradas `inputs` al llamar al workflow.
#
# Entradas principales (ver workflow):
#   - rust-version: toolchain fijada (default: 1.99.1, SHA256 verificada)
#   - cargo-fmt / cargo-clippy / cargo-test / cargo-build: activar/desactivar
#   - install-system-deps: apt packages si los necesita (p. ej. libssl-dev)
#   - test-args / clippy-args: argumentos adicionales
#
# Ejemplo de llamada en el repo consumidor:
#
#   jobs:
#     ci-rust:
#       uses: ruuuberth/engineering-standards/.github/workflows/ci-rust.yml@v1.0.0
#       with:
#         rust-version: "1.78.0"
#         cargo-test: true
#         cargo-fmt: true
#         install-system-deps: "libssl-dev"