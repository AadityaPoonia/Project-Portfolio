from tools.csv_tools import _execute_pandas_expression, _validate_pandas_expression
from tools.sql_tools import _is_readonly_query


def test_csv_validator_allows_dataframe_expression():
    valid, error = _validate_pandas_expression("df.groupby('season')['total_trip_cost'].mean()")

    assert valid
    assert error == ""


def test_csv_validator_blocks_direct_function_call():
    valid, error = _validate_pandas_expression("open('secret.txt').read()")

    assert not valid
    assert "Direct function calls" in error or "Unknown name" in error


def test_csv_executor_handles_groupby_aggregation():
    expression = (
        "df.groupby(['season', 'accommodation_type']).agg("
        "average_nightly_rate=('accommodation_cost_per_night', 'mean'), "
        "average_total_trip_cost=('total_trip_cost', 'mean'), "
        "trip_count=('trip_id', 'count'), "
        "average_trip_duration=('trip_duration_days', 'mean'))"
        ".sort_values('average_total_trip_cost', ascending=False).head(8).round(2)"
    )

    success, result = _execute_pandas_expression(expression)

    assert success
    assert "average_total_trip_cost" in result
    assert "Summer" in result


def test_sql_guard_allows_select():
    assert _is_readonly_query("SELECT * FROM flights LIMIT 5")


def test_sql_guard_blocks_delete():
    assert not _is_readonly_query("DELETE FROM flights")


def test_sql_guard_blocks_non_select_shape():
    assert not _is_readonly_query("PRAGMA table_info(flights)")
