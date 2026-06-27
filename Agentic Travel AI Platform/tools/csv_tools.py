"""
CSV Tools (Pandas-based)
=========================
Tools for querying the tourism trends CSV using pandas.
All operations are performed on a read-only copy of the DataFrame.
"""

import ast
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import pandas as pd
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from config import CSV_DATA_PATH, CSV_QUERY_TIMEOUT_SECONDS

# ── Load CSV once (module-level, read-only reference) ─────────────
_df = None

ALLOWED_AST_NODES = (
    ast.Expression,
    ast.Load,
    ast.Name,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Slice,
    ast.keyword,
    ast.Subscript,
    ast.Attribute,
    ast.Call,
    ast.Compare,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.IfExp,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Invert,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.BitAnd,
    ast.BitOr,
    ast.USub,
    ast.UAdd,
)

ALLOWED_NAMES = {"df", "pd", "True", "False", "None"}


def _validate_pandas_expression(pandas_code: str) -> tuple[bool, str]:
    """Validate that generated code is a single safe pandas expression."""
    if len(pandas_code) > 1200:
        return False, "Expression is too long."

    try:
        tree = ast.parse(pandas_code, mode="eval")
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            return False, f"Unsupported Python syntax: {type(node).__name__}"

        if isinstance(node, ast.Name) and node.id not in ALLOWED_NAMES:
            return False, f"Unknown name '{node.id}'. Only 'df' and 'pd' are allowed."

        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return False, "Private or dunder attributes are not allowed."

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return False, "Direct function calls are not allowed. Use df or pd methods."
            if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("_"):
                return False, "Private or dunder method calls are not allowed."

    return True, ""

def _get_dataframe() -> pd.DataFrame:
    """Lazy-load the tourism CSV into a pandas DataFrame."""
    global _df
    if _df is None:
        _df = pd.read_csv(str(CSV_DATA_PATH))
    # Always return a copy to prevent mutations
    return _df.copy()


def _evaluate_pandas_expression(pandas_code: str) -> str:
    """Evaluate a validated pandas expression against a copied DataFrame."""
    worker_df = _get_dataframe()
    allowed_globals = {"__builtins__": {}}
    allowed_locals = {"df": worker_df, "pd": pd}
    result = eval(pandas_code, allowed_globals, allowed_locals)
    return str(result)


def _execute_pandas_expression(pandas_code: str) -> tuple[bool, str]:
    """Execute a pandas expression with a timeout.

    A spawned process is very expensive on Windows because it starts a fresh
    interpreter and imports pandas for every query. For this read-only CSV
    workflow, AST validation plus a copied DataFrame gives us a practical fast
    boundary while keeping generated code away from builtins, imports, and file
    system operations.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_evaluate_pandas_expression, pandas_code)
        return True, future.result(timeout=CSV_QUERY_TIMEOUT_SECONDS)
    except TimeoutError:
        return False, f"Query exceeded {CSV_QUERY_TIMEOUT_SECONDS} seconds and was stopped."
    except Exception as e:
        return False, str(e)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# ── Input Schemas ─────────────────────────────────────────────────

class CSVQueryInput(BaseModel):
    pandas_code: str = Field(
        description=(
            "A pandas expression to run on 'df'. "
            "IMPORTANT: Use single quotes for all strings inside the code. "
            "Example: df.groupby('season')['total_trip_cost'].mean() or "
            "df.groupby(['season', 'accommodation_type']).agg("
            "avg_cost=('total_trip_cost', 'mean'), "
            "count=('trip_id', 'count'))"
        )
    )
    dummy: str = Field(description="Leave this empty string always. MUST be provided.")


# ── Tools ─────────────────────────────────────────────────────────

@tool
def get_csv_info() -> str:
    """Get information about the tourism trends CSV dataset.
    Returns column names, data types, shape, and sample rows.
    Use this FIRST before writing any pandas query to understand the data."""
    try:
        df = _get_dataframe()

        info_lines = [
            "Tourism Trends Dataset Info:",
            f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns",
            "",
            "Columns and Types:",
        ]

        for col in df.columns:
            dtype = str(df[col].dtype)
            nunique = df[col].nunique()
            sample = str(df[col].iloc[0])
            info_lines.append(f"  - {col} ({dtype}, {nunique} unique) e.g. '{sample}'")

        info_lines.append("")
        info_lines.append("Sample Rows (first 3):")
        sample_df = df.head(3).to_string(index=False)
        info_lines.append(sample_df)

        return "\n".join(info_lines)
    except Exception as e:
        return f"Error reading CSV: {e}"


@tool(args_schema=CSVQueryInput)
def query_csv(pandas_code: str, dummy: str = "") -> str:
    """Execute a pandas query on the tourism trends dataset.
    The DataFrame is available as 'df'. Write a valid pandas expression.
    Use double quotes for all column name strings.
    Returns the result and the exact pandas code that was executed.

    IMPORTANT: Only use pandas operations. No file I/O, no imports, no system calls."""
    # ── Safety: Restrict allowed operations ───────────────────────
    blocked_keywords = [
        "import ", "os.", "sys.", "subprocess", "exec(", "eval(",
        "open(", "__", "globals", "locals", "compile",
        "shutil", "pathlib", "requests", "urllib",
    ]
    code_lower = pandas_code.lower()
    for keyword in blocked_keywords:
        if keyword.lower() in code_lower:
            return f"BLOCKED: The expression contains a forbidden operation ('{keyword.strip()}'). Only pandas operations on 'df' are allowed."

    is_valid, validation_error = _validate_pandas_expression(pandas_code)
    if not is_valid:
        return f"BLOCKED: {validation_error} Only safe pandas expressions on 'df' are allowed."

    try:
        success, result = _execute_pandas_expression(pandas_code)
        if not success:
            return f"PANDAS_CODE_USED: {pandas_code}\n\nExecution Error: {result}\n\nPlease verify column names and pandas syntax."

        # Format output
        result_str = str(result)
        if len(result_str) > 3000:
            result_str = result_str[:3000] + "\n... (output truncated)"

        return (
            f"PANDAS_CODE_USED: {pandas_code}\n\n"
            f"Result:\n{result_str}"
        )
    except SyntaxError as e:
        return f"PANDAS_CODE_USED: {pandas_code}\n\nSyntax Error: {e}\n\nPlease check your pandas expression."
    except Exception as e:
        return f"PANDAS_CODE_USED: {pandas_code}\n\nExecution Error: {e}\n\nPlease verify column names and pandas syntax."
