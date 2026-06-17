"""Registration phases for PhotoshopMcpServer builtin actions.

Shared base classes (RegistrationContext, RegistrationPhase,
PhaseOutcome, RegistrationReport) and the executor
(run_registration_phases) are imported from
:mod:`dcc_mcp_core._registration` (PIP-689, core v0.18.14+).

Adapters define their own phase subclasses here for host-specific
registration steps.
"""

from __future__ import annotations

from typing import Sequence

from dcc_mcp_core._registration import (
    RegistrationContext,
    RegistrationPhase,
    run_registration_phases,  # noqa: F401 - re-exported for callers
)


class CoreBuiltinActionsPhase(RegistrationPhase):
    """Discover and register built-in skills via the server's skill catalog."""

    name = "core_builtin_actions"

    def run(self, context: RegistrationContext) -> None:
        context.server._register_core_builtin_actions(context)  # noqa: SLF001


class MetadataDrivenToolsPhase(RegistrationPhase):
    """Expose ``recipes__*`` / ``skill_refs__*`` via core metadata registration."""

    name = "metadata_driven_tools"

    def run(self, context: RegistrationContext) -> None:
        context.server._register_metadata_driven_tools(context)  # noqa: SLF001


class StrictSkillScanPhase(RegistrationPhase):
    """Run strict skill validation when enabled (fails CI on broken SKILL.md)."""

    name = "strict_skill_scan"
    fatal_exceptions = (ValueError,)

    def run(self, context: RegistrationContext) -> None:
        context.server._run_strict_skill_scan_if_enabled(  # noqa: SLF001
            context.strict_scan,
            context.extra_skill_paths,
            context.include_bundled,
        )


class CapabilityManifestPhase(RegistrationPhase):
    """Register the capability manifest tool for gateway aggregation."""

    name = "capability_manifest"

    def run(self, context: RegistrationContext) -> None:
        context.server._register_capability_manifest_tool()  # noqa: SLF001


class ResourcesPhase(RegistrationPhase):
    """Attach resources (context snapshots, etc.) to the server."""

    name = "resources"

    def run(self, context: RegistrationContext) -> None:
        context.server._attach_resources()  # noqa: SLF001


def default_registration_phases() -> Sequence[RegistrationPhase]:
    """Return the default ordered registration phases for Photoshop."""
    return (
        CoreBuiltinActionsPhase(),
        MetadataDrivenToolsPhase(),
        StrictSkillScanPhase(),
        CapabilityManifestPhase(),
        ResourcesPhase(),
    )
