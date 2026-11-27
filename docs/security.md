# Documentación de seguridad.

## Principios generales

- **Mínimos privilegios**: cada workflow declara solo los permisos que necesita
  (`contents: read`, `pull-requests: write`, `statuses: write`). Nunca se usan
  permisos `write` globales si no son necesarios.
- **Sin código no confiable bajo `pull_request_target`**: los workflows que requieren
  `statuses: write` usan `pull_request_target` para acceder al repo BASE, no al head
  del PR. La acción oficial de OpenCode Review hace checkout de la rama base y obtiene
  los blobs del head como objetos git, sin materializar código del PR.
- **SHA fija, no mutable**: todas las acciones (`actions/checkout`, `actions/setup-*`,
  `gitleaks/gitleaks-action`, `alibaba/open-code-review`) están pinzadas a commit
  SHA completos verificados. No se usa `@main`, `@latest` ni referencias semánticas
  en dependencias críticas de workflows consumidores.
- **Secretos fuera de logs**: el workflow de gitleaks usa siempre `--redact` (valor
  por defecto 100%) y sube el informe como artefacto, nunca imprime los valores
  reales. El motor de política de tamaño de PR nunca pasa el cuerpo del PR como
  argumento de shell (usa `execFileSync` con array).
- **No exponer secretos en logs**: los outputs de `ocr review` y `gitleaks dir` ya
  vienen redactados por `--redact`. El paso de fallo en gitleaks muestra solo el
  conteo y las reglas afectadas, no los valores de los secretos.

## Gitleaks

- Configuración centralizada en `configs/gitleaks/gitleaks.toml`.
- Allowlists para checksums y tokens conocidos de PSS (para evitar falsos positivos).
- Excepciones SOLO mediante allowlists; `continue-on-error` nunca debe usarse en
  producción.
- El binario se descarga con SHA256 verificado (versión fija 8.30.1).

## OpenCode Review

- Se requiere configurar un proveedor LLM antes de que el workflow funcione.
- Los secrets `OCR_LLM_URL` y `OCR_LLM_AUTH_TOKEN` nunca aparecen en los logs
  de la acción (la acción los mapea internamente).
- `llm_use_anthropic` con string vacío elige protocolo Anthropic; para endpoints
  openai-compatibles pasar `'false'` explícito.
- No se debe pasar `--audience human` (streaming progress que contamina output).
- Siempre usar `--audience agent`.

## Release CI

- Los tags deben tener formato `vX.Y.Z` (con prefijo `v` opcional configurables).
- La versión del tag debe coincidir con la versión de `pyproject.toml` (validación
  rápida antes de crear la release).
- `gh release create` es idempotente: si la release ya existe, se omite la creación.
- Los artefactos se suben desde `dist/` o la raíz; si no hay artefactos, se emite
  un warning y se continúa (no falla el job).
- No se publican paquetes en registros externos (PyPI, crates.io, etc.) desde
  este workflow. Eso se hace en flujos de trabajo separados.