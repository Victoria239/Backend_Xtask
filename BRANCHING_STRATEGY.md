# Estrategia de Branching - Backend XTask

## Modelo: Git Flow Simplificado

```
main ─────────────────────────────────────────────► (producción)
  │
  └── develop ────────────────────────────────────► (integración)
        │         │         │
        └── feature/auth    │
                  └── feature/projects
                            └── feature/payroll
```

## Ramas Principales

| Rama | Propósito | Protegida |
|------|-----------|-----------|
| `main` | Código en producción, estable | Sí |
| `develop` | Integración de features, testing | Sí |

## Ramas de Trabajo

| Prefijo | Propósito | Ejemplo |
|---------|-----------|---------|
| `feature/` | Nueva funcionalidad | `feature/auth-service` |
| `fix/` | Corrección de bugs | `fix/cors-headers` |
| `hotfix/` | Fix urgente en producción | `hotfix/login-crash` |
| `refactor/` | Refactorización sin cambio funcional | `refactor/db-connection` |
| `docs/` | Solo documentación | `docs/api-contracts` |
| `chore/` | Configuración, CI/CD, tooling | `chore/docker-setup` |

## Flujo de Trabajo

### Crear un feature nuevo:
```bash
git checkout develop
git pull origin develop
git checkout -b feature/nombre-del-feature
# ... trabajar ...
git add .
git commit -m "feat(módulo): descripción corta"
git push origin feature/nombre-del-feature
# Crear PR hacia develop en GitHub
```

### Mergear a develop:
```bash
git checkout develop
git pull origin develop
git merge feature/nombre-del-feature
git push origin develop
git branch -d feature/nombre-del-feature
```

### Release a main:
```bash
git checkout main
git pull origin main
git merge develop
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin main --tags
```

## Convenciones de Commits

Usamos **Conventional Commits**:

```
<tipo>(<scope>): <descripción>

[cuerpo opcional]

[footer opcional]
```

### Tipos:
- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Documentación
- `refactor`: Refactorización
- `test`: Tests
- `chore`: Tareas de mantenimiento
- `ci`: Cambios en CI/CD

### Scopes (por microservicio):
- `auth`, `projects`, `employees`, `finance`, `payroll`, `kpi`, `skills`, `dashboard`, `gateway`

### Ejemplos:
```
feat(auth): implement JWT login endpoint
fix(payroll): correct salary calculation rounding
docs(api): update endpoint documentation
refactor(gateway): extract middleware to shared module
test(projects): add unit tests for CRUD operations
chore(docker): add postgres service to compose
```
