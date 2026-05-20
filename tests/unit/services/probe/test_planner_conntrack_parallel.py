"""planner：baseline/post conntrack 与 runtime 命令规划。"""

from sdwan_desktop.services.probe.planner import (
    filter_commands_skip_keys,
    plan_baseline_conntrack_commands,
    plan_post_tcp_conntrack_commands,
    plan_post_topology_probe_commands,
    plan_runtime_probe_commands,
)


def test_baseline_conntrack_save_as() -> None:
    cmds = plan_baseline_conntrack_commands(["1.2.3.4", "1.2.3.4"])
    assert len(cmds) == 1
    assert cmds[0]["save_as"] == "diagnose:nf_conntrack baseline grep 1.2.3.4"


def test_post_tcp_conntrack_save_as() -> None:
    cmds = plan_post_tcp_conntrack_commands(["8.8.8.8"])
    assert cmds[0]["save_as"] == "diagnose:nf_conntrack grep 8.8.8.8"


def test_runtime_probe_includes_conntrack_first() -> None:
    cmds = plan_runtime_probe_commands("raisecom_msg5200b", ["8.8.8.8"])
    assert cmds[0]["save_as"] == "diagnose:nf_conntrack grep 8.8.8.8"
    save_as_set = {c["save_as"] for c in cmds}
    assert "diagnose:ipset --list" in save_as_set


def test_filter_commands_skip_keys() -> None:
    cmds = plan_post_topology_probe_commands(
        "raisecom_msg5200b",
        biz_target_ips=["1.1.1.1"],
        skip_keys={"diagnose:ipset --list"},
    )
    save_as = {c["save_as"] for c in cmds}
    assert "diagnose:ipset --list" not in save_as
