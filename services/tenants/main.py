"""Tenants microservice — standalone entry point.

Incluye el router CRUD básico (tenants) más el admin_router (admin dashboard
de tenants introducido en P-03).
"""
from shared.service_app import create_service_app
from services.tenants.router import router
from services.tenants.admin_router import router as admin_router

app = create_service_app(
    title="XTask Tenants Service",
    service_name="tenants-service",
    prefix="/api/tenants",
)

app.include_router(router, prefix="/api/tenants", tags=["Tenants"])
app.include_router(admin_router, prefix="/api/tenants", tags=["Tenants Admin"])
