# Documentación de Dependabot.

Este repositorio incluye configuraciones de referencia para Dependabot, que el
consumidor puede activar copiando el contenido a su propio `.github/dependabot.yml`.

## Formatos compatibles

- **GitHub Actions**: actualizaciones de acciones y workflows.
- **Python**: actualizaciones de dependencias (`pip`, `poetry`, `pipenv`).
- **Rust / Cargo**: actualizaciones de versiones de Rust y dependencias `Cargo.toml`.
- **Docker**: actualizaciones de imágenes base y capas.

## Configuración recomendada (copiar al repo consumidor)

```yaml
version: 2
updates:
  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    allow:
      - pull-requests
    ignore:
      - dependency-name: "*"
        update-types: ["version-update:semver-patch"]
    # Empaquetado grupado para reducir número de PR
    # (experimental a 2026; verificar en docs de GitHub)
    # commit-message:
    #   include: "scope"
    #   prefix: "deps"

  # Python
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    allow:
      - pull-requests
    # Versiones mayor.minor se marcan como minor (no parche automático)
    # directory: "/"

  # Rust
  - package-ecosystem: "cargo"
    directory: "/"
    schedule:
      interval: "weekly"
    allow:
      - pull-requests

  # Docker
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
    allow:
      - pull-requests
```

## Consejos

- **Actualizaciones agrupadas**: GitHub tiende a agrupar múltiples actualizaciones
  en un solo PR cuando el calendario coincide, lo que reduce el ruido.
- **Excluir dependencias inestables**: usa el campo `ignore` para saltarte paquetes
  que rompen builds en tu proyecto.
- **Revisar antes de fusionar**: las PRs de Dependabot deben revisarse como cualquier
  otra, sobre todo en la primera vez que se habilita para un ecosistema nuevo.