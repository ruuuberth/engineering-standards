# Documentación de la política de tamaño de PR.

## Política Balanced

Los límites acordados son:
- **1–100 líneas modificadas** → PASS. El PR puede fusionarse.
- **101–150 líneas modificadas** → PASS + WARNING. El PR puede fusionarse pero
  avisa al revisor.
- **151 o más líneas modificadas** → FAIL. El merge está bloqueado por el status
  check obligatorio.

### Cálculo de líneas modificadas

Se cuentan `adiciones + eliminaciones` por cada fichero. No se excluyen tests,
documentación ni configuraciones normales por defecto.

### Exclusiones (por defecto)

- `**/*.lock`
- `**/generated/**`
- `**/dist/**`
- `**/build/**`
- `**/*.min.js`
- `**/*.min.css`

### Excepción `size-exempt`

Solo los mantenedores (permiso `write`, `maintain` o `admin`) pueden aplicar
esta etiqueta al PR. Requisitos:

1. La etiqueta `size-exempt` debe estar en el PR.
2. Debe haber un bloque `<!-- size-exemption --> motivo <!-- /size-exemption -->`
   o una línea `Size exemption: motivo` en el cuerpo del PR.
3. La justificación debe tener al menos 15 caracteres no vacíos.
4. Quien la aplica debe tener permiso de escritura sobre el repositorio.

Si se retira la etiqueta `size-exempt`, el límite vuelve a aplicarse automáticamente
al siguiente evento (reabrir, actualizar, cambiar etiquetas).

### Límites por defecto

- PASS: ≤ 100 líneas modificadas (excluyendo los patrones de exclusión).
- WARN: 101–150 líneas modificadas.
- FAIL: > 150 líneas modificadas.