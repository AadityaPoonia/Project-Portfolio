"""The query guard is the security core — these tests are the spec.

Every blocked case here is something that must NEVER reach a production
database, regardless of what credentials the connection carries.
"""
import pytest

from datadict.query_guard import validate_query, QueryBlocked

ENGINES = ["mysql", "postgres", "redshift"]


@pytest.mark.parametrize("engine", ENGINES)
class TestAllowed:
    def test_plain_select(self, engine):
        assert validate_query("SELECT id, name FROM users", engine)

    def test_select_with_where_group_limit(self, engine):
        assert validate_query(
            "SELECT status, COUNT(*) c FROM orders WHERE created_at > '2024-01-01' "
            "GROUP BY status ORDER BY c DESC LIMIT 10", engine)

    def test_information_schema(self, engine):
        assert validate_query(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'ops'", engine)

    def test_join_and_subquery(self, engine):
        assert validate_query(
            "SELECT u.id FROM users u JOIN (SELECT user_id FROM orders) o "
            "ON o.user_id = u.id", engine)

    def test_union(self, engine):
        assert validate_query("SELECT id FROM a UNION SELECT id FROM b", engine)

    def test_cte(self, engine):
        assert validate_query(
            "WITH x AS (SELECT id FROM users) SELECT * FROM x", engine)

    def test_bound_params(self, engine):
        assert validate_query("SELECT * FROM t WHERE schema_name = :schema", engine)


@pytest.mark.parametrize("engine", ENGINES)
class TestBlocked:
    @pytest.mark.parametrize("sql", [
        "INSERT INTO users (id) VALUES (1)",
        "UPDATE users SET name = 'x'",
        "DELETE FROM users",
        "DROP TABLE users",
        "TRUNCATE TABLE users",
        "CREATE TABLE t (id INT)",
        "ALTER TABLE users ADD COLUMN x INT",
        "GRANT ALL ON users TO evil",
    ])
    def test_writes_and_ddl(self, engine, sql):
        with pytest.raises(QueryBlocked):
            validate_query(sql, engine)

    def test_stacked_statements(self, engine):
        with pytest.raises(QueryBlocked):
            validate_query("SELECT 1; DELETE FROM users", engine)

    def test_stacked_selects_also_blocked(self, engine):
        with pytest.raises(QueryBlocked):
            validate_query("SELECT 1; SELECT 2", engine)

    def test_set_statement(self, engine):
        with pytest.raises(QueryBlocked):
            validate_query("SET foreign_key_checks = 0", engine)

    def test_cte_hiding_dml(self, engine):
        # data-modifying CTE (valid on postgres)
        with pytest.raises(QueryBlocked):
            validate_query(
                "WITH del AS (DELETE FROM users RETURNING id) SELECT * FROM del",
                engine)

    def test_empty_and_garbage(self, engine):
        with pytest.raises(QueryBlocked):
            validate_query("", engine)
        with pytest.raises(QueryBlocked):
            validate_query("not sql at all (", engine)


class TestEngineSpecific:
    def test_select_for_update_blocked(self):
        with pytest.raises(QueryBlocked):
            validate_query("SELECT * FROM users FOR UPDATE", "postgres")

    def test_select_into_blocked(self):
        with pytest.raises(QueryBlocked):
            validate_query("SELECT * INTO new_table FROM users", "postgres")

    def test_explain_select_allowed(self):
        assert validate_query("EXPLAIN SELECT * FROM users", "postgres")

    def test_explain_delete_blocked(self):
        with pytest.raises(QueryBlocked):
            validate_query("EXPLAIN DELETE FROM users", "postgres")

    def test_explain_analyze_blocked(self):
        # EXPLAIN ANALYZE executes the statement on Postgres — never allowed
        with pytest.raises(QueryBlocked):
            validate_query("EXPLAIN ANALYZE SELECT * FROM users", "postgres")
        with pytest.raises(QueryBlocked):
            validate_query("EXPLAIN ANALYZE DELETE FROM users", "postgres")

    def test_explain_explain_blocked(self):
        with pytest.raises(QueryBlocked):
            validate_query("EXPLAIN EXPLAIN SELECT 1", "postgres")

    def test_mysql_multi_statement_injection(self):
        with pytest.raises(QueryBlocked):
            validate_query("SELECT 1; DROP TABLE users; -- ", "mysql")

    def test_unknown_engine_rejected(self):
        with pytest.raises(QueryBlocked):
            validate_query("SELECT 1", "oracle")


class TestClassifier:
    def test_conservative_default_and_overrides(self):
        from datadict.classify import classify, values_allowed
        assert classify("email_id") == "sensitive"          # sensitive beats id-pattern
        assert classify("customer_phone_number") == "sensitive"
        assert classify("user_id") == "internal"
        assert classify("created_at") == "internal"
        assert classify("weird_business_field") == "unknown"
        assert classify("weird_business_field", {"weird_business_field": "public"}) == "public"
        assert not values_allowed("unknown")                # unknown == sensitive downstream
        assert not values_allowed("sensitive")
        assert values_allowed("internal")
