import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT / "migrations" / "versions"


def _literal_revision(path: Path) -> str:
    module = ast.parse(path.read_text())
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "revision":
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "revision":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    raise AssertionError(f"missing literal revision in {path}")


def test_alembic_revision_ids_fit_default_version_table_width() -> None:
    too_long = {
        path.name: revision
        for path in VERSIONS_DIR.glob("*.py")
        if path.name != "__init__.py"
        if (revision := _literal_revision(path)) and len(revision) > 32
    }

    assert too_long == {}
