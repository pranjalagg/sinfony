from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pages_workflow_runs_tests_builds_and_deploys():
    text = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    for needle in (
        "branches: [main]",
        "uv run pytest",
        "node --test web/tests/*.test.js",
        "uv run python scripts/build_web.py",
        "actions/upload-pages-artifact",
        "path: web",
        "actions/deploy-pages",
        "pages: write",
        "id-token: write",
    ):
        assert needle in text, needle


def test_readme_documents_the_playground():
    text = (ROOT / "README.md").read_text()
    for needle in ("## Playground", "scripts/build_web.py", "http.server", "GitHub Actions"):
        assert needle in text, needle
