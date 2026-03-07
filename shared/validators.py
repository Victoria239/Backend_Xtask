"""Chain of Responsibility Pattern — Composable validation pipelines.

Each validator checks one condition and either passes to the next
or raises a ValidationException. Validators are chained explicitly.

Usage:
    chain = (
        StatusTransitionValidator(allowed={"pending": ["approved", "rejected"]})
        .then(PositiveAmountValidator(field="base_salary"))
    )
    await chain.validate(data)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shared.exceptions import ValidationException


class Validator(ABC):
    """Base link in a validation chain."""

    def __init__(self):
        self._next: Validator | None = None

    def then(self, next_validator: Validator) -> Validator:
        """Chain another validator after this one. Returns the next validator for fluent API."""
        self._next = next_validator
        return self._next

    async def validate(self, data: dict[str, Any]) -> None:
        """Run this validator, then delegate to the next in the chain."""
        await self._check(data)
        if self._next:
            await self._next.validate(data)

    @abstractmethod
    async def _check(self, data: dict[str, Any]) -> None:
        """Perform the actual validation. Raise ValidationException on failure."""
        ...


# ─── Concrete validators ──────────────────────────────────────────

class RequiredFieldsValidator(Validator):
    """Ensures specified fields are present and non-None."""

    def __init__(self, fields: list[str]):
        super().__init__()
        self._fields = fields

    async def _check(self, data: dict[str, Any]) -> None:
        missing = [f for f in self._fields if f not in data or data[f] is None]
        if missing:
            raise ValidationException(f"Missing required fields: {', '.join(missing)}")


class PositiveAmountValidator(Validator):
    """Ensures a numeric field is positive."""

    def __init__(self, field: str):
        super().__init__()
        self._field = field

    async def _check(self, data: dict[str, Any]) -> None:
        value = data.get(self._field)
        if value is not None and value < 0:
            raise ValidationException(f"Field '{self._field}' must be a positive number")


class StatusTransitionValidator(Validator):
    """Ensures a status transition is allowed according to a transition map."""

    def __init__(self, transitions: dict[str, list[str]]):
        super().__init__()
        self._transitions = transitions

    async def _check(self, data: dict[str, Any]) -> None:
        current = data.get("current_status")
        new = data.get("new_status")
        if current is None or new is None:
            return
        allowed = self._transitions.get(current, [])
        if new not in allowed:
            raise ValidationException(
                f"Cannot transition from '{current}' to '{new}'. "
                f"Allowed: {allowed}"
            )


class EntityExistsValidator(Validator):
    """Ensures an entity exists in the database via a lookup callable."""

    def __init__(self, lookup_key: str, lookup_fn, entity_name: str = "Entity"):
        super().__init__()
        self._lookup_key = lookup_key
        self._lookup_fn = lookup_fn
        self._entity_name = entity_name

    async def _check(self, data: dict[str, Any]) -> None:
        entity_id = data.get(self._lookup_key)
        if entity_id is None:
            return
        entity = await self._lookup_fn(entity_id)
        if not entity:
            raise ValidationException(f"{self._entity_name} with id '{entity_id}' not found")


# ─── Helper to build chains quickly ──────────────────────────────

def build_chain(*validators: Validator) -> Validator:
    """Link validators in order and return the head of the chain."""
    if not validators:
        raise ValueError("At least one validator is required")
    head = validators[0]
    current = head
    for v in validators[1:]:
        current.then(v)
        current = v
    return head
