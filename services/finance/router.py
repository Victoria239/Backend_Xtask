"""Finance service - API routes.

Handles multiple frontend endpoint patterns:
- /api/finances/budgets/*
- /api/presupuestos/*
- /api/finances/invoices/*
- /api/facturacion/*
- /api/finanzas/recursos/*
- /api/finances/reports/*
- /api/finances/audits/*
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# PRESUPUESTOS / BUDGETS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finances/budgets")
async def list_budgets(user_id: int = Depends(get_current_user_id)):
    # TODO: Implement in feature/finance-service
    return []


@router.get("/api/finances/budgets/{budget_id}")
async def get_budget(budget_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": budget_id}


@router.post("/api/finances/budgets")
async def create_budget(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/finances/budgets/{budget_id}")
async def update_budget(budget_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": budget_id}


@router.delete("/api/finances/budgets/{budget_id}")
async def delete_budget(budget_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": budget_id}


@router.get("/api/finances/budgets/{budget_id}/execution")
async def get_budget_execution(budget_id: int, user_id: int = Depends(get_current_user_id)):
    return {}


@router.post("/api/finances/budgets/{budget_id}/validate-expense")
async def validate_expense(budget_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"valid": True}


# ─── /api/presupuestos ───────────────────────────────────────

@router.get("/api/presupuestos")
async def list_presupuestos(
    organizationId: int | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return []


@router.get("/api/presupuestos/{presupuesto_id}")
async def get_presupuesto(presupuesto_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": presupuesto_id}


@router.post("/api/presupuestos")
async def create_presupuesto(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/presupuestos/{presupuesto_id}")
async def update_presupuesto(presupuesto_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": presupuesto_id}


@router.post("/api/presupuestos/{presupuesto_id}/gastos")
async def registrar_gasto(presupuesto_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": presupuesto_id}


@router.post("/api/presupuestos/importar")
async def importar_presupuestos(data: dict, user_id: int = Depends(get_current_user_id)):
    return []


# ═══════════════════════════════════════════════════════════════
# FACTURACIÓN / INVOICES
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finances/invoices")
async def list_invoices(user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/finances/invoices/overdue")
async def get_overdue_invoices(
    daysThreshold: int = Query(7),
    user_id: int = Depends(get_current_user_id),
):
    return []


@router.get("/api/finances/invoices/{invoice_id}")
async def get_invoice(invoice_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": invoice_id}


@router.post("/api/finances/invoices")
async def create_invoice(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/finances/invoices/{invoice_id}")
async def update_invoice(invoice_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": invoice_id}


@router.patch("/api/finances/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": invoice_id}


@router.post("/api/finances/invoices/{invoice_id}/payment")
async def record_invoice_payment(invoice_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


@router.get("/api/finances/invoices/{invoice_id}/items")
async def get_invoice_items(invoice_id: int, user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/finances/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(invoice_id: int, user_id: int = Depends(get_current_user_id)):
    return {"url": ""}


@router.post("/api/finances/invoices/{invoice_id}/send-email")
async def send_invoice_email(invoice_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


# ─── /api/facturacion ────────────────────────────────────────

@router.get("/api/facturacion/{proyecto_id}")
async def list_facturas_proyecto(
    proyecto_id: int,
    estado: str | None = Query(None),
    cliente: str | None = Query(None),
    fechaDesde: str | None = Query(None),
    fechaHasta: str | None = Query(None),
    busqueda: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return []


@router.get("/api/facturacion/{proyecto_id}/indicadores")
async def get_indicadores_facturacion(proyecto_id: int, user_id: int = Depends(get_current_user_id)):
    return {}


@router.get("/api/facturacion/detalle/{factura_id}")
async def get_factura_detalle(factura_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": factura_id}


@router.post("/api/facturacion")
async def registrar_factura(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/facturacion/{factura_id}/estado")
async def update_factura_estado(factura_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": factura_id}


@router.delete("/api/facturacion/{factura_id}")
async def delete_factura(factura_id: int, user_id: int = Depends(get_current_user_id)):
    return None


# ═══════════════════════════════════════════════════════════════
# RECURSOS FINANCIEROS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finanzas/recursos/{presupuesto_id}")
async def list_recursos(presupuesto_id: int, user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/finanzas/recursos/{presupuesto_id}/resumen")
async def get_resumen_costos(presupuesto_id: int, user_id: int = Depends(get_current_user_id)):
    return {}


@router.post("/api/finanzas/recursos")
async def create_recurso(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/finanzas/recursos/{recurso_id}")
async def update_recurso(recurso_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": recurso_id}


@router.delete("/api/finanzas/recursos/{recurso_id}")
async def delete_recurso(recurso_id: int, user_id: int = Depends(get_current_user_id)):
    return None


# ═══════════════════════════════════════════════════════════════
# INFORMES FINANCIEROS / REPORTS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finances/reports")
async def list_reports(user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/finances/reports/{report_id}")
async def get_report(report_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": report_id}


@router.post("/api/finances/reports")
async def create_report(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/finances/reports/{report_id}")
async def update_report(report_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": report_id}


@router.post("/api/finances/reports/balance-sheet")
async def generate_balance_sheet(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}


@router.post("/api/finances/reports/income-statement")
async def generate_income_statement(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}


@router.post("/api/finances/reports/cash-flow")
async def generate_cash_flow(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}


@router.get("/api/finances/reports/{report_id}/pdf")
async def get_report_pdf(report_id: int, user_id: int = Depends(get_current_user_id)):
    return {"url": ""}


@router.get("/api/finances/reports/{report_id}/excel")
async def get_report_excel(report_id: int, user_id: int = Depends(get_current_user_id)):
    return {"url": ""}


# ═══════════════════════════════════════════════════════════════
# AUDITORÍA FINANCIERA
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finances/audits")
async def list_audits(user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/finances/audits/{audit_id}")
async def get_audit(audit_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": audit_id}


@router.get("/api/finances/audits/history/{entity_type}/{entity_id}")
async def get_entity_history(entity_type: str, entity_id: int, user_id: int = Depends(get_current_user_id)):
    return []


@router.post("/api/finances/audits/detect-irregularities")
async def detect_irregularities(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}


@router.get("/api/finances/audits/verify-compliance/transaction/{transaction_id}")
async def verify_compliance(transaction_id: int, user_id: int = Depends(get_current_user_id)):
    return {}


@router.post("/api/finances/audits/report")
async def generate_audit_report(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}
