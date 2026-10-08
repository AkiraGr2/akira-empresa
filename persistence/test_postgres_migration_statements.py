import unittest

from persistence.postgres import _iter_migration_statements


class MigrationStatementNormalizationTests(unittest.TestCase):
    def test_expands_only_multi_table_enable_rls_statement(self):
        sql = """
        CREATE TABLE public.fixture (id text PRIMARY KEY);
        ALTER TABLE public.agent_tasks, public.agents, public.audit_log ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON TABLE public.agent_tasks, public.agents, public.audit_log FROM anon, authenticated;
        """
        self.assertEqual(
            list(_iter_migration_statements(sql)),
            [
                "CREATE TABLE public.fixture (id text PRIMARY KEY)",
                "ALTER TABLE public.agent_tasks ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY",
                "REVOKE ALL ON TABLE public.agent_tasks, public.agents, public.audit_log FROM anon, authenticated",
            ],
        )

    def test_leaves_valid_single_table_statement_unchanged(self):
        sql = "ALTER TABLE public.fixture ENABLE ROW LEVEL SECURITY;"
        self.assertEqual(
            list(_iter_migration_statements(sql)),
            ["ALTER TABLE public.fixture ENABLE ROW LEVEL SECURITY"],
        )


if __name__ == "__main__":
    unittest.main()
