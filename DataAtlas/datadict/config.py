"""Configuration: sources.yml (what to extract) + .env (credentials).

Credentials never live in sources.yml — each source names an env prefix,
and the actual secrets come from environment variables / .env, matching
the pattern used across the rest of the analytics stack.
"""
import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv


@dataclass
class SourceConfig:
    name: str
    engine: str                      # mysql | postgres | redshift
    env_prefix: str                  # e.g. OPS_DB -> OPS_DB_HOST, OPS_DB_USER, ...
    schemas: list[str]
    table_allowlist: dict[str, list[str] | None] = field(default_factory=dict)
    #                ^ schema -> list of tables, or None meaning "all tables in schema"
    column_overrides: dict[str, str] = field(default_factory=dict)
    #                ^ lowercase column name -> tier, human-reviewed
    sample_size: int = 100
    row_cap: int = 10_000
    timeout_s: int = 60

    def credentials(self) -> dict:
        p = self.env_prefix
        missing = [v for v in (f"{p}_HOST", f"{p}_USER", f"{p}_PASSWORD", f"{p}_NAME")
                   if not os.environ.get(v)]
        if missing:
            raise SystemExit(f"source {self.name!r}: missing env vars {missing}")
        return {
            "host": os.environ[f"{p}_HOST"],
            "port": int(os.environ.get(f"{p}_PORT",
                                       "3306" if self.engine == "mysql" else "5439" if self.engine == "redshift" else "5432")),
            "user": os.environ[f"{p}_USER"],
            "password": os.environ[f"{p}_PASSWORD"],
            "database": os.environ[f"{p}_NAME"],
        }


@dataclass
class AppConfig:
    sources: list[SourceConfig]
    sandbox_url: str
    audit_log_path: str


def load_config(path: str = "sources.yml") -> AppConfig:
    load_dotenv()
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    sources = []
    for s in raw.get("sources", []):
        sources.append(SourceConfig(
            name=s["name"],
            engine=s["engine"],
            env_prefix=s["env_prefix"],
            schemas=s["schemas"],
            table_allowlist=s.get("table_allowlist", {}),
            column_overrides={k.lower(): v for k, v in (s.get("column_overrides") or {}).items()},
            sample_size=s.get("sample_size", 100),
            row_cap=s.get("row_cap", 10_000),
            timeout_s=s.get("timeout_s", 60),
        ))

    sandbox_url = os.environ.get("SANDBOX_DB_URL") or raw.get("sandbox_url")
    if not sandbox_url:
        raise SystemExit("SANDBOX_DB_URL env var (or sandbox_url in sources.yml) is required")

    return AppConfig(
        sources=sources,
        sandbox_url=sandbox_url,
        audit_log_path=raw.get("audit_log_path", "logs/audit.jsonl"),
    )
