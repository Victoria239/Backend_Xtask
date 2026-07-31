"""Seed de 5 plantillas de contrato pre-configuradas (E-03).

Idempotente: si una plantilla con el mismo nombre+tenant ya existe, la actualiza
solo si la marca `_xtask_seed: true` está en meta — para que el usuario pueda
modificar libremente sin que el seed le pise los cambios.

Invocable vía POST /api/docgen/internal/seed-contracts?tenant_id=X.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CONTRACT_TEMPLATES = [
    {
        "name": "Contrato indefinido",
        "description": "Modelo base para contratos a tiempo indefinido conforme legislación local",
        "category": "contrato",
        "rag_query": "tipo contrato indefinido salario periodo prueba vacaciones",
        "body": """# Contrato laboral indefinido

**Entre las partes:**
- **Empleador:** Xtask SaaS S.L.
- **Empleado/a:** {{ employee.first_name }} {{ employee.last_name }}
- **Posición:** {{ employee.position }}
- **Departamento:** {{ employee.department }}

## 1. Objeto

El empleado/a se compromete a prestar sus servicios profesionales como **{{ employee.position }}** bajo las directrices del empleador.

## 2. Retribución

Salario bruto anual: **{{ custom.salary_eur | default(employee.salary) }} EUR**, abonable en doce mensualidades.

## 3. Cláusulas vigentes

{{ rag.block }}

## 4. Vigencia

El presente contrato tiene carácter **indefinido** y entra en vigor el {{ custom.start_date | default('fecha a determinar') }}.

---
Firmado en _____________ a _____________ de _____________.
""",
    },
    {
        "name": "Contrato temporal",
        "description": "Contrato a término fijo con fecha de inicio y fin definidas",
        "category": "contrato",
        "rag_query": "contrato temporal duración determinada finalización",
        "body": """# Contrato temporal

**Entre:** Xtask SaaS S.L. y **{{ employee.first_name }} {{ employee.last_name }}**

## 1. Posición y duración

- **Rol:** {{ employee.position }} en {{ employee.department }}
- **Inicio:** {{ custom.start_date | default('a determinar') }}
- **Fin previsto:** {{ custom.end_date | default('a determinar') }}
- **Causa de temporalidad:** {{ custom.reason | default('sustitución / proyecto puntual') }}

## 2. Retribución

{{ custom.salary_eur | default(employee.salary) }} EUR brutos anuales, prorrateados al período del contrato.

## 3. Políticas aplicables

{{ rag.block }}

## 4. Extinción

El contrato se extinguirá automáticamente en la fecha prevista de fin, sin necesidad de preaviso.

---
""",
    },
    {
        "name": "Acuerdo de confidencialidad (NDA)",
        "description": "NDA mutual para colaboraciones y onboarding",
        "category": "nda",
        "rag_query": "confidencialidad información reservada secretos comerciales obligaciones",
        "body": """# Acuerdo de confidencialidad

**Partes:**
- **Xtask SaaS S.L.** (en adelante, "la Empresa")
- **{{ employee.first_name }} {{ employee.last_name }}** (en adelante, "el/la Receptor/a")

## 1. Objeto

El presente acuerdo regula el tratamiento de la información confidencial que el/la Receptor/a pueda conocer en su relación con la Empresa como **{{ employee.position }}**.

## 2. Obligaciones específicas

{{ rag.block }}

## 3. Vigencia y duración

Este acuerdo permanece vigente durante toda la relación contractual y por **{{ custom.years_after | default(5) }} años** después de su finalización.

## 4. Devolución de información

Al cese de la relación, el/la Receptor/a se compromete a devolver toda documentación y a eliminar copias digitales en su posesión.

---
""",
    },
    {
        "name": "Contrato freelance / autónomo",
        "description": "Contrato mercantil para profesionales independientes",
        "category": "freelance",
        "rag_query": "contrato mercantil autónomo facturación entregables propiedad intelectual",
        "body": """# Contrato de servicios profesionales

**Cliente:** Xtask SaaS S.L.
**Prestador/a:** {{ employee.first_name }} {{ employee.last_name }} (NIF: {{ custom.nif | default('___________') }})

## 1. Naturaleza

Relación mercantil de carácter no laboral. El/la prestador/a actúa como autónomo/a y es responsable de sus obligaciones fiscales.

## 2. Servicios

- **Descripción:** {{ custom.service_description | default('Servicios técnicos en el ámbito de ' + employee.department) }}
- **Entregables:** según anexos.
- **Plazo:** {{ custom.duration | default('hasta finalización del proyecto') }}.

## 3. Honorarios

**{{ custom.fee_eur | default('a determinar') }} EUR** + IVA, facturable {{ custom.invoice_period | default('mensualmente') }}.

## 4. Cláusulas vigentes

{{ rag.block }}

## 5. Propiedad intelectual

Todo material generado durante la prestación queda en propiedad exclusiva del Cliente.

---
""",
    },
    {
        "name": "Adenda salarial",
        "description": "Modificación de retribución sobre contrato existente",
        "category": "adenda",
        "rag_query": "modificación retributiva adenda salario revisión",
        "body": """# Adenda al contrato laboral

**Empleado/a:** {{ employee.first_name }} {{ employee.last_name }} — {{ employee.position }}, {{ employee.department }}

## 1. Antecedentes

Con efecto desde el contrato original firmado entre las partes, se acuerda mediante la presente adenda la modificación de las condiciones retributivas.

## 2. Nueva retribución

- **Salario bruto anual anterior:** {{ custom.old_salary | default('___________') }} EUR
- **Salario bruto anual revisado:** **{{ custom.new_salary | default(employee.salary) }} EUR**
- **Vigente desde:** {{ custom.effective_date | default('próximo período de pago') }}

## 3. Motivo

{{ custom.reason | default('Revisión anual conforme a políticas internas y desempeño.') }}

## 4. Resto de cláusulas

Todas las demás cláusulas del contrato original permanecen inalteradas. Aplicables las siguientes políticas:

{{ rag.block }}

---
""",
    },
]


async def seed_contract_templates(db: AsyncSession, tenant_id: int) -> dict:
    """Inserta o actualiza las plantillas seed.

    Retorna {created: N, updated: N, kept: N}.
    """
    created = 0
    updated = 0
    kept = 0

    for tpl in CONTRACT_TEMPLATES:
        # Buscamos existente por nombre+tenant
        existing = (await db.execute(
            text(
                "SELECT id, description FROM svc_docgen.doc_templates "
                "WHERE tenant_id = :tid AND name = :n LIMIT 1"
            ),
            {"tid": tenant_id, "n": tpl["name"]},
        )).first()

        if existing is None:
            await db.execute(
                text(
                    """
                    INSERT INTO svc_docgen.doc_templates
                        (tenant_id, name, description, category, body, rag_query, created_by)
                    VALUES (:tid, :n, :d, :cat, :body, :rag, NULL)
                    """
                ),
                {
                    "tid": tenant_id, "n": tpl["name"], "d": tpl["description"],
                    "cat": tpl["category"], "body": tpl["body"], "rag": tpl["rag_query"],
                },
            )
            created += 1
        else:
            # No tocamos templates ya creados — el seed es solo para bootstrap inicial.
            kept += 1

    return {"created": created, "updated": updated, "kept": kept}
