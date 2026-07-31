"""Swagger UI theme alineado con DESIGN.md de XTask.

Reescribe la página de docs de FastAPI con un tema oscuro + sienna
para mantener coherencia visual con el SPA y la landing.
"""

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


XTASK_SWAGGER_CSS = """
/* ── XTask Swagger UI · dark + sienna ───────────────────────────── */
:root {
  --bg:        #0A0A0A;
  --bg-2:      #0D0D0D;
  --surface:   #131313;
  --surface-2: #171717;
  --rule:      #1F1F1F;
  --rule-2:    #2A2A2A;
  --ink:       #F4F2EE;
  --text-2:    #A8A29B;
  --text-3:    #6B645C;
  --accent:    #C76A3F;
  --accent-2:  #DD8159;
  --accent-d:  #5C2E18;
  --get:       #7AA0C6;
  --post:      #7BB662;
  --patch:     #D9994E;
  --delete:    #D26A6A;
  --ease:      cubic-bezier(0.23, 1, 0.32, 1);
}

html, body {
  background: var(--bg) !important;
  color: var(--ink) !important;
  font-family: 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  font-feature-settings: "ss01", "cv11";
  -webkit-font-smoothing: antialiased;
}

::selection { background: var(--accent-d); color: var(--ink); }

/* Top bar fuera */
.swagger-ui .topbar { display: none !important; }

/* Layout */
.swagger-ui { color: var(--ink) !important; max-width: 1140px; margin: 0 auto; padding: 32px 24px; }
.swagger-ui .wrapper { padding: 0; max-width: none; }

/* Heading principal */
.swagger-ui .information-container { padding: 0 0 32px; margin-bottom: 32px; border-bottom: 1px solid var(--rule); }
.swagger-ui .info { margin: 0; }
.swagger-ui .info .title {
  color: var(--ink) !important;
  font-size: 32px !important;
  font-weight: 500 !important;
  letter-spacing: -0.02em !important;
  line-height: 1.1;
}
.swagger-ui .info .title small {
  background: var(--surface) !important;
  border: 1px solid var(--rule) !important;
  color: var(--text-2) !important;
  font-family: 'Geist Mono', monospace !important;
  font-size: 11px !important;
  padding: 2px 8px !important;
  border-radius: 4px !important;
  margin-left: 12px;
  vertical-align: middle;
}
.swagger-ui .info .title small pre { background: transparent !important; padding: 0 !important; color: var(--text-2) !important; }
.swagger-ui .info .base-url, .swagger-ui .info hgroup.main a { color: var(--accent-2) !important; }
.swagger-ui .info p, .swagger-ui .info li, .swagger-ui .info table { color: var(--text-2) !important; }

/* Scheme container (servers, authorize) */
.swagger-ui .scheme-container {
  background: var(--bg-2) !important;
  border: 1px solid var(--rule) !important;
  box-shadow: none !important;
  border-radius: 12px;
  padding: 16px 20px;
  margin: 0 0 32px;
}
.swagger-ui .scheme-container .schemes-title { color: var(--text-3) !important; }
.swagger-ui select {
  background: var(--surface) !important;
  border: 1px solid var(--rule) !important;
  color: var(--ink) !important;
  border-radius: 8px !important;
  height: 36px !important;
  padding: 0 12px !important;
  font-size: 14px !important;
  box-shadow: none !important;
}
.swagger-ui .auth-wrapper .authorize {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: var(--bg) !important;
  border-radius: 8px !important;
  height: 36px !important;
  padding: 0 14px !important;
  transition: background 160ms var(--ease);
}
.swagger-ui .auth-wrapper .authorize:hover { background: var(--accent-2) !important; border-color: var(--accent-2) !important; }
.swagger-ui .auth-wrapper .authorize svg { fill: var(--bg) !important; }

/* Tags (sections) */
.swagger-ui .opblock-tag {
  background: transparent !important;
  border: 0 !important;
  border-bottom: 1px solid var(--rule) !important;
  padding: 24px 0 12px !important;
  margin: 0 0 12px !important;
  color: var(--ink) !important;
  font-size: 20px !important;
  font-weight: 500 !important;
  letter-spacing: -0.018em !important;
}
.swagger-ui .opblock-tag small {
  background: transparent !important;
  color: var(--text-3) !important;
  font-weight: 400 !important;
  font-size: 14px !important;
  margin-left: 12px;
}
.swagger-ui .opblock-tag:hover { background: transparent !important; }

/* Operation blocks (endpoints) */
.swagger-ui .opblock {
  background: var(--bg-2) !important;
  border: 1px solid var(--rule) !important;
  border-radius: 10px !important;
  box-shadow: none !important;
  margin: 0 0 8px !important;
}
.swagger-ui .opblock .opblock-summary {
  border-bottom: 0 !important;
  padding: 8px 12px !important;
}
.swagger-ui .opblock .opblock-summary-method {
  font-family: 'Geist Mono', monospace !important;
  font-weight: 500 !important;
  font-size: 12px !important;
  min-width: 72px !important;
  padding: 6px 0 !important;
  border-radius: 6px !important;
  text-shadow: none !important;
  letter-spacing: 0.04em;
}
.swagger-ui .opblock.opblock-get    { border-left: 2px solid var(--get) !important; }
.swagger-ui .opblock.opblock-post   { border-left: 2px solid var(--post) !important; }
.swagger-ui .opblock.opblock-patch  { border-left: 2px solid var(--patch) !important; }
.swagger-ui .opblock.opblock-put    { border-left: 2px solid var(--patch) !important; }
.swagger-ui .opblock.opblock-delete { border-left: 2px solid var(--delete) !important; }
.swagger-ui .opblock.opblock-get   .opblock-summary-method { background: rgba(122,160,198,0.15) !important; color: var(--get) !important; }
.swagger-ui .opblock.opblock-post  .opblock-summary-method { background: rgba(123,182,98,0.15)  !important; color: var(--post) !important; }
.swagger-ui .opblock.opblock-patch .opblock-summary-method { background: rgba(217,153,78,0.15)  !important; color: var(--patch) !important; }
.swagger-ui .opblock.opblock-put   .opblock-summary-method { background: rgba(217,153,78,0.15)  !important; color: var(--patch) !important; }
.swagger-ui .opblock.opblock-delete.opblock-summary-method { background: rgba(210,106,106,0.15) !important; color: var(--delete) !important; }
.swagger-ui .opblock.opblock-delete .opblock-summary-method { background: rgba(210,106,106,0.15) !important; color: var(--delete) !important; }

.swagger-ui .opblock-summary-path {
  font-family: 'Geist Mono', monospace !important;
  color: var(--ink) !important;
  font-size: 13.5px !important;
  letter-spacing: -0.01em;
}
.swagger-ui .opblock-summary-path__deprecated { color: var(--text-4) !important; }
.swagger-ui .opblock-summary-description { color: var(--text-2) !important; font-size: 13.5px !important; }
.swagger-ui .opblock-summary { transition: background 160ms var(--ease); }
.swagger-ui .opblock-summary:hover { background: var(--surface) !important; }

.swagger-ui .opblock.is-open { background: var(--bg-2) !important; }
.swagger-ui .opblock.is-open .opblock-summary { background: var(--surface) !important; border-bottom: 1px solid var(--rule) !important; }

.swagger-ui .opblock-body { background: var(--bg-2) !important; padding: 16px 0 !important; }
.swagger-ui .opblock-section-header {
  background: transparent !important;
  border: 0 !important;
  border-bottom: 1px solid var(--rule) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  padding: 8px 16px !important;
  margin: 0 0 16px !important;
}
.swagger-ui .opblock-section-header h4, .swagger-ui .opblock-section-header > label { color: var(--ink) !important; font-weight: 500 !important; font-size: 13px !important; }
.swagger-ui .opblock-description-wrapper p,
.swagger-ui .opblock-external-docs-wrapper p { color: var(--text-2) !important; }

/* Parameters */
.swagger-ui .parameters-container, .swagger-ui table.parameters { background: transparent !important; }
.swagger-ui table.parameters tbody tr { background: transparent !important; border-bottom: 1px solid var(--rule); }
.swagger-ui table.parameters tbody tr td { background: transparent !important; padding: 12px 16px !important; }
.swagger-ui .parameter__name { color: var(--ink) !important; font-weight: 500 !important; font-family: 'Geist Mono', monospace !important; font-size: 13px; }
.swagger-ui .parameter__name.required::after { color: var(--accent) !important; }
.swagger-ui .parameter__type { color: var(--text-3) !important; font-family: 'Geist Mono', monospace !important; }
.swagger-ui .parameter__in { color: var(--text-3) !important; font-style: normal; }
.swagger-ui .parameter__deprecated { color: var(--text-4) !important; }
.swagger-ui table thead tr th { background: transparent !important; color: var(--text-3) !important; border-bottom: 1px solid var(--rule) !important; }

/* Inputs */
.swagger-ui input[type=text], .swagger-ui input[type=password], .swagger-ui input[type=email],
.swagger-ui input[type=search], .swagger-ui textarea {
  background: var(--surface) !important;
  border: 1px solid var(--rule) !important;
  color: var(--ink) !important;
  border-radius: 8px !important;
  padding: 8px 12px !important;
  font-family: 'Geist Mono', monospace !important;
  font-size: 13px !important;
  box-shadow: none !important;
  transition: border-color 160ms var(--ease);
}
.swagger-ui input:focus, .swagger-ui textarea:focus { border-color: var(--accent) !important; outline: none !important; }
.swagger-ui .body-param__text, .swagger-ui .body-param-content-type { color: var(--text-2) !important; }
.swagger-ui textarea.body-param__text { min-height: 160px; }

/* Botones de acción */
.swagger-ui .btn {
  background: transparent !important;
  border: 1px solid var(--rule-2) !important;
  color: var(--ink) !important;
  border-radius: 8px !important;
  font-family: inherit !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 8px 16px !important;
  box-shadow: none !important;
  text-shadow: none !important;
  transition: background 160ms var(--ease), border-color 160ms var(--ease), transform 120ms var(--ease);
}
.swagger-ui .btn:hover { background: var(--surface) !important; border-color: #4A4A4A !important; }
.swagger-ui .btn:active { transform: scale(0.97); }
.swagger-ui .btn.execute {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: var(--bg) !important;
}
.swagger-ui .btn.execute:hover { background: var(--accent-2) !important; border-color: var(--accent-2) !important; }
.swagger-ui .btn.cancel { color: var(--text-2) !important; border-color: var(--rule) !important; }
.swagger-ui .btn.try-out__btn { border-color: var(--rule-2) !important; }
.swagger-ui .btn-clear { color: var(--text-2) !important; }

/* Responses */
.swagger-ui .responses-wrapper { background: transparent !important; }
.swagger-ui table.responses-table { background: transparent !important; }
.swagger-ui table.responses-table tbody tr { background: transparent !important; border-bottom: 1px solid var(--rule); }
.swagger-ui .response-col_status { color: var(--ink) !important; font-family: 'Geist Mono', monospace !important; font-weight: 500 !important; }
.swagger-ui .response-col_description__inner p { color: var(--text-2) !important; }

/* Bloques de código JSON */
.swagger-ui .highlight-code, .swagger-ui .microlight, .swagger-ui pre {
  background: var(--bg) !important;
  border: 1px solid var(--rule) !important;
  border-radius: 8px !important;
  color: var(--text-2) !important;
  font-family: 'Geist Mono', monospace !important;
  font-size: 12.5px !important;
  line-height: 1.55 !important;
  padding: 12px 16px !important;
}
.swagger-ui .highlight-code .copy-to-clipboard {
  background: var(--surface-2) !important;
  border: 1px solid var(--rule-2) !important;
  border-radius: 6px !important;
}
.swagger-ui .highlight-code .copy-to-clipboard button { background: transparent !important; color: var(--text-2) !important; }
.swagger-ui .download-contents { background: var(--surface) !important; color: var(--ink) !important; border: 1px solid var(--rule-2) !important; border-radius: 6px !important; }

/* Schemas */
.swagger-ui section.models {
  background: var(--bg-2) !important;
  border: 1px solid var(--rule) !important;
  border-radius: 12px !important;
  margin: 32px 0 0 !important;
  padding: 16px 20px !important;
}
.swagger-ui section.models h4 { color: var(--ink) !important; }
.swagger-ui section.models .model-container { background: transparent !important; border-bottom: 1px solid var(--rule); padding: 8px 0; }
.swagger-ui section.models .model-container:last-child { border-bottom: 0; }
.swagger-ui .model-title { color: var(--ink) !important; font-family: 'Geist Mono', monospace !important; }
.swagger-ui .model { color: var(--text-2) !important; }
.swagger-ui .model .property { color: var(--text-2) !important; }
.swagger-ui .model .property.primitive { color: var(--accent-2) !important; }
.swagger-ui .prop-type { color: var(--get) !important; font-family: 'Geist Mono', monospace !important; }
.swagger-ui .prop-name { color: var(--ink) !important; font-family: 'Geist Mono', monospace !important; }

/* Loading spinner */
.swagger-ui .loading-container .loading::before { border-color: var(--accent) transparent transparent transparent !important; }

/* Curl & request URL */
.swagger-ui .curl-command, .swagger-ui .request-url {
  background: var(--bg) !important;
  border: 1px solid var(--rule) !important;
  color: var(--text-2) !important;
}

/* Tab buttons (Example / Schema) */
.swagger-ui .tab li { color: var(--text-3) !important; }
.swagger-ui .tab li.active { color: var(--ink) !important; }
.swagger-ui .tab li button.tablinks { color: inherit !important; }

/* Icons */
.swagger-ui svg.arrow { fill: var(--text-2) !important; }
.swagger-ui .opblock-summary-control svg { fill: var(--text-2) !important; }
.swagger-ui .authorization__btn svg, .swagger-ui .unlocked svg { fill: var(--text-2) !important; }
.swagger-ui .authorization__btn.locked svg { fill: var(--accent) !important; }

/* Modal de autorización */
.swagger-ui .dialog-ux .modal-ux {
  background: var(--bg-2) !important;
  border: 1px solid var(--rule) !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
}
.swagger-ui .dialog-ux .modal-ux-header { border-bottom: 1px solid var(--rule) !important; }
.swagger-ui .dialog-ux .modal-ux-header h3 { color: var(--ink) !important; }
.swagger-ui .dialog-ux .modal-ux-content h4,
.swagger-ui .dialog-ux .modal-ux-content p,
.swagger-ui .dialog-ux .modal-ux-content label { color: var(--ink) !important; }
.swagger-ui .auth-container { border-bottom: 1px solid var(--rule) !important; padding-bottom: 16px; }
.swagger-ui .auth-container h6 { color: var(--text-2) !important; }
.swagger-ui .dialog-ux .backdrop-ux { background: rgba(10,10,10,0.7) !important; backdrop-filter: blur(4px); }

/* Scrollbar */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--rule-2); border-radius: 999px; border: 2px solid var(--bg); }
::-webkit-scrollbar-thumb:hover { background: var(--text-4); }

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
}
"""


def install_xtask_swagger(app: FastAPI, openapi_url: str, title: str) -> None:
    """Reemplaza el endpoint /docs por uno con el tema XTask inyectado.

    Llamar después de crear el `FastAPI` y antes de servir la primera
    request. Requiere que `docs_url` se haya pasado como None al constructor
    (o se desactivará el reemplazo).
    """

    @app.get(app.docs_url or "/docs", include_in_schema=False)
    async def custom_swagger_ui_html() -> HTMLResponse:
        html = get_swagger_ui_html(
            openapi_url=openapi_url,
            title=f"{title} · API",
            swagger_favicon_url="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect width='24' height='24' rx='5' fill='%23C76A3F'/><text x='12' y='17' font-family='-apple-system,sans-serif' font-size='14' font-weight='600' fill='%230A0A0A' text-anchor='middle'>X</text></svg>",
            swagger_ui_parameters={
                "docExpansion": "list",
                "defaultModelsExpandDepth": 0,
                "displayRequestDuration": True,
                "tryItOutEnabled": True,
                "syntaxHighlight.theme": "tomorrow-night",
            },
        )
        body = html.body.decode("utf-8")
        # Inyecta Geist + nuestro tema
        font_link = (
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&'
            'family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">'
        )
        style_block = f"<style>{XTASK_SWAGGER_CSS}</style>"
        body = body.replace("</head>", f"{font_link}{style_block}</head>")
        return HTMLResponse(body)
