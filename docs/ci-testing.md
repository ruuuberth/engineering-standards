# Documentación de pruebas y validación de workflows.

## Pruebas unitarias

La política de tamaño de PR tiene un conjunto de pruebas unitarias completas en
`tests/test_pr_size_policy.py` (51 tests, todas pasan). Cubre:

- Límites de 0, 1, 100 (PASS), 101, 150 (WARN), 151+ (FAIL).
- Exclusiones por defecto y personalizadas.
- Excepción `size-exempt` con y sin justificación, con autoría y sin ella.
- Ficheros truncados por el límite de 3000 ficheros de GitHub.
- Comportamiento CLI real (`python3 -m unittest tests.test_pr_size_policy`).

## Validación de YAML

Todos los workflows `.github/workflows/*.yml` pasan el linter `actionlint` (versión 1.7.12).
Se usan SHAs completas para pinzar actions, evitando referencias mutables como `@main`
o `@latest`.

## Flujo devalidación continua

1. Todo push a `main` o etiqueta `v*.*.*` dispara los workflows correspondientes.
2. Los workflows reutilizables validan sintaxis y checksums antes de ejecutarse.
3. Los commits deben pasar el status check "PR Size Policy" antes de poder hacer merge
   (configurable en branch protection).
4. Los artefactualos y releases se suben tras validar la versión contra `pyproject.toml`.

## Límites conocidos

- El límite de 3000 ficheros por PR de GitHub: si el diff tiene más, el workflow
  marcará `truncated: true` y fallará en lugar de aprobar a ciegas.
- Los permisos de colaborador se compruegan sobre el repo consumidor, no sobre el
  repo central (el workflow lee `github.repository` del contexto).
- La excepción `size-exempt` requiere que el actor tenga permiso `write`/`maintain`/
  `admin` en el repo consumidor; esto se comprueba vía `github.rest.repos.getCollaboratorPermissionLevel`.