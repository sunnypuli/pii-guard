"""
Preset registry.

Usage:
    from pii_guard.presets import load_presets
    patterns = load_presets(["dpdp", "pci"])
"""

from .dpdp import DPDP_PATTERNS
from .gdpr import GDPR_PATTERNS
from .hipaa import HIPAA_PATTERNS
from .pci import PCI_PATTERNS

_REGISTRY: dict[str, dict[str, str]] = {
    "dpdp":  DPDP_PATTERNS,
    "gdpr":  GDPR_PATTERNS,
    "hipaa": HIPAA_PATTERNS,
    "pci":   PCI_PATTERNS,
}

AVAILABLE_PRESETS = list(_REGISTRY.keys())


def load_presets(names: list[str]) -> dict[str, str]:
    """Merge patterns from one or more named presets."""
    merged: dict[str, str] = {}
    for name in names:
        key = name.lower()
        if key not in _REGISTRY:
            raise ValueError(f"Unknown preset '{name}'. Available: {AVAILABLE_PRESETS}")
        merged.update(_REGISTRY[key])
    return merged
