#!/usr/bin/env python3
"""Motor de la política de tamaño de PR (Balanced).

Este módulo NO habla con la API de GitHub. Recibe datos ya resueltos (lista de
ficheros del PR, cuerpo del PR, etiquetas, actor que aplicó la etiqueta y su
permiso en el repo) y devuelve un veredicto determinista. Esa separación es
deliberada: la lógica con límites es lo único que necesita pruebas exhaustivas,
y al ser pura se puede probar sin red ni credenciales.

Contrato de salida (JSON):

    {
      "verdict": "pass" | "warn" | "fail",
      "status_state": "success" | "failure",
      "total_changed": int,
      "additions": int,
      "deletions": int,
      "files_considered": int,
      "files_excluded": int,
      "excluded_paths": [...],
      "largest_files": [{"filename": ..., "changed": ...}, ...],
      "exemption": {"requested": bool, "granted": bool, "reason": str},
      "limits": {"max_pass": int, "max_warn": int},
      "truncated": bool,
      "summary": str
    }

Uso:
    pr_size_policy.py --files files.jsonl --body body.md --labels a,b \
        --exempt-label size-exempt --actor-permission write --json-out out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Exclusiones acordadas en la política Balanced. No se excluyen tests,
# documentación ni configuraciones normales: solo artefactos generados,
# dependencias bloqueadas y minificados.
DEFAULT_EXCLUDES = (
    "**/*.lock",
    "**/generated/**",
    "**/dist/**",
    "**/build/**",
    "**/*.min.js",
    "**/*.min.css",
)

# GitHub devuelve como máximo 3000 ficheros en el diff de un PR. Si alcanzamos
# ese techo el recuento es una cota inferior y no se puede decidir: se marca
# `truncated` y el veredicto es FAIL para no aprobar a ciegas.
GITHUB_MAX_PR_FILES = 3000

# Permisos de colaborador, ordenados de menor a mayor. `maintain` solo existe
# en repos de organización; `write` es el rol de mantenedor en repos personales.
PERMISSION_RANK = {
    "none": 0,
    "unknown": 0,
    "read": 1,
    "triage": 2,
    "write": 3,
    "maintain": 4,
    "admin": 5,
}

# `author_association` del actor que aplicó la etiqueta. Las tres primeras
# relaciones implican pertenencia al equipo con acceso de escritura al repo.
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
ASSOCIATION_RANK = {
    "NONE": 0,
    "CONTRIBUTOR": 1,
    "FIRST_TIMER": 1,
    "FIRST_TIME_CONTRIBUTOR": 1,
    "MANNEQUIN": 0,
}
ALLOWED_EXEMPT_PERMISSIONS = frozenset({"admin", "maintain", "write"})
DEFAULT_MIN_PERMISSION = "write"


def glob_to_regex(pattern: str) -> str:
    """Traduce un glob estilo GitHub a regex anclada.

    Semántica:
      *   -> cualquier cosa salvo '/'
      ?   -> un carácter salvo '/'
      **  -> cualquier cosa incluido '/'
      **/ -> cero o más segmentos de ruta (así '**/generated/**' casa también
             con 'generated/x', no solo con 'src/generated/x')
    """
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "*":
            j = i
            while j < n and pattern[j] == "*":
                j += 1
            stars = j - i
            if stars >= 2:
                if j < n and pattern[j] == "/":
                    out.append("(?:.*/)?")
                    i = j + 1
                else:
                    out.append(".*")
                    i = j
            else:
                # Un solo '*' no cruza directorios.
                out.append("[^/]*")
                i = j
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            j = i + 1
            if j < n and pattern[j] in "!^":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:  # corchete sin cerrar: literal
                out.append(r"\[")
                i += 1
            else:
                body = pattern[i + 1 : j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                i = j + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return "".join(out)


class PathFilter:
    """Conjunto de patrones de exclusión compilados una sola vez."""

    def __init__(self, patterns):
        self.patterns = [p.strip() for p in patterns if p and p.strip()]
        self._compiled = [
            (p, re.compile(glob_to_regex(p), re.DOTALL)) for p in self.patterns
        ]

    def matches(self, path: str) -> bool:
        return any(rx.fullmatch(path) for _, rx in self._compiled)

    def matching_pattern(self, path: str) -> str | None:
        for pat, rx in self._compiled:
            if rx.fullmatch(path):
                return pat
        return None


def _as_int(value) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def load_files(paths) -> list[dict]:
    """Normaliza la lista de ficheros del PR.

    Acepta una lista de dicts (uso en tests) o líneas JSONL con las claves
    filename/additions/deletions tal y como las emite `gh api --jq`.
    """
    files: list[dict] = []
    for item in paths:
        if isinstance(item, dict):
            files.append(item)
            continue
        for line in Path(item).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            files.append(json.loads(line))
    normalised = []
    for f in files:
        name = (f.get("filename") or f.get("path") or "").strip()
        if not name:
            continue
        normalised.append(
            {
                "filename": name,
                "additions": _as_int(f.get("additions")),
                "deletions": _as_int(f.get("deletions")),
            }
        )
    return normalised


def count_changed(files, excludes=DEFAULT_EXCLUDES, max_files=GITHUB_MAX_PR_FILES):
    """Suma adiciones + eliminaciones ignorando rutas excluidas."""
    flt = PathFilter(excludes)
    additions = deletions = considered = 0
    excluded: list[str] = []
    for f in files:
        name = f["filename"]
        if flt.matches(name):
            excluded.append(name)
            continue
        considered += 1
        additions += max(int(f.get("additions") or 0), 0)
        deletions += max(int(f.get("deletions") or 0), 0)
    return {
        "additions": additions,
        "deletions": deletions,
        "total_changed": additions + deletions,
        "files_considered": considered,
        "files_excluded": len(excluded),
        "excluded_paths": sorted(excluded),
        "truncated": len(files) >= max_files,
    }


# ---------------------------------------------------------------- justificación

_BLOCK = re.compile(
    r"<!--\s*size[-_ ]?ex(?:empt(?:ion)?|ception)\s*-->(.*?)"
    r"<!--\s*/\s*size[-_ ]?ex(?:empt(?:ion)?|ception)\s*-->",
    re.IGNORECASE | re.DOTALL,
)
_LINE = re.compile(
    r"^[ \t>*_-]*(?:size[-_ ]?ex(?:empt(?:ion)?|ception))[ \t]*[:=][ \t]*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_justification(body: str) -> str | None:
    """Devuelve el texto de justificación embebido en el cuerpo del PR.

    Se aceptan dos formas para no imponer un formato rígido:
      1. Bloque explícito:  <!-- size-exemption --> motivo <!-- /size-exemption -->
      2. Línea etiquetada:  Size exemption: motivo
    """
    if not body:
        return None
    for rx in (_BLOCK, _LINE):
        for m in rx.finditer(body):
            text = m.group(1).strip()
            # Descarta HTML residual si quedó dentro del bloque.
            text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
            if text:
                return text
    return None


def evaluate_exemption(
    *,
    labels,
    body,
    exempt_label,
    actor=None,
    actor_permission=None,
    require_authorized_actor=True,
    unattributable="deny",
    min_justification_chars=15,
    min_permission=DEFAULT_MIN_PERMISSION,
):
    """Decide si la excepción `size-exempt` está correctamente aplicada.

    Devuelve dict con requested/granted/reason. Fail-closed: ante la duda la
    excepción NO se concede (salvo que el repo configure unattributable=warn,
    que solo afecta al caso "no se pudo atribuir el actor", nunca a la falta
    de justificación).
    """
    requested = exempt_label in {(lbl or "").strip() for lbl in labels}
    if not requested:
        return {
            "requested": False,
            "granted": False,
            "reason": f"La etiqueta '{exempt_label}' no está aplicada: se aplica el límite.",
        }

    justification = extract_justification(body or "")
    if not justification:
        return {
            "requested": True,
            "granted": False,
            "reason": (
                "Falta la justificación obligatoria. Añade un bloque "
                "<!-- size-exemption --> motivo <!-- /size-exemption --> "
                "o una línea 'Size exemption: motivo' en el cuerpo del PR."
            ),
        }
    if len(re.sub(r"\s+", "", justification)) < min_justification_chars:
        return {
            "requested": True,
            "granted": False,
            "reason": (
                "La justificación es demasiado corta "
                f"(mínimo {min_justification_chars} caracteres no vacíos)."
            ),
        }

    if require_authorized_actor:
        if not actor:
            if unattributable == "warn":
                return {
                    "requested": True,
                    "granted": True,
                    "reason": (
                        "Excepción concedida con aviso: no se pudo determinar "
                        "quién aplicó la etiqueta y 'unattributable=warn' está "
                        "configurado."
                    ),
                }
            return {
                "requested": True,
                "granted": False,
                "reason": (
                    "No se pudo determinar quién aplicó la etiqueta "
                    f"'{exempt_label}', así que la excepción se rechaza. "
                    "Vuelve a aplicarla desde una cuenta con permiso de escritura."
                ),
            }
        perm = (actor_permission or "unknown").lower()
        required = (min_permission or DEFAULT_MIN_PERMISSION).lower()
        rank = PERMISSION_RANK.get(perm, 0)
        if rank < PERMISSION_RANK.get(required, 3):
            return {
                "requested": True,
                "granted": False,
                "reason": (
                    f"La etiqueta la aplicó '{actor}' con permiso '{perm}': solo "
                    f"mantenedores (al menos '{required}': write/maintain/admin) "
                    "pueden eximir del límite."
                ),
            }

    return {
        "requested": True,
        "granted": True,
        "reason": (
            f"Excepción aplicada por '{actor}' (permiso {actor_permission or 'n/d'}) "
            "con justificación."
            if require_authorized_actor
            else "Excepción aplicada con justificación (no se valida el actor)."
        ),
    }


# ------------------------------------------------------------------- veredicto


def classify(total_changed: int, max_pass: int, max_warn: int) -> str:
    """pass <= max_pass < warn <= max_warn < fail."""
    if total_changed <= max_pass:
        return "pass"
    if total_changed <= max_warn:
        return "warn"
    return "fail"


def evaluate(
    *,
    files,
    body="",
    labels=(),
    max_pass=100,
    max_warn=150,
    exempt_label="size-exempt",
    excludes=DEFAULT_EXCLUDES,
    actor=None,
    actor_permission=None,
    require_authorized_actor=True,
    unattributable="deny",
    min_justification_chars=15,
    min_permission=DEFAULT_MIN_PERMISSION,
    max_files=GITHUB_MAX_PR_FILES,
):
    counts = count_changed(files, excludes=excludes, max_files=max_files)
    exemption = evaluate_exemption(
        labels=labels,
        body=body,
        exempt_label=exempt_label,
        actor=actor,
        actor_permission=actor_permission,
        require_authorized_actor=require_authorized_actor,
        unattributable=unattributable,
        min_justification_chars=min_justification_chars,
        min_permission=min_permission,
    )

    total = counts["total_changed"]
    if counts["truncated"]:
        verdict = "fail"
        status_state = "failure"
        headline = (
            f"Diff truncado por GitHub ({max_files} ficheros): no se puede "
            "calcular el tamaño. Divide el PR."
        )
    elif exemption["granted"]:
        verdict = "pass"
        status_state = "success"
        headline = f"Exenta por '{exempt_label}': {total} líneas modificadas."
    else:
        verdict = classify(total, max_pass, max_warn)
        status_state = "failure" if verdict == "fail" else "success"
        if verdict == "pass":
            headline = f"{total} líneas modificadas (<= {max_pass})."
        elif verdict == "warn":
            headline = (
                f"{total} líneas modificadas: por encima de {max_pass} y hasta "
                f"{max_warn}. Pasa con aviso."
            )
        else:
            headline = (
                f"{total} líneas modificadas: supera {max_warn}. "
                "Reduce el PR o aplica una excepción justificada."
            )
        if exemption["requested"] and not exemption["granted"]:
            headline += f" Excepción rechazada: {exemption['reason']}"

    largest = sorted(
        (
            {
                "filename": f["filename"],
                "changed": max(int(f.get("additions") or 0), 0)
                + max(int(f.get("deletions") or 0), 0),
            }
            for f in files
            if not PathFilter(excludes).matches(f["filename"])
        ),
        key=lambda x: x["changed"],
        reverse=True,
    )[:10]

    summary = build_summary(counts, verdict, headline, exemption, max_pass, max_warn)

    return {
        "verdict": verdict,
        "status_state": status_state,
        "additions": counts["additions"],
        "deletions": counts["deletions"],
        "total_changed": total,
        "files_considered": counts["files_considered"],
        "files_excluded": counts["files_excluded"],
        "excluded_paths": counts["excluded_paths"],
        "largest_files": largest,
        "exemption": exemption,
        "limits": {"max_pass": max_pass, "max_warn": max_warn},
        "truncated": counts["truncated"],
        "headline": headline,
        "summary": summary,
    }


def build_summary(counts, verdict, headline, exemption, max_pass, max_warn) -> str:
    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[verdict]
    lines = [
        f"## {icon} Política de tamaño de PR — {verdict.upper()}",
        "",
        headline,
        "",
        "| Métrica | Valor |",
        "| --- | --- |",
        f"| Líneas modificadas (adiciones + eliminaciones) | **{counts['total_changed']}** |",
        f"| Adiciones | {counts['additions']} |",
        f"| Eliminaciones | {counts['deletions']} |",
        f"| Ficheros contados | {counts['files_considered']} |",
        f"| Ficheros excluidos | {counts['files_excluded']} |",
        f"| Umbral PASS | <= {max_pass} |",
        f"| Umbral WARN | {max_pass + 1}–{max_warn} |",
        f"| Umbral FAIL | > {max_warn} |",
        "",
    ]
    if exemption["requested"]:
        estado = "concedida" if exemption["granted"] else "rechazada"
        lines += [f"**Excepción**: {estado} — {exemption['reason']}", ""]
    if counts["excluded_paths"]:
        shown = ", ".join(f"`{p}`" for p in counts["excluded_paths"][:20])
        extra = (
            f" (+{len(counts['excluded_paths']) - 20} más)"
            if len(counts["excluded_paths"]) > 20
            else ""
        )
        lines += [f"Rutas excluidas: {shown}{extra}", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Política de tamaño de PR (Balanced)")
    p.add_argument("--files", nargs="+", required=True, help="JSONL de ficheros del PR")
    p.add_argument("--body", help="Fichero con el cuerpo del PR")
    p.add_argument("--labels", default="", help="Etiquetas separadas por comas")
    p.add_argument("--exempt-label", default="size-exempt")
    p.add_argument("--label-actor", default=None, help="Login que aplicó la etiqueta")
    p.add_argument(
        "--actor-permission",
        default=None,
        help="Permiso del actor en el repo (admin|maintain|write|triage|read|none|unknown)",
    )
    p.add_argument("--no-require-authorized-actor", action="store_true")
    p.add_argument("--unattributable", choices=["deny", "warn"], default="deny")
    p.add_argument("--min-justification-chars", type=int, default=15)
    p.add_argument(
        "--min-permission",
        default=DEFAULT_MIN_PERMISSION,
        help="Permiso mínimo para eximir: read|triage|write|maintain|admin",
    )
    p.add_argument("--max-pass", type=int, default=100)
    p.add_argument("--max-warn", type=int, default=150)
    p.add_argument("--max-files", type=int, default=GITHUB_MAX_PR_FILES)
    p.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Patrón de exclusión (repetible). Si se omite, usa los de la política.",
    )
    p.add_argument("--json-out", help="Escribe el veredicto JSON en esta ruta")
    p.add_argument("--enforce", action="store_true", help="Sale con 2 si el veredicto es fail")
    args = p.parse_args(argv)

    body = Path(args.body).read_text(encoding="utf-8") if args.body else ""
    labels = [x for x in (args.labels or "").split(",") if x.strip()]

    result = evaluate(
        files=load_files(args.files),
        body=body,
        labels=labels,
        max_pass=args.max_pass,
        max_warn=args.max_warn,
        exempt_label=args.exempt_label,
        excludes=tuple(args.exclude) if args.exclude else DEFAULT_EXCLUDES,
        actor=args.label_actor,
        actor_permission=args.actor_permission,
        require_authorized_actor=not args.no_require_authorized_actor,
        unattributable=args.unattributable,
        min_justification_chars=args.min_justification_chars,
        min_permission=args.min_permission,
        max_files=args.max_files,
    )

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if args.enforce and result["verdict"] == "fail":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
