"""Network reject rule, /workspace mode, /stat fields and the per-script probe."""

from __future__ import annotations

import stat as statmod


import main
import scripts
import supervisor
from script_runtime import _ze_main
from tests.test_scripts_relay import run_to_end

UID = 4242


class FakeRunner:
    """Records shell commands; `listing` is what the chain listing command returns."""

    def __init__(self, listing: str = "", fail: tuple[str, ...] = ()) -> None:
        self.commands: list[str] = []
        self.listing = listing
        self.fail = fail

    def __call__(self, command: str) -> tuple[int, str]:
        self.commands.append(command)
        if any(command.startswith(prefix) for prefix in self.fail):
            return 1, ""
        if " list chain " in command or command.startswith("iptables -S"):
            return 0, self.listing
        return 0, ""


def only(*names: str):
    return lambda name: name if name in names else None


def test_nft_reject_rule_is_added_and_verified_from_the_listing() -> None:
    runner = FakeRunner(listing=f"chain output {{\n meta skuid {UID} reject\n}}")
    ok = supervisor.apply_script_isolation(UID, runner=runner, which=only("nft"))
    assert ok is True
    assert any(
        f"meta skuid {UID} reject" in c and c.startswith("nft add rule")
        for c in runner.commands
    )


def test_a_successful_command_whose_listing_lacks_the_rule_is_not_isolated() -> None:
    runner = FakeRunner(listing="chain output {\n}")
    assert (
        supervisor.apply_script_isolation(UID, runner=runner, which=only("nft"))
        is False
    )


def test_iptables_is_the_fallback_and_verified_too() -> None:
    runner = FakeRunner(listing=f"-A OUTPUT -m owner --uid-owner {UID} -j REJECT")
    assert (
        supervisor.apply_script_isolation(UID, runner=runner, which=only("iptables"))
        is True
    )
    assert any(
        "--uid-owner" in c and "REJECT" in c and c.startswith("iptables -I")
        for c in runner.commands
    )
    assert (
        supervisor.apply_script_isolation(
            UID, runner=FakeRunner(listing=""), which=only("iptables")
        )
        is False
    )


def test_no_firewall_tool_is_not_isolated() -> None:
    assert (
        supervisor.apply_script_isolation(UID, runner=FakeRunner(), which=only())
        is False
    )


def test_lifespan_closes_workspace_after_network_isolation(
    tmp_path, monkeypatch
) -> None:
    order: list[str] = []
    root = tmp_path / "ws"
    root.mkdir()
    root.chmod(0o777)
    monkeypatch.setattr(supervisor, "WORKSPACE_ROOT", root)
    monkeypatch.setattr(main, "WORKSPACE_ROOT", root)
    monkeypatch.setattr(main, "API_TOKEN", "")
    monkeypatch.setattr(
        supervisor, "apply_network_isolation", lambda: order.append("network") or True
    )
    real_chmod = main.os.chmod
    monkeypatch.setattr(
        main.os,
        "chmod",
        lambda path, mode: (order.append("chmod"), real_chmod(path, mode))[1],
    )
    from fastapi.testclient import TestClient

    with TestClient(main.app):
        pass
    assert order == ["network", "chmod"]
    assert statmod.S_IMODE(root.stat().st_mode) == 0o750


def test_stat_reports_script_fields(scripts_client, monkeypatch) -> None:
    monkeypatch.setattr(
        scripts, "isolation", scripts.Isolation(rule_verified=True, mode_set=True)
    )
    body = scripts_client.get("/stat", headers={"Authorization": "Bearer tok"}).json()
    assert body["scripts_busy"] is False
    assert body["scripts_isolated"] is True
    monkeypatch.setattr(
        scripts, "isolation", scripts.Isolation(rule_verified=True, mode_set=False)
    )
    body = scripts_client.get("/stat", headers={"Authorization": "Bearer tok"}).json()
    assert body["scripts_isolated"] is False


def test_probe_passes_when_workspace_is_closed_and_network_is_refused() -> None:
    def denied(_path):
        raise PermissionError

    def refused(*_a, **_k):
        raise ConnectionRefusedError

    assert _ze_main.probe("/workspace", listdir=denied, connect=refused) is None


def test_probe_breach_when_workspace_is_listable() -> None:
    def refused(*_a, **_k):
        raise OSError

    breach = _ze_main.probe("/workspace", listdir=lambda _p: ["x"], connect=refused)
    assert breach is not None and "workspace" in breach


def test_probe_breach_when_the_network_connects() -> None:
    def denied(_path):
        raise PermissionError

    class Sock:
        def close(self) -> None:
            pass

    breach = _ze_main.probe(
        "/workspace", listdir=denied, connect=lambda *_a, **_k: Sock()
    )
    assert breach is not None and "network" in breach


def test_a_probe_breach_ends_unavailable_and_clears_scripts_isolated(
    scripts_client, monkeypatch
) -> None:
    monkeypatch.setattr(scripts, "PROBE_WORKSPACE", "/")
    monkeypatch.setattr(scripts, "probe_enabled", lambda: True)
    monkeypatch.setattr(
        scripts, "isolation", scripts.Isolation(rule_verified=True, mode_set=True)
    )
    _, end = run_to_end(scripts_client, "import ze_tools as z\nz.finish(1)\n")
    assert end["status"] == "unavailable"
    assert scripts.isolation.ok is False
