"""
Configuration and environment variable resolution for model-creator.
"""

import os
from pathlib import Path
from typing import Optional


def get_api_key(provider: str = "hyper3d", explicit_key: Optional[str] = None) -> Optional[str]:
    """
    Resolve API key for a given provider.
    Priority:
    1. Explicit key argument passed by user
    2. Provider-specific environment variable (e.g. HYPER3D_API_KEY, RODIN_API_KEY)
    3. Generic 3D_MODEL_API_KEY
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    provider_normalized = provider.lower().replace("-", "_")

    if provider_normalized in ("hyper3d", "rodin"):
        # Hyper3D / Rodin supported env keys
        for var_name in ["HYPER3D_API_KEY", "RODIN_API_KEY", "HYPER_3D_API_KEY"]:
            val = os.environ.get(var_name)
            if val and val.strip():
                return val.strip()

    # Fallback to generic provider pattern: <PROVIDER>_API_KEY
    generic_var = f"{provider_normalized.upper()}_API_KEY"
    val = os.environ.get(generic_var)
    if val and val.strip():
        return val.strip()

    return None


DEFAULT_TIMEOUT_SECONDS = 1200  # 20 minutes
DEFAULT_POLL_INTERVAL_MIN = 5.0
DEFAULT_POLL_INTERVAL_MAX = 30.0
