from __future__ import annotations

import pytest

import skills
from content_intelligence import director, metadata_gen
from edit_engine import director as reel_director
from motion import moments
from skills import HOOKS, MOTION_GRAPHICS, STANDALONE_SHORTS, TITLES, skill, skill_block


@pytest.mark.parametrize("prompt, names", [
    (director.MAP_SYSTEM, (STANDALONE_SHORTS, HOOKS)),
    (director.DIRECTOR_SYSTEM, (STANDALONE_SHORTS, HOOKS, TITLES)),
    (director.STORY_SYSTEM, (STANDALONE_SHORTS, HOOKS, TITLES)),
    (director.CHECK_SYSTEM, (STANDALONE_SHORTS,)),
    (director.EDGES_SYSTEM, (STANDALONE_SHORTS,)),
    (reel_director.SYSTEM, (HOOKS, TITLES)),
    (metadata_gen.TITLE_SYSTEM, (TITLES,)),
    (moments.SYSTEM, (MOTION_GRAPHICS,)),
])
def test_every_director_reads_its_skills(prompt, names):
    for name in names:
        assert skill(name) in prompt


def test_skills_lose_their_front_matter():
    assert not skill(HOOKS).startswith("---") and skill(HOOKS).startswith("# Skill: hooks")


def test_a_missing_skill_is_an_error_not_a_silent_gap(monkeypatch, tmp_path):
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    skill.cache_clear()
    try:
        with pytest.raises(FileNotFoundError):
            skill_block("hooks")
    finally:
        monkeypatch.undo()
        skill.cache_clear()
