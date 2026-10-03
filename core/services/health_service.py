from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor


class HealthService:
    def is_db_ready(self) -> bool:
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except DatabaseError:
            return False
        else:
            return not plan
