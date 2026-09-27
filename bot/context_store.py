from typing import Dict, Any


class ContextStore:
    def __init__(self):
        self.contexts: Dict[str, Dict[str, Any]] = {}

    def save(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: Dict[str, Any],
        delivered_at: str | None = None,
    ):
        key = f"{scope}:{context_id}"

        existing = self.contexts.get(key)

        # First version
        if existing is None:
            self.contexts[key] = {
                "scope": scope,
                "context_id": context_id,
                "version": version,
                "payload": payload,
                "delivered_at": delivered_at,
            }

            return "accepted", self.contexts[key]

        # Same or older version = stale
        # Official challenge expects 409 for duplicate version.
        if version <= existing["version"]:
            return "stale", existing

        # Higher version replaces the old context
        self.contexts[key] = {
            "scope": scope,
            "context_id": context_id,
            "version": version,
            "payload": payload,
            "delivered_at": delivered_at,
        }

        return "accepted", self.contexts[key]

    def get(self, scope: str, context_id: str):
        key = f"{scope}:{context_id}"
        return self.contexts.get(key)

    def all(self):
        return self.contexts

    def count_by_scope(self):
        counts = {
            "category": 0,
            "merchant": 0,
            "customer": 0,
            "trigger": 0,
        }

        for context in self.contexts.values():
            scope = context["scope"]

            if scope in counts:
                counts[scope] += 1

        return counts