import re
from pathlib import Path

from src.provider_support import PACKAGED_PROVIDER_CAPABILITIES, PACKAGED_PROVIDER_REQUIREMENTS


def test_packaged_provider_dependencies_are_in_production_requirements():
    repo_root = Path(__file__).resolve().parents[2]
    requirements = {
        line.strip().lower().replace("_", "-").split("==", 1)[0].split(">=", 1)[0]
        for line in (repo_root / "backend" / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    missing = {
        provider: package
        for provider, package in PACKAGED_PROVIDER_REQUIREMENTS.items()
        if package.lower().replace("_", "-") not in requirements
    }

    assert missing == {}


def test_frontend_provider_options_exist_in_backend_provider_matrix():
    repo_root = Path(__file__).resolve().parents[2]
    frontend_source = (repo_root / "frontend" / "src" / "utils" / "modelProviderOptions.ts").read_text()
    frontend_providers = set(re.findall(r"value: '([a-z0-9_]+)'", frontend_source))

    assert frontend_providers == set(PACKAGED_PROVIDER_CAPABILITIES)
