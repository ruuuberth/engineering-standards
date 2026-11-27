# Guía de adopción: cómo incorporar los estándares centralizados a un repositorio consumidor.

## Paso 1: Añadir el workflow reutilizable

En `.github/workflows/<tu-check>.yml`, añade un job que use el workflow central:

```yaml
jobs:
  pr-size:
    uses: ruuuberth/engineering-standards/.github/workflows/pr-size-policy.yml@v1.0.0
    with:
      exempt-label: size-exempt
      min-permission: write
```

## Paso 2: Configurar permisos

Asegúrate de que el workflow tiene `pull-requests: write` y `statuses: write` en su sección `permissions:`, o define esos permisos en el repo raíz (esto es necesario para publicar el commit status que bloquea el merge).

## Paso 3: Añadir los secrets y variables necesarios

Los workflows reutilizables usan `secrets` y `vars` para comunicar credenciales.
Lee cada workflow y añade los secrets/ variables que soliciten en
`Settings → Secrets and variables → Actions` de tu repositorio.

## Paso 4: Personalizar los inputs opcionales

Cada workflow tiene inputs con valores por defecto. Sobrescribe los que necesites:

- `max-pass-lines`: cambia el umbral PASS (default 100).
- `max-warn-lines`: cambia el umbral WARN (default 150).
- `python-version`, `rust-version`, `exempt-label`, etc.

## Paso 5: Ejecutar y ver el resultado

Al abrir o actualizar un PR, GitHub ejecutará el workflow. Verifica:
- El commit status "PR Size Policy" (éxito, aviso o fallo).
- El comentario en el PR con el desglose.
- Si aplicaste `size-exempt`, el check pasará si la justificación está completa.

## Paso 6: Iterar

Si los límites no se ajustan a tu equipo, modifica los valores de `max-pass-lines` y `max-warn-lines` en el input del workflow, o ajusta la política en `scripts/pr_size_policy.py` y publica una nueva versión del repo central.

---
> **Nota importante:** los workflows usan `pull_request_target` para tener acceso a `statuses: write`. No los ejecutes con `pull_request` en PRs de forks a menos que sepas lo que haces.