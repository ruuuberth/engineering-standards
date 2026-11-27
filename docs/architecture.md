# Documentación de arquitectura del repositorio engineering-standards.

## Visión general

Este repositorio contiene workflows reutilizables, configuraciones y documentación
compartida para CI/CD y calidad de código en los repositorios de `ruuuberth`.

## Arquitectura

### Workflows reutilizables

Todos los workflows están diseñados para ser invocados mediante `workflow_call` desde
otros repositorios. La estructura es:

1. **pr-size-policy.yml** — Motor de la política de tamaño de PR (Balanced). Ejecuta
   el script `scripts/pr_size_policy.py` contra el PR actual y publica un commit status
   obligatorio. Soporta excepción `size-exempt` con autoría y justificación.

2. **ci-python.yml** — CI para proyectos Python. Usa `uv` por defecto, instalando
   dependencias, ejecutando `ruff check/format` y `pytest` (cuando haya tests).
   Cada parámetro es configurable mediante inputs.

3. **ci-rust.yml** — CI para proyectos Rust. Verifica `cargo fmt --check`,
   `cargo clippy`, `cargo test` y `cargo build`. La toolchain se instala verificando
   el SHA256 de `rustup-init` contra un valor fijado (no usa `@stable` ni `@latest`
   como referencia mutable).

4. **gitleaks.yml** — Escaneo de secretos reutilizable. Dos modos: `pr` (rango del
   PR vía `--log-opts`) y `full` (historial del repo). Siempre usa `--redact` para
   evitar exponer secretos en logs. Sube el informe como artefacto y comenta el PR.

5. **opencode-review.yml** — Integración reutilizable de OpenCode Review (OCR).
   Pulsa la acción `alibaba/open-code-review@891df1b` (v1.13.6) con los secrets y
   vars del consumidor. Gestiona comentarios sticky y modos incremental/checkpoint.

6. **release.yml** — Automatiza la creación de GitHub Releases al push de tags
   `v*.*.*`. Valida la versión contra `pyproject.toml`, crea la release (idempotente)
   y sube artefactos desde `dist/`.

### Seguridad y permisos

- Todos los workflows usan permisos mínimos (`contents: read`, `pull-requests: write`,
  `statuses: write` solo donde sea necesario).
- `pull_request_target` se usa cuando es necesario `statuses: write`; la acción
  oficial de OCR hace checkout de la rama base y obtiene los blobs del head sin
  materializar código del PR.
- Las SHAs de las actions están fijadas (no `@main` ni `@latest`) para evitar
  cambios silenciosos.
- Las versiones de herramientas (gitleaks, ruff, rust) se descargan con SHA256
  verificado.

### Consumo

Un repositorio consumidor simplemente añade un job que use el workflow:

```yaml
jobs:
  my-check:
    uses: ruuuberth/engineering-standards/.github/workflows/<workflow>.yml@v1.0.0
    with:
      <parámetros-para-tu-proyecto>
    secrets:
      <secretos-del-repositorio>
```

## Límites y extensibilidad

- **Máximo 50 workflows llamados desde un solo workflow** (límite de GitHub).
- **Máximo 10 niveles de anidamiento** de workflows reutilizables.
- Se pueden añadir nuevos perfiles (lenguajes) creando nuevos workflows en
  `.github/workflows/` y actualizando la documentación.
- Los configs viven bajo `configs/` y se referencian desde los workflows.