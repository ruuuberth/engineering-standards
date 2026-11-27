# Documentación de OpenCode Review en este repositorio central.

## Integración reutilizable

Este workflow (`opencode-review.yml`) invoca la acción oficial
`alibaba/open-code-review@891df1b` (v1.13.6) para proporcionar revisiones de código
basadas en LLM en los PRs.

### Configuración requerida

El consumidor debe definir estos `secrets` en `Settings → Secrets and variables → Actions`:

- `OCR_LLM_URL`: Endpoint del proveedor LLM (OpenAI-compatible, Anthropic, etc.).
- `OCR_LLM_AUTH_TOKEN`: Token de autenticación (la acción lo mapea a `OCR_LLM_TOKEN`).

Y estas `variables` de repositorio (en `Settings → Variables de repositorio`):

- `OCR_LLM_MODEL`: Nombre del modelo (p. ej. `claude-3-5-sonnet-20240620`).
- `OCR_LLM_USE_ANTHROPIC`: `'true'` para Anthropic, `'false'` para OpenAI-compatible.

### Cómo funciona

1. El workflow se dispara en `pull_request_target` (abierto, sincronizado, reopened)
   o cuando un comentario comienza con `/open-code-review` o `@open-code-review`
   (solo por usuarios con `author_association: MEMBER|OWNER|COLLABORATOR`).

2. Resuelve `base_ref` y `head_sha` (para `issue_comment`events, consulta la PR
   vía `pulls.get`).

3. Ejecuta `ocr review` con los parámetros pasados como inputs.

4. Publica comentarios inline y un comentario resumen sticky.

5. Soporta modos `sticky` (actualizar un solo comentario) e `incremental`
   (solo comentarios nuevos).

### Seguridad

- Nunca se ejecuta código del PR bajo `pull_request_target`; la acción OCR hace
  checkout de la rama base y accede a los blobs del head como objetos git.
- Los secrets nunca se imprimen en los logs (la acción los inyecta como variables
  de entorno).
- `route_severity_below` y `route_channels` controlan qué hallazgos van al resumen
  y cuáles permanecen inline.