"""The flag and config registries are valid, and the generated TypeScript is current."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from feature_flags.config_registry import CONFIGS, validate_config_registry
from feature_flags.registry import FLAGS, LEGACY_KEYS, NEW_UI_SHELL, FlagDefinition, validate_registry
from scripts.gen_flag_types import OUTPUT, render

CLEANUP_GRACE = timedelta(days=14)


def test_registries_are_valid():
    assert validate_registry(FLAGS) == []
    assert validate_config_registry(CONFIGS) == []


def test_the_thirteen_legacy_keys_are_unchanged():
    assert LEGACY_KEYS == {
        "social_publishing", "social_publishing.youtube", "social_publishing.tiktok", "social_publishing.instagram",
        "social_publishing.x", "video_upload", "broll_studio", "broll_studio.cutaways", "broll_studio.reels",
        "broll_studio.ai_shots", "broll_studio.reels.footage", "broll_studio.reels.footage.opus_director",
        "agent_editor",
    }


def test_every_new_flag_ships_dark():
    assert all(not flag.default for flag in FLAGS.values())


def test_no_flag_is_past_its_expiry_plus_grace():
    """The cleanup forcing function: remove the flag, or extend it in a reviewed change."""
    overdue = [key for key, flag in FLAGS.items() if flag.expires and date.today() > flag.expires + CLEANUP_GRACE]
    assert overdue == []


def _with(**changes: FlagDefinition) -> dict[str, FlagDefinition]:
    return {**FLAGS, **changes}


def test_validation_catches_bad_definitions():
    shell = FLAGS[NEW_UI_SHELL]
    cases = {
        "no expiry": replace(shell, expires=None),
        "too long": replace(shell, expires=shell.created + timedelta(days=181)),
        "public server flag": replace(shell, public=True, client=False),
        "missing parent": replace(shell, parent="nope"),
    }
    for name, definition in cases.items():
        assert validate_registry(_with(**{NEW_UI_SHELL: definition})), name
    bad_key = replace(shell, key="Bad-Key")
    assert validate_registry({**FLAGS, "Bad-Key": bad_key})


def test_cycles_across_parent_and_requires_are_rejected():
    shell = FLAGS[NEW_UI_SHELL]
    problems = validate_registry(_with(**{NEW_UI_SHELL: replace(shell, requires=("new_ui_dashboard",))}))
    assert any("cycle" in problem for problem in problems)


def test_generated_typescript_is_up_to_date():
    assert OUTPUT.read_text() == render(), "Run `cd backend && python -m scripts.gen_flag_types`"
