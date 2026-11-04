import json
from pathlib import Path

from app.main import app


def export_openapi() -> None:
    """Generate and write the FastAPI OpenAPI schema to apps/web/openapi.json."""
    openapi_schema = app.openapi()

    # Find the repository apps/web directory
    # Current file: apps/api/app/scripts/export_openapi.py
    # parents[0] = scripts, parents[1] = app, parents[2] = api, parents[3] = apps, parents[4] = brandmuse
    repo_root = Path(__file__).resolve().parents[3].parent
    output_path = repo_root / "apps" / "web" / "openapi.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    export_openapi()
