# Documentación de releases.

## Workflow reutilizable `release.yml`

Este workflow se desencadena al push de un tag que coincida con el patrón
`v*.*.*` sobre la rama `main`. Cumple los siguientes requisitos:

1. **Activación mediante tags de versión**: `push: { tags: [\"v*.*.*\"] }`.

2. **Validación de versión y formato del tag**: antes de crear la release, se
   comprueba que el nombre del tag (quitar prefijo `v`) tenga el formato semántico
   mayor.minor.patch. Si no pasa la validación, el job falla rápido.

3. **Ejecución de CI antes de publicar**: el consumidor puede configurar un
   `ci-before-publish` input que ejecute un workflow de CI concreto antes de
   crear la release. Por defecto, se asume que CI pasó antes del push del tag.

4. **Generación de artefactos**: el workflow sube los ficheros que encuentre en
   `dist/` o en la raíz (filtrando rutas habituales como `.git`, `.yml`, `.md`,
   etc.). Si no encuentra nada, emite warning y continúa.

5. **Creación de GitHub Releases**: usa `gh release create --generate-notes` para
   rellenar el cuerpo de la release con los commits desde el tag anterior. Es
   idempotente: si la release ya existe, se omite su creación.

6. **Soporte para binarios multiplataforma**: los binarios compilados para
   diferentes plataformas pueden subirse como assets. El workflow no asume una
   plataforma concreta; sube todo lo que encuentre en `dist/` que no sea un
   patrón excluido.

7. **Extensibilidad para publicar paquetes Python y Rust**: los inputs
   `python-version` y la capacidad de ejecutar CI antes de publicar permiten
   al consumidor añadir pasos para `twine upload` o `cargo publish`, pero el
   workflow base **no** publica ni usa credenciales de registros externos. Eso
   debe hacerse en workflows separados, con sus propios secrets.

### Flujo típico

1. Desarrollador etiqueta: `git tag v1.2.3 && git push origin v1.2.3`
2. GitHub dispara `release.yml`
3. Valida que `v1.2.3` coincide con `pyproject.toml `[tool.version]`
4. Ejecuta CI opcional (si se configuró)
5. Crea/actualiza la release `v1.2.3` con `gh release create`
6. Sube artefactos desde `dist/`
7. Comenta en el PR o repositorio con el enlace a la release