"""Unit of Work pattern for atomic multi-repository transactions.

Usage:
    async with UnitOfWork() as uow:
        project = await uow.projects.create({...})
        employee = await uow.employees.create({...})
        await uow.commit()
        # If anything fails, rollback is automatic

For simple single-repo operations, the existing get_db dependency
with auto-commit is still fine. Use UoW when a service method needs
to coordinate writes across multiple repositories atomically.
"""

from shared.database import async_session, _get_session_factory


class UnitOfWork:
    """Manages a single database session shared across repositories.

    Repositories are created lazily on first access to avoid
    importing all repo classes when only one is needed.

    Args:
        service_name: Optional service name to use a per-schema session.
                      If None, uses the default shared session (all schemas).
    """

    def __init__(self, service_name: str | None = None):
        self._session = None
        self._repos: dict = {}
        self._service_name = service_name

    async def __aenter__(self):
        if self._service_name:
            factory = _get_session_factory(self._service_name)
            self._session = factory()
        else:
            self._session = async_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        await self._session.close()

    @property
    def session(self):
        return self._session

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()

    # ─── Lazy repository accessors ───────────────────────────

    def _get_repo(self, key: str, repo_cls):
        if key not in self._repos:
            self._repos[key] = repo_cls(self._session)
        return self._repos[key]

    @property
    def users(self):
        from services.auth.repository import UserRepository
        return self._get_repo("users", UserRepository)

    @property
    def projects(self):
        from services.projects.repository import ProjectRepository
        return self._get_repo("projects", ProjectRepository)

    @property
    def employees(self):
        from services.employees.repository import EmployeeRepository
        return self._get_repo("employees", EmployeeRepository)

    @property
    def budgets(self):
        from services.finance.repository import BudgetRepository
        return self._get_repo("budgets", BudgetRepository)

    @property
    def invoices(self):
        from services.finance.repository import InvoiceRepository
        return self._get_repo("invoices", InvoiceRepository)

    @property
    def payrolls(self):
        from services.payroll.repository import PayrollRepository
        return self._get_repo("payrolls", PayrollRepository)

    @property
    def kpis(self):
        from services.kpis.repository import KpiRepository
        return self._get_repo("kpis", KpiRepository)

    @property
    def skills(self):
        from services.skills.repository import SkillRepository
        return self._get_repo("skills", SkillRepository)

    @property
    def layouts(self):
        from services.dashboard.repository import LayoutRepository
        return self._get_repo("layouts", LayoutRepository)

    @property
    def widgets(self):
        from services.dashboard.repository import WidgetRepository
        return self._get_repo("widgets", WidgetRepository)
