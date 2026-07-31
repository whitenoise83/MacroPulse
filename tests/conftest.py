import sys
import types

try:
    import duckdb  # noqa: F401
except ModuleNotFoundError:
    duckdb_stub = types.ModuleType("duckdb")
    duckdb_stub.DuckDBPyConnection = object
    duckdb_stub.connect = lambda *args, **kwargs: None
    sys.modules["duckdb"] = duckdb_stub
