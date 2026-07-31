"""Templates HTML responsivos para los emails transaccionales (P-04.2).

Renderizado simple via str.format (no Jinja2 — son strings cortos).
"""

from typing import Any


def render_email(
    *,
    title: str,
    body: str,
    cta_label: str | None = None,
    cta_url: str | None = None,
    category: str = "general",
) -> tuple[str, str]:
    """Devuelve (html, text). El layout es minimal, accesible, dark-mode friendly."""
    accent = _CATEGORY_COLOR.get(category, "#02BDEA")

    cta_html = ""
    cta_text = ""
    if cta_label and cta_url:
        cta_html = (
            f'<p style="margin:24px 0;text-align:center;">'
            f'<a href="{cta_url}" style="display:inline-block;padding:12px 24px;'
            f'background:{accent};color:#FFFFFF;text-decoration:none;'
            f'border-radius:6px;font-weight:600;font-size:14px;">'
            f"{cta_label}</a></p>"
        )
        cta_text = f"\n\n{cta_label}: {cta_url}"

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title></head>
<body style="margin:0;padding:24px;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:#F7F7F9;color:#1A1726;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:8px;overflow:hidden;border:1px solid #E5E5EA;">
  <tr><td style="padding:24px 32px 0;border-bottom:3px solid {accent};">
    <h1 style="margin:0;font-size:14px;font-weight:600;color:{accent};letter-spacing:0.04em;text-transform:uppercase;">XTask · {category}</h1>
  </td></tr>
  <tr><td style="padding:32px 32px 8px;">
    <h2 style="margin:0 0 16px;font-size:20px;font-weight:600;color:#1A1726;line-height:1.3;">{title}</h2>
    <div style="font-size:14px;line-height:1.6;color:#605C70;">{body}</div>
    {cta_html}
  </td></tr>
  <tr><td style="padding:16px 32px 24px;border-top:1px solid #E5E5EA;background:#F7F7F9;">
    <p style="margin:0;font-size:11px;color:#8E8A99;text-align:center;line-height:1.5;">
      Recibís este email porque tenés notificaciones de "{category}" activadas.<br>
      Podés cambiar tus preferencias desde XTask → Configuración.
    </p>
  </td></tr>
</table></body></html>"""

    text = f"""{title}

{_strip_html_to_text(body)}{cta_text}

— XTask
Cambiá tus preferencias desde XTask → Configuración."""

    return html, text


_CATEGORY_COLOR: dict[str, str] = {
    "contracts": "#0A4D70",
    "leaves": "#02BDEA",
    "payouts": "#01B89E",
    "okrs": "#251948",
    "kpis": "#251948",
    "ats": "#E08A0E",
    "auth": "#02BDEA",
    "approvals": "#E08A0E",
    "general": "#02BDEA",
}


def _strip_html_to_text(html: str) -> str:
    import re
    txt = re.sub(r"<br\s*/?>", "\n", html)
    txt = re.sub(r"</?p\b[^>]*>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


# Templates pre-definidos por evento
def welcome(name: str, login_url: str) -> tuple[str, str]:
    return render_email(
        title=f"Bienvenido a XTask, {name}",
        body=(
            "<p>Tu cuenta acaba de crearse en XTask. Ya podés iniciar sesión y empezar a usar la plataforma.</p>"
            "<p>Si tenés dudas, contactá a tu administrador o respondé a este email.</p>"
        ),
        cta_label="Iniciar sesión", cta_url=login_url, category="auth",
    )


def leave_decided(name: str, type_name: str, days: float, approved: bool, link: str) -> tuple[str, str]:
    return render_email(
        title=f"Tu solicitud de {type_name.lower()} fue {'aprobada' if approved else 'rechazada'}",
        body=(
            f"<p>Hola {name},</p>"
            f"<p>Tu solicitud de <strong>{days:.0f} días</strong> fue {'aprobada' if approved else 'rechazada'} por tu manager.</p>"
        ),
        cta_label="Ver detalle", cta_url=link, category="leaves",
    )


def payout_paid(name: str, amount: float, currency: str, link: str) -> tuple[str, str]:
    return render_email(
        title=f"Tu comisión fue pagada",
        body=(
            f"<p>Hola {name},</p>"
            f"<p>Acabamos de marcar como pagada tu comisión del período: "
            f"<strong>{amount:.2f} {currency}</strong>.</p>"
        ),
        cta_label="Ver detalle", cta_url=link, category="payouts",
    )


def contract_signed(name: str, contract_title: str, link: str) -> tuple[str, str]:
    return render_email(
        title=f"Contrato firmado: {contract_title}",
        body=(
            f"<p>Hola {name},</p>"
            f"<p>El contrato <strong>{contract_title}</strong> fue firmado y queda en estado final.</p>"
        ),
        cta_label="Ver contrato", cta_url=link, category="contracts",
    )
