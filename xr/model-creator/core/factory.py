"""
Provider factory and dynamic registry.
"""

from typing import Dict, Type, Optional, List, Union, Callable
from .exceptions import ProviderNotFoundError
from .config import get_api_key

_PROVIDERS: Dict[str, Type] = {}


def register_provider(name: str) -> Callable:
    """Decorator to register a provider class by identifier."""
    def decorator(cls):
        normalized = name.strip().lower()
        _PROVIDERS[normalized] = cls
        return cls
    return decorator


def register_provider_class(name: str, cls: Type):
    """Directly register a provider class by identifier."""
    normalized = name.strip().lower()
    _PROVIDERS[normalized] = cls


def list_providers() -> List[str]:
    """List all registered provider identifiers."""
    return sorted(list(_PROVIDERS.keys()))


def get_provider(
    name: str = "hyper3d",
    api_key: Optional[str] = None,
    **kwargs,
):
    """
    Instantiate and return a provider instance by name.
    Resolves API key automatically if omitted.
    """
    normalized = name.strip().lower()

    # Dynamic import to trigger registration if needed
    if normalized in ("hyper3d", "rodin"):
        import providers.hyper3d  # noqa: F401

    if normalized not in _PROVIDERS:
        available = ", ".join(list_providers()) or "none"
        raise ProviderNotFoundError(
            f"Unknown 3D model provider '{name}'. Available providers: {available}"
        )

    provider_cls = _PROVIDERS[normalized]
    resolved_key = get_api_key(provider=normalized, explicit_key=api_key)

    return provider_cls(api_key=resolved_key, **kwargs)
