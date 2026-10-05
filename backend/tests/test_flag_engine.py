"""Flag and config evaluation against in-memory snapshots: no database."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import pytest

from core.exceptions import CustomException
from feature_flags.config_registry import CONFIGS, FLAGS_LEGACY_PARENT_SEMANTICS, GIB, ConfigValueError
from feature_flags.context import FlagContext
from feature_flags.engine import FlagEngine
from feature_flags.evaluation import Evaluator, Snapshot, bucket, build_snapshot, in_rollout
from feature_flags.registry import (
    AGENT_EDITOR,
    BROLL_REELS,
    BROLL_STUDIO,
    FLAGS,
    NEW_UI_DASHBOARD,
    NEW_UI_EDITOR,
    NEW_UI_EDITOR_TIMELINE,
    NEW_UI_SETTINGS,
    NEW_UI_SHELL,
    REEL_EDITOR,
    REEL_EDITOR_OPUS,
)
from feature_flags.service import resolve

ALICE = FlagContext(user_id="user-alice", role="user", email="alice@example.com", plan="free")
ADMIN = FlagContext(user_id="user-admin", role="admin", email="admin@clipnera.test", plan="pro")
FULL_CHAIN = {FLAGS_LEGACY_PARENT_SEMANTICS: False}


def snapshot(flags=None, config=None, segments=None, overrides=None) -> Snapshot:
    """``flags``: key -> True/False (a plain switch) or a dict of row fields."""
    flag_rows = [
        {"key": key, **(row if isinstance(row, dict) else {"enabled": row})} for key, row in (flags or {}).items()
    ]
    config_rows = [
        {"key": key, **(row if isinstance(row, dict) else {"default_value": row})}
        for key, row in (config or {}).items()
    ]
    return build_snapshot(7, flag_rows, config_rows, segments or [], overrides or [])


def evaluate(key, ctx=ALICE, **kwargs):
    return Evaluator(snapshot(**kwargs), ctx).flag(key)


def rule(rule_id, serve=True, rollout_bps=10000, **when):
    return {"id": rule_id, "when": when, "rollout_bps": rollout_bps, "serve": serve}


def override(key, subject_id, value, subject_type="user", kind="flag", expires_at=None):
    return {"target_kind": kind, "target_key": key, "subject_type": subject_type, "subject_id": subject_id,
            "value": value, "expires_at": expires_at}


STAFF = {"key": "staff", "user_ids": ["user-listed"], "email_domains": [], "roles": ["admin"]}

# -- evaluation order (06-flags §3.5), one test per step ---------------------------------


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        evaluate("not_a_flag")


def test_kill_beats_everything_including_an_override():
    result = evaluate(AGENT_EDITOR, flags={AGENT_EDITOR: {"enabled": True, "killed": True}},
                      overrides=[override(AGENT_EDITOR, ALICE.user_id, True)])
    assert (result.value, result.reason) == (False, "KILLED")


def test_off_ancestor_beats_an_override():
    result = evaluate(NEW_UI_DASHBOARD, flags={NEW_UI_SHELL: False, NEW_UI_DASHBOARD: True},
                      overrides=[override(NEW_UI_DASHBOARD, ALICE.user_id, True)])
    assert (result.value, result.reason, result.blocked_by) == (False, "ANCESTOR_OFF", NEW_UI_SHELL)


def test_requirement_off():
    result = evaluate(NEW_UI_EDITOR, flags={NEW_UI_SHELL: True, NEW_UI_EDITOR: True})
    assert (result.value, result.reason, result.blocked_by) == (False, "REQUIREMENT_OFF", AGENT_EDITOR)
    assert evaluate(NEW_UI_EDITOR, flags={NEW_UI_SHELL: True, NEW_UI_EDITOR: True, AGENT_EDITOR: True}).value


def test_no_row_uses_the_definition_default():
    result = evaluate(NEW_UI_SHELL)
    assert (result.value, result.reason) == (FLAGS[NEW_UI_SHELL].default, "DEFAULT") == (False, "DEFAULT")


def test_targeting_off_ignores_overrides_and_rules():
    result = evaluate(NEW_UI_SHELL, flags={NEW_UI_SHELL: {"enabled": False, "rules": [rule("r_all")]}},
                      overrides=[override(NEW_UI_SHELL, ALICE.user_id, True)])
    assert (result.value, result.reason) == (False, "TARGETING_OFF")


def test_user_override_then_workspace_override():
    ctx = FlagContext(user_id="u1", workspace_id="w1")
    flags = {NEW_UI_SHELL: {"enabled": True, "rollout_bps": 0}}
    both = [override(NEW_UI_SHELL, "u1", False), override(NEW_UI_SHELL, "w1", True, "workspace")]
    assert evaluate(NEW_UI_SHELL, ctx, flags=flags, overrides=both).reason == "USER_OVERRIDE"
    result = evaluate(NEW_UI_SHELL, ctx, flags=flags, overrides=both[1:])
    assert (result.value, result.reason) == (True, "WORKSPACE_OVERRIDE")


def test_expired_override_is_ignored():
    past = datetime.utcnow() - timedelta(minutes=1)
    result = evaluate(NEW_UI_SHELL, flags={NEW_UI_SHELL: {"enabled": True, "rollout_bps": 0}},
                      overrides=[override(NEW_UI_SHELL, ALICE.user_id, True, expires_at=past)])
    assert (result.value, result.reason) == (False, "ROLLOUT_OUT")


def test_first_matching_rule_wins():
    flags = {NEW_UI_SHELL: {"enabled": True, "rollout_bps": 0, "rules": [
        rule("r_pro", plans=["pro"]), rule("r_staff", segments=["staff"], serve=False), rule("r_everyone"),
    ]}}
    assert evaluate(NEW_UI_SHELL, ADMIN, flags=flags, segments=[STAFF]).rule_id == "r_pro"
    staff_free = FlagContext(user_id="user-listed", plan="free")
    result = evaluate(NEW_UI_SHELL, staff_free, flags=flags, segments=[STAFF])
    assert (result.value, result.rule_id) == (False, "r_staff")
    assert evaluate(NEW_UI_SHELL, ALICE, flags=flags, segments=[STAFF]).rule_id == "r_everyone"


def test_segment_matches_by_role_user_or_email_domain():
    segment = {"key": "beta", "user_ids": ["u9"], "email_domains": ["partner.io"], "roles": ["admin"]}
    flags = {NEW_UI_SHELL: {"enabled": True, "rollout_bps": 0, "rules": [rule("r_beta", segments=["beta"])]}}
    for ctx, expected in (
        (FlagContext(user_id="u9"), True), (FlagContext(user_id="u1", role="admin"), True),
        (FlagContext(user_id="u2", email="Someone@Partner.io"), True), (ALICE, False),
    ):
        assert evaluate(NEW_UI_SHELL, ctx, flags=flags, segments=[segment]).value is expected


def test_rule_percentage_falls_through_when_out_of_bucket():
    flags = {NEW_UI_SHELL: {"enabled": True, "rollout_bps": 10000, "rules": [rule("r_none", serve=False,
                                                                                  rollout_bps=0)]}}
    assert evaluate(NEW_UI_SHELL, flags=flags).reason == "ROLLOUT_IN"


def test_fallthrough_rollout():
    on = evaluate(NEW_UI_SHELL, flags={NEW_UI_SHELL: {"enabled": True, "rollout_bps": 10000}})
    off = evaluate(NEW_UI_SHELL, flags={NEW_UI_SHELL: {"enabled": True, "rollout_bps": 0}})
    assert (on.value, on.reason, off.value, off.reason) == (True, "ROLLOUT_IN", False, "ROLLOUT_OUT")
    partial = evaluate(NEW_UI_SHELL, flags={NEW_UI_SHELL: {"enabled": True, "rollout_bps": 5000}})
    assert partial.bucket == bucket(NEW_UI_SHELL, ALICE.user_id)
    assert partial.value is (partial.bucket < 5000)


def test_no_unit_is_out_of_a_partial_rollout_but_in_at_100_percent():
    nobody = FlagContext()
    assert not evaluate(NEW_UI_SHELL, nobody, flags={NEW_UI_SHELL: {"enabled": True, "rollout_bps": 9999}}).value
    assert evaluate(NEW_UI_SHELL, nobody, flags={NEW_UI_SHELL: {"enabled": True}}).value


def test_signed_out_visitors_bucket_by_anon_id_and_workspace_flags_by_workspace():
    assert in_rollout(5000, "k", "anon-1") == in_rollout(5000, "k", FlagContext(anon_id="anon-1").anon_id)
    ev = Evaluator(Snapshot(), FlagContext(user_id="u", workspace_id="w"))
    assert ev._unit("workspace") == "w" and ev._unit("user") == "u"


def test_bucket_salt_reshuffles():
    flags = {NEW_UI_SHELL: {"enabled": True, "rollout_bps": 5000, "bucket_salt": "reshuffled"}}
    assert evaluate(NEW_UI_SHELL, flags=flags).bucket == bucket("reshuffled", ALICE.user_id)


def test_invalid_stored_rules_and_unknown_keys_are_skipped():
    snap = build_snapshot(1, [
        {"key": NEW_UI_SHELL, "enabled": True, "rules": [{"id": "bad id", "when": {}, "serve": True}]},
        {"key": "retired_flag", "enabled": True},
    ])
    assert snap.flags[NEW_UI_SHELL].rules == () and "retired_flag" not in snap.flags


# -- hierarchy and the two parent modes ----------------------------------------------------

OPUS_CHAIN = {BROLL_STUDIO: False, BROLL_REELS: True, REEL_EDITOR: True, REEL_EDITOR_OPUS: True}


def test_legacy_mode_is_the_default_and_keeps_one_level_parents():
    """flags.legacy_parent_semantics defaults on: today's behaviour, grandparent ignored."""
    assert CONFIGS[FLAGS_LEGACY_PARENT_SEMANTICS].default is True
    assert evaluate(BROLL_REELS, flags=OPUS_CHAIN).value is False
    assert evaluate(REEL_EDITOR, flags=OPUS_CHAIN).value is True
    assert evaluate(REEL_EDITOR_OPUS, flags=OPUS_CHAIN).value is True
    assert evaluate(REEL_EDITOR, flags={**OPUS_CHAIN, BROLL_REELS: False}).blocked_by == BROLL_REELS


def test_legacy_mode_matches_the_old_resolve_for_every_stored_combination():
    keys = [BROLL_STUDIO, BROLL_REELS, REEL_EDITOR, REEL_EDITOR_OPUS]
    for mask in range(16):
        stored = {key: bool(mask >> i & 1) for i, key in enumerate(keys)}
        old = {key: stored.get(key, False) and (FLAGS[key].parent is None or stored.get(FLAGS[key].parent, False))
               for key in keys}
        assert {key: resolve(stored)[key] for key in keys} == old


@pytest.mark.parametrize("off", [BROLL_STUDIO, BROLL_REELS, REEL_EDITOR])
def test_full_chain_mode_turns_off_every_descendant_at_any_depth(off):
    flags = {**OPUS_CHAIN, BROLL_STUDIO: True, off: False}
    result = evaluate(REEL_EDITOR_OPUS, flags=flags, config=FULL_CHAIN)
    assert (result.value, result.reason, result.blocked_by) == (False, "ANCESTOR_OFF", off)


def test_full_chain_mode_parent_at_ten_percent_limits_the_child_to_that_cohort():
    flags = {NEW_UI_SHELL: {"enabled": True, "rollout_bps": 1000}, NEW_UI_SETTINGS: True}
    for i in range(200):
        ctx = FlagContext(user_id=f"user-{i}")
        assert evaluate(NEW_UI_SETTINGS, ctx, flags=flags).value == evaluate(NEW_UI_SHELL, ctx, flags=flags).value


def test_new_flags_are_hierarchical_in_both_modes():
    flags = {NEW_UI_SHELL: False, NEW_UI_EDITOR: True, NEW_UI_EDITOR_TIMELINE: True, AGENT_EDITOR: True}
    for config in ({}, FULL_CHAIN):
        result = evaluate(NEW_UI_EDITOR_TIMELINE, flags=flags, config=config)
        assert (result.value, result.blocked_by) == (False, NEW_UI_SHELL)


# -- kill cascade and restore ----------------------------------------------------------------


@pytest.mark.parametrize("config", [{}, FULL_CHAIN])
def test_a_kill_cascades_to_descendants_and_dependants_in_both_modes(config):
    on = {BROLL_STUDIO: True, BROLL_REELS: True, REEL_EDITOR: True, REEL_EDITOR_OPUS: True,
          NEW_UI_SHELL: True, NEW_UI_EDITOR: True, AGENT_EDITOR: True, "prompt_streaming_v2": True}
    killed = {**on, BROLL_STUDIO: {"enabled": True, "killed": True}, AGENT_EDITOR: {"enabled": True, "killed": True}}
    for key in (BROLL_REELS, REEL_EDITOR, REEL_EDITOR_OPUS, NEW_UI_EDITOR, "prompt_streaming_v2"):
        assert evaluate(key, flags=on, config=config).value is True
        assert evaluate(key, flags=killed, config=config).value is False, key
    # Restoring clears only the kill: the stored targeting was never touched.
    assert all(evaluate(key, flags=on, config=config).value for key in (REEL_EDITOR_OPUS, NEW_UI_EDITOR))


def test_restore_returns_the_same_cohort():
    row = {"enabled": True, "rollout_bps": 2500}
    before = [evaluate(NEW_UI_SHELL, FlagContext(user_id=f"u{i}"), flags={NEW_UI_SHELL: row}).value for i in range(300)]
    killed = [evaluate(NEW_UI_SHELL, FlagContext(user_id=f"u{i}"), flags={NEW_UI_SHELL: {**row, "killed": True}}).value
              for i in range(300)]
    after = [evaluate(NEW_UI_SHELL, FlagContext(user_id=f"u{i}"), flags={NEW_UI_SHELL: row}).value for i in range(300)]
    assert not any(killed) and before == after and 0 < sum(before) < 300


# -- hashing -------------------------------------------------------------------------------

GOLDEN = [
    ("new_ui_shell", "user-1", 2571),
    ("new_ui_shell", "user-2", 7222),
    ("agent_editor", "user-1", 3190),
    ("broll_studio", "6f1c1b8e-2f7a-4f43-9a52-0d6e1c3b9a10", 3239),
    ("salt", "", 7643),
]


@pytest.mark.parametrize(("salt", "unit", "expected"), GOLDEN)
def test_bucket_golden_vectors(salt, unit, expected):
    """A change here silently reshuffles every rollout in production."""
    assert bucket(salt, unit) == expected


def test_raising_the_percentage_only_adds_users():
    rng = random.Random(1)
    ids = [f"u-{rng.getrandbits(64):x}" for _ in range(10000)]
    steps = [0, 1, 100, 1000, 2500, 5000, 9999, 10000]
    cohorts = [{uid for uid in ids if in_rollout(bps, "flag", uid)[0]} for bps in steps]
    assert all(smaller <= larger for smaller, larger in zip(cohorts, cohorts[1:]))
    assert cohorts[0] == set() and cohorts[-1] == set(ids)


def test_ten_percent_lands_near_ten_percent():
    share = sum(in_rollout(1000, "new_ui_shell", f"user-{i}")[0] for i in range(100_000)) / 100_000
    assert 0.095 <= share <= 0.105


def test_two_flags_at_half_overlap_by_about_a_quarter():
    ids = [f"user-{i}" for i in range(20_000)]
    both = sum(in_rollout(5000, "flag_a", uid)[0] and in_rollout(5000, "flag_b", uid)[0] for uid in ids)
    assert 0.23 <= both / len(ids) <= 0.27


# -- config --------------------------------------------------------------------------------


def config_value(key, ctx=ALICE, **kwargs):
    return Evaluator(snapshot(**kwargs), ctx).config(key)


def test_config_defaults_and_plan_defaults():
    assert config_value("agent.approval_credit_threshold").value == 60
    quota = "storage.user_library_quota_bytes"
    assert config_value(quota).value == 1 * GIB
    assert config_value(quota, ADMIN).value == 25 * GIB
    assert config_value(quota, FlagContext(plan="pro_plus")).value == 25 * GIB


def test_config_rules_overrides_and_stored_default():
    key = "agent.approval_credit_threshold"
    stored = {key: {"default_value": 80, "rules": [rule("r_pro", serve=200, plans=["pro"])]}}
    assert config_value(key, config=stored).value == 80
    assert (config_value(key, ADMIN, config=stored).value, config_value(key, ADMIN, config=stored).rule_id) == (
        200, "r_pro")
    forced = [override(key, ALICE.user_id, 5, kind="config")]
    assert config_value(key, config=stored, overrides=forced).reason == "USER_OVERRIDE"


def test_invalid_stored_config_falls_back_to_the_code_default():
    key = "agent.auto_retry_cap"
    for bad in (99, "two", True):
        assert config_value(key, config={key: bad}).value == 1


def test_global_config_ignores_rules_and_overrides():
    key = "rate_limit.default_per_minute"
    stored = {key: {"default_value": 500, "rules": [rule("r_all", serve=30)]}}
    assert config_value(key, config=stored, overrides=[override(key, ALICE.user_id, 31, kind="config")]).value == 500


def test_config_validation_rejects_out_of_range_wrong_type_and_bool_as_number():
    threshold, ratio = CONFIGS["agent.approval_credit_threshold"], CONFIGS["agent.approval_timeline_removal_ratio"]
    for bad in (-1, 10001, "60", True, 1.5):
        with pytest.raises(ConfigValueError):
            threshold.validate(bad)
    assert ratio.validate(1) == 1.0 and isinstance(ratio.validate(1), float)
    with pytest.raises(ConfigValueError):
        ratio.validate(False)
    with pytest.raises(ConfigValueError):
        CONFIGS[FLAGS_LEGACY_PARENT_SEMANTICS].validate(1)


# -- the SDK ---------------------------------------------------------------------------------


def test_require_raises_the_existing_feature_disabled_body():
    engine = FlagEngine()
    with pytest.raises(CustomException) as err:
        engine.require(AGENT_EDITOR, ctx=ALICE)
    assert (err.value.status_code, err.value.to_dict()) == (403, {
        "feature": AGENT_EDITOR, "error": "FEATURE_DISABLED", "message": "Editor is not available right now.",
    })


def test_override_forces_values_keeps_hierarchy_and_restores():
    engine = FlagEngine()
    with engine.override({NEW_UI_EDITOR: True}, config={"agent.auto_retry_cap": 0}) as forced:
        assert engine.config("agent.auto_retry_cap") == 0
        assert engine.explain(NEW_UI_EDITOR, ALICE).reason == "ANCESTOR_OFF"
        forced.set(NEW_UI_SHELL, True)
        forced.set(AGENT_EDITOR, True)
        assert engine.is_enabled(NEW_UI_EDITOR, ALICE)
        with pytest.raises(KeyError):
            forced.set("nope", True)
    assert not engine.is_enabled(NEW_UI_SHELL) and engine.config("agent.auto_retry_cap") == 1


def test_bootstrap_sends_only_client_values_and_only_public_ones_when_signed_out():
    engine = FlagEngine()
    signed_in = engine.bootstrap(ALICE, "user")
    assert REEL_EDITOR_OPUS not in signed_in.flags and NEW_UI_SHELL in signed_in.flags
    assert "rate_limit.default_per_minute" not in signed_in.config
    assert signed_in.config["storage.user_library_quota_bytes"] == 1 * GIB
    assert signed_in.poll_seconds == 60
    anonymous = engine.bootstrap(FlagContext(anon_id="a"), "anonymous")
    assert anonymous.flags == {} and anonymous.config == {}
