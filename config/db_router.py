from typing import Any

from django.db.models import Model


class LogRouter:
    app_labels = frozenset({"audit"})
    db = "log"

    def db_for_read(self, model: type[Model], **hints: Any) -> str | None:
        return self.db if self._is_log_model(model) else None

    def db_for_write(self, model: type[Model], **hints: Any) -> str | None:
        return self.db if self._is_log_model(model) else None

    # Postgres can't enforce a foreign key across databases.
    def allow_relation(self, obj1: Model, obj2: Model, **hints: Any) -> bool | None:
        if self._is_log_model(obj1) or self._is_log_model(obj2):
            return self._is_log_model(obj1) and self._is_log_model(obj2)
        return None

    # Else `migrate --database=log` would create every app's tables there too.
    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints: Any
    ) -> bool | None:
        if app_label in self.app_labels:
            return db == self.db
        if db == self.db:
            return False
        return None

    def _is_log_model(self, model: type[Model] | Model) -> bool:
        return model._meta.app_label in self.app_labels
