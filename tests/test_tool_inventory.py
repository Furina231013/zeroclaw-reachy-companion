from __future__ import annotations

import yaml

from zeroclaw_reachy_companion.reachy import ReachyClient
from zeroclaw_reachy_companion.tools import create_tool_registry


def test_phase12_tool_inventory_matches_scenario_manifest() -> None:
    manifest = yaml.safe_load(open("scenarios/reachy_phase12.yaml", encoding="utf-8"))
    expected = set(manifest["tool_inventory"]["migrated_phase12"])
    registry = create_tool_registry(ReachyClient(mode="dry_run"))
    assert expected.issubset(set(registry.names))


def test_excluded_tools_are_not_registered() -> None:
    manifest = yaml.safe_load(open("scenarios/reachy_phase12.yaml", encoding="utf-8"))
    excluded = set(manifest["tool_inventory"]["intentionally_excluded_phase12"])
    registry = create_tool_registry(ReachyClient(mode="dry_run"))
    assert excluded.isdisjoint(set(registry.names))

