"""
Documento de las reglas de negocio para leer y presentar (Markdown o HTML imprimible).

El `reglas_negocio.toml` es el formato de trabajo: se edita y se verifica. Este módulo lo convierte en un documento
que cualquiera entiende sin saber TOML: cuántas reglas hay y en qué estado, una tabla de contenido y, por cada regla,
qué dice, en qué casos se comprueba (Dado / Cuando / Entonces), qué dudas faltan por resolver y de qué parte del
documento de requisitos salió. El HTML se puede imprimir o guardar como PDF desde el navegador.
"""

from datetime import date
from html import escape

from app.analyses.reglas import BusinessRule, RuleSet

TYPE_LABEL = {
    "datos": "Datos",
    "flujo": "Flujo",
    "calculo": "Cálculo",
    "permisos": "Permisos",
    "auditoria": "Auditoría",
    "integracion": "Integración",
    "proceso": "Proceso (lo hace una persona)",
}
SEVERITY_LABEL = {"alta": "Alta", "media": "Media", "baja": "Baja"}
STATE_LABEL = {"aprobada": "Aprobada", "borrador": "Borrador (por revisar)"}

LEGEND = [
    ("Gravedad", "qué tan grave es que la regla no se cumpla: alta (dinero, seguridad, permisos o datos personales), media (la operación) o baja."),
    ("Estado", "«Aprobada» = el equipo la revisó y se comprueba en cada análisis. «Borrador» = falta revisarla; todavía no se comprueba."),
    ("Ejemplos", "cada ejemplo cuenta un caso con datos concretos: **Dado** cómo está el sistema, **cuando** pasa algo, **entonces** qué debe ocurrir."),
    ("Dudas", "lo que el documento de requisitos no deja claro. Hay que resolverlo antes de aprobar la regla."),
]


def _quote_state(rule: BusinessRule) -> str:
    if rule.quote_ok is None:
        return "Cita del documento (no se pudo comprobar automáticamente)"
    return "Cita comprobada en el documento" if rule.quote_ok else "Cita NO encontrada en el documento: revísala"


def _how_checked(rule: BusinessRule) -> str:
    if rule.process:
        return "Fuera del código: la hace una persona, así que no se comprueba con pruebas."
    parts = []
    if rule.scenarios:
        parts.append(f"{len(rule.scenarios)} ejemplo(s) que se convierten en prueba")
    if rule.forbidden:
        parts.append(f"no debe aparecer el patrón `{rule.forbidden}`")
    if rule.required:
        parts.append(f"debe aparecer el patrón `{rule.required}`")
    return "; ".join(parts).capitalize() + "." if parts else "Aún sin forma de comprobarse: falta un ejemplo o un patrón."


def _summary(rules: RuleSet) -> list[str]:
    items = rules.rules
    approved = sum(r.approved for r in items)
    doubts = sum(bool(r.doubts) for r in items)
    process = sum(r.process for r in items)
    lines = [f"{len(items)} reglas: {approved} aprobadas y {len(items) - approved} en borrador."]
    if doubts:
        lines.append(f"{doubts} con dudas por resolver.")
    if process:
        lines.append(f"{process} de proceso: las hace una persona y no se comprueban con pruebas.")
    return lines


def markdown(rules: RuleSet, today: date | None = None) -> str:
    out = [f"# Reglas de negocio · {rules.project}", "", f"_{(today or date.today()).strftime('%d/%m/%Y')}_", ""]
    out += [f"**{line}**  " for line in _summary(rules)]
    out += ["", "## Cómo leer este documento", ""] + [f"- **{k}:** {v}" for k, v in LEGEND]
    out += ["", "## Resumen", "", "| Regla | Título | Gravedad | Tipo | Estado |", "|---|---|---|---|---|"]
    for r in rules.rules:
        out.append(f"| {r.id} | {r.title} | {SEVERITY_LABEL.get(r.severity, r.severity)} | {TYPE_LABEL.get(r.tipo or '', '—')} | {STATE_LABEL.get(r.status, r.status)} |")
    for r in rules.rules:
        out += ["", "---", "", f"## {r.id} · {r.title}", ""]
        out.append(f"**Gravedad:** {SEVERITY_LABEL.get(r.severity, r.severity)} · **Tipo:** {TYPE_LABEL.get(r.tipo or '', '—')} · **Estado:** {STATE_LABEL.get(r.status, r.status)}")
        if r.description and r.description.strip().lower() != r.title.strip().lower():
            out += ["", r.description]
        if r.scenarios:
            out += ["", "**Ejemplos**", ""]
            out += [f"{i}. **Dado** {s.given}; **cuando** {s.when}; **entonces** {s.then}." for i, s in enumerate(r.scenarios, 1)]
        out += ["", f"**Cómo se comprueba:** {_how_checked(r)}"]
        if r.doubts:
            out += ["", "**Dudas por resolver**", ""] + [f"- {d}" for d in r.doubts]
        if r.source:
            out += ["", f"_Fuente: {r.source}_"]
        if r.quote:
            out += ["", f"> {r.quote}", f"> {_quote_state(r)}"]
    return "\n".join(out) + "\n"


CSS = """
:root{color-scheme:light}
body{font:15px/1.55 system-ui,'Segoe UI',sans-serif;color:#1e293b;max-width:860px;margin:2rem auto;padding:0 1.25rem}
h1{font-size:1.8rem;margin:0 0 .2rem}h2{font-size:1.15rem;margin:0 0 .4rem}
.fecha{color:#64748b;margin:0 0 1rem}
.resumen{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0}
.resumen span{background:#eef2ff;color:#3730a3;border-radius:999px;padding:.25rem .8rem;font-weight:600;font-size:.9rem}
.leyenda{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:.8rem 1.1rem;margin:1rem 0}
.leyenda p{margin:.3rem 0}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid #e2e8f0;font-size:.9rem}
th{background:#f1f5f9}
.regla{border:1px solid #e2e8f0;border-radius:12px;padding:1rem 1.2rem;margin:1rem 0;break-inside:avoid}
.id{font-family:ui-monospace,Consolas,monospace;color:#64748b;font-size:.85rem}
.etiquetas{display:flex;flex-wrap:wrap;gap:.4rem;margin:.4rem 0 .6rem}
.etiqueta{border-radius:6px;padding:.1rem .55rem;font-size:.78rem;font-weight:600;background:#f1f5f9;color:#334155}
.alta{background:#ffe4e6;color:#9f1239}.media{background:#fef3c7;color:#92400e}.baja{background:#e0f2fe;color:#075985}
.aprobada{background:#dcfce7;color:#166534}.borrador{background:#f1f5f9;color:#475569}
.ejemplo{background:#f8fafc;border-left:3px solid #6366f1;padding:.4rem .8rem;margin:.4rem 0;border-radius:0 8px 8px 0;font-size:.9rem}
.dudas{background:#fff1f2;border:1px solid #fecdd3;border-radius:8px;padding:.5rem .9rem;margin:.6rem 0;font-size:.9rem}
.dudas ul{margin:.3rem 0 0 1.1rem;padding:0}
.fuente{color:#64748b;font-size:.82rem;margin-top:.6rem}
.como{color:#475569;font-size:.88rem}
.cita{border-left:3px solid #94a3b8;margin:.6rem 0;padding:.2rem .8rem;color:#475569;font-style:italic;font-size:.88rem}
@media print{body{margin:0;max-width:none}.regla{border-color:#cbd5e1}}
"""


def html(rules: RuleSet, today: date | None = None) -> str:
    e = escape
    out = [
        '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>Reglas de negocio · {e(rules.project)}</title><style>{CSS}</style></head><body>",
        f"<h1>Reglas de negocio · {e(rules.project)}</h1>",
        f'<p class="fecha">{(today or date.today()).strftime("%d/%m/%Y")}</p>',
        '<div class="resumen">' + "".join(f"<span>{e(line)}</span>" for line in _summary(rules)) + "</div>",
        '<div class="leyenda"><strong>Cómo leer este documento</strong>',
    ]
    for key, text in LEGEND:
        out.append(f"<p><strong>{e(key)}:</strong> {e(text).replace('**', '')}</p>")
    out.append("</div><h2>Resumen</h2><table><tr><th>Regla</th><th>Título</th><th>Gravedad</th><th>Tipo</th><th>Estado</th></tr>")
    for r in rules.rules:
        out.append(
            f'<tr><td class="id">{e(r.id)}</td><td>{e(r.title)}</td><td>{e(SEVERITY_LABEL.get(r.severity, r.severity))}</td>'
            f"<td>{e(TYPE_LABEL.get(r.tipo or '', '—'))}</td><td>{e(STATE_LABEL.get(r.status, r.status))}</td></tr>"
        )
    out.append("</table>")
    for r in rules.rules:
        out.append(f'<section class="regla"><span class="id">{e(r.id)}</span><h2>{e(r.title)}</h2><div class="etiquetas">')
        out.append(f'<span class="etiqueta {e(r.severity)}">Gravedad {e(SEVERITY_LABEL.get(r.severity, r.severity))}</span>')
        if r.tipo:
            out.append(f'<span class="etiqueta">{e(TYPE_LABEL.get(r.tipo, r.tipo))}</span>')
        out.append(f'<span class="etiqueta {e(r.status)}">{e(STATE_LABEL.get(r.status, r.status))}</span></div>')
        if r.description and r.description.strip().lower() != r.title.strip().lower():
            out.append(f"<p>{e(r.description)}</p>")
        for i, s in enumerate(r.scenarios, 1):
            out.append(f'<div class="ejemplo"><strong>Ejemplo {i}.</strong> <strong>Dado</strong> {e(s.given)}; <strong>cuando</strong> {e(s.when)}; <strong>entonces</strong> {e(s.then)}.</div>')
        out.append(f'<p class="como"><strong>Cómo se comprueba:</strong> {e(_how_checked(r)).replace("`", "")}</p>')
        if r.doubts:
            out.append('<div class="dudas"><strong>Dudas por resolver</strong><ul>' + "".join(f"<li>{e(d)}</li>" for d in r.doubts) + "</ul></div>")
        if r.source:
            out.append(f'<p class="fuente">Fuente: {e(r.source)}</p>')
        if r.quote:
            out.append(f'<blockquote class="cita">{e(r.quote)}<br><small>{e(_quote_state(r))}</small></blockquote>')
        out.append("</section>")
    out.append("</body></html>")
    return "\n".join(out)
