"""Every feature flag, declared once. Python is the single source of truth.

A flag must be declared here before it can be read or set, so a typo fails
loudly instead of silently reading as "off". The database holds only state
(targeting, kills, overrides); a flag can never exist without the code that
reads it. ``frontend/lib/flags/registry.gen.ts`` is generated from this file
by ``scripts/gen_flag_types.py``, and a test fails when it is out of date.

New flags ship dark (``default=False``) and are rolled out from the admin API.
A flag is on only while its parent and everything it ``requires`` are on; see
``evaluation.py`` for the order and for the legacy one-level parent switch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

FlagKind = Literal["release", "ops", "experiment"]
#   release:    temporary; ships a new thing; has an expiry; removed after 100%
#   ops:        permanent kill switch / cost switch
#   experiment: temporary A/B, compared by cohort; has an expiry
LiveUpdate = Literal["immediate", "next_navigation"]
BucketBy = Literal["user", "workspace"]

KEY_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")
KEY_MAX_LENGTH = 100
MAX_LIFETIME = timedelta(days=180)

FRONTEND_LEAD = "frontend-lead"
BACKEND_LEAD = "backend-lead"
PRODUCT_OWNER = "product-owner"


@dataclass(frozen=True)
class FlagDefinition:
    key: str
    label: str
    description: str
    owner: str
    kind: FlagKind
    created: date
    default: bool = False                      # value when no DB row exists
    parent: str | None = None                  # off parent => off child, at any depth
    requires: tuple[str, ...] = ()             # non-hierarchical dependencies
    bucket_by: BucketBy = "user"
    client: bool = True                        # sent in the bootstrap payload
    public: bool = False                       # evaluated for signed-out visitors
    live_update: LiveUpdate = "immediate"
    expires: date | None = None                # required for release/experiment


# -- the 13 keys that existed before the revamp (names never change) ---------------------

SOCIAL_PUBLISHING = "social_publishing"
VIDEO_UPLOAD = "video_upload"
BROLL_STUDIO = "broll_studio"
BROLL_CUTAWAYS = f"{BROLL_STUDIO}.cutaways"
BROLL_REELS = f"{BROLL_STUDIO}.reels"
BROLL_AI_SHOTS = f"{BROLL_STUDIO}.ai_shots"
REEL_EDITOR = f"{BROLL_REELS}.footage"
REEL_EDITOR_OPUS = f"{REEL_EDITOR}.opus_director"
AGENT_EDITOR = "agent_editor"
REFERRAL_PROGRAM = "referral_program"

# -- revamp flags (docs/revamp/04-architecture.md §4) ------------------------------------

NEW_UI_SHELL = "new_ui_shell"
NEW_UI_AUTH = "new_ui_auth"
NEW_UI_DASHBOARD = "new_ui_dashboard"
NEW_UI_EDITOR = "new_ui_editor"
NEW_UI_EDITOR_TIMELINE = "new_ui_editor_timeline"
NEW_UI_EXPORT = "new_ui_export"
NEW_UI_SETTINGS = "new_ui_settings"
NEW_UI_REELS = "new_ui_reels"
NEW_UI_ADMIN = "new_ui_admin"
PROMPT_STREAMING_V2 = "prompt_streaming_v2"
BROLL_PLATFORM_LIBRARY = "broll_platform_library"
BROLL_USER_LIBRARY = "broll_user_library"
AUTH_COOKIE_ENFORCE = "auth_cookie_enforce"


def social_platform_flag(platform: str) -> str:
    return f"{SOCIAL_PUBLISHING}.{platform}"


_SOCIAL_CREATED = date(2026, 9, 26)
_BROLL_CREATED = date(2026, 9, 26)
_REVAMP_CREATED = date(2026, 10, 3)
_REVAMP_EXPIRES = date(2027, 3, 31)


def _social(platform: str, label: str, description: str) -> FlagDefinition:
    return FlagDefinition(
        social_platform_flag(platform), label, description, BACKEND_LEAD, "ops", _SOCIAL_CREATED,
        parent=SOCIAL_PUBLISHING,
    )


def _new_ui(key: str, label: str, description: str, parent: str | None = NEW_UI_SHELL, **extra) -> FlagDefinition:
    return FlagDefinition(
        key, label, description, FRONTEND_LEAD, "release", _REVAMP_CREATED,
        parent=parent, live_update="next_navigation", expires=_REVAMP_EXPIRES, **extra,
    )


_LEGACY_DEFINITIONS = (
    FlagDefinition(
        SOCIAL_PUBLISHING,
        "Connected publishing platforms",
        "Users can connect social accounts and publish or schedule clips. Turning this off "
        "pauses publishing; disconnects and platform deletion requests keep working.",
        BACKEND_LEAD, "ops", _SOCIAL_CREATED,
    ),
    _social("youtube", "YouTube Shorts", "Connect and publish to YouTube."),
    _social("tiktok", "TikTok", "Connect and publish to TikTok."),
    _social("instagram", "Instagram Reels", "Connect and publish to Instagram."),
    _social("x", "X", "Connect and publish to X. Every post is billed by X."),
    FlagDefinition(
        VIDEO_UPLOAD,
        "Video upload",
        "Users can upload a video file from their device instead of pasting a YouTube link.",
        BACKEND_LEAD, "ops", _SOCIAL_CREATED,
    ),
    FlagDefinition(
        BROLL_STUDIO,
        "B-Roll Studio",
        "Main switch for B-roll features. The admin B-roll library stays available so it can be filled "
        "before launch.",
        PRODUCT_OWNER, "ops", _BROLL_CREATED,
    ),
    FlagDefinition(
        BROLL_CUTAWAYS,
        "B-roll cutaways on clips",
        "The AI adds stock cutaways to generated clips (5 credits per clip that gets them); users can swap "
        "or remove them in the editor. Clips already planned keep their B-roll when this is turned off.",
        PRODUCT_OWNER, "release", _BROLL_CREATED, parent=BROLL_STUDIO, expires=date(2027, 1, 31),
    ),
    FlagDefinition(
        BROLL_REELS,
        "Reels from images",
        "Users build a reel from their photos and a script or topic.",
        PRODUCT_OWNER, "release", _BROLL_CREATED, parent=BROLL_STUDIO, expires=date(2027, 1, 31),
    ),
    FlagDefinition(
        BROLL_AI_SHOTS,
        # The Pro limit is enforced by entitlements (broll/generation.py), not by this flag. 06-flags §3.7
        # drops "(Pro)" from the label; it stays until phase 2 so the legacy admin page does not change.
        "AI-generated shots (Pro)",
        "Pro users can generate a scene or cutaway with Veo (120 credits). Needs Veo quota on the Gemini key.",
        PRODUCT_OWNER, "ops", _BROLL_CREATED, parent=BROLL_STUDIO,
    ),
    FlagDefinition(
        REEL_EDITOR,
        "Reels from raw footage",
        "Users upload raw videos, photos, an optional script and voiceover; the AI plans and renders a finished reel.",
        PRODUCT_OWNER, "release", _BROLL_CREATED, parent=BROLL_REELS, expires=date(2027, 1, 31),
    ),
    FlagDefinition(
        REEL_EDITOR_OPUS,
        "Opus director for Pro footage reels",
        "Pro footage reels are planned by Claude Opus 5.5 instead of Sonnet 5. Opus costs more, so these reels "
        "cost 1.5x the credits while this is on.",
        BACKEND_LEAD, "ops", _BROLL_CREATED, parent=REEL_EDITOR, client=False,
    ),
    FlagDefinition(
        AGENT_EDITOR,
        "Editor",
        "The multi-track editor: users build and change a video on a timeline, by hand and with the agent.",
        BACKEND_LEAD, "release", _REVAMP_CREATED, expires=_REVAMP_EXPIRES,
    ),
    FlagDefinition(
        REFERRAL_PROGRAM,
        "Referral program",
        "Users share a referral code and earn bonus credits when the people they bring in buy Pro and process "
        "a video in time. Turning this off stops new codes from being accepted; referrals already running finish "
        "under their own rules.",
    ),
)

_REVAMP_DEFINITIONS = (
    _new_ui(NEW_UI_SHELL, "New UI: shell", "New shell, navigation and prompt bar. Parent of every new_ui_* flag.",
            parent=None),
    _new_ui(NEW_UI_AUTH, "New UI: sign-in and landing",
            "The landing page, /editor, /login and /signup, with the prompt carried through sign-in."),
    _new_ui(NEW_UI_DASHBOARD, "New UI: dashboard",
            "Home, projects, upload, the project progress page and analytics."),
    _new_ui(NEW_UI_EDITOR, "New UI: editor",
            "The editor and clip studio URLs, with the prompt bar, plan and progress. A session in progress is "
            "never swapped.", requires=(AGENT_EDITOR,)),
    _new_ui(NEW_UI_EDITOR_TIMELINE, "New UI: editor timeline", "The new preview, timeline and versions.",
            parent=NEW_UI_EDITOR),
    _new_ui(NEW_UI_EXPORT, "New UI: export", "Export dialog, share and scheduler."),
    _new_ui(NEW_UI_SETTINGS, "New UI: settings", "Settings, billing, usage and brand kit."),
    _new_ui(NEW_UI_REELS, "New UI: reels", "The /dashboard/reels pages."),
    FlagDefinition(
        NEW_UI_ADMIN, "New UI: admin console",
        "The admin console, flags console and B-roll curation. Admin-only by nature: target the staff "
        "segment, never a percentage.",
        BACKEND_LEAD, "release", _REVAMP_CREATED, live_update="next_navigation", expires=_REVAMP_EXPIRES,
    ),
    FlagDefinition(
        PROMPT_STREAMING_V2, "Prompt streaming v2",
        "The run event stream v2. Evaluated at run start and pinned to the run.",
        BACKEND_LEAD, "release", _REVAMP_CREATED, requires=(AGENT_EDITOR,), live_update="next_navigation",
        expires=date(2027, 1, 31),
    ),
    FlagDefinition(
        BROLL_PLATFORM_LIBRARY, "B-roll: Clipnera library",
        "Users browse and insert shots from the curated library. The admin library is unaffected.",
        PRODUCT_OWNER, "release", _REVAMP_CREATED, parent=BROLL_STUDIO, expires=_REVAMP_EXPIRES,
    ),
    FlagDefinition(
        BROLL_USER_LIBRARY, "B-roll: personal uploads",
        "Users upload their own B-roll, within the storage.user_library_quota_bytes quota.",
        PRODUCT_OWNER, "release", _REVAMP_CREATED, parent=BROLL_STUDIO, expires=_REVAMP_EXPIRES,
    ),
    FlagDefinition(
        AUTH_COOKIE_ENFORCE, "Cookie auth enforced",
        "Auth release C: middleware redirects and bearer tokens are refused from browsers.",
        BACKEND_LEAD, "release", _REVAMP_CREATED, live_update="next_navigation", expires=_REVAMP_EXPIRES,
    ),
)

FLAGS: dict[str, FlagDefinition] = {flag.key: flag for flag in (*_LEGACY_DEFINITIONS, *_REVAMP_DEFINITIONS)}

# The keys served by GET /features and the legacy admin routes before the revamp.
LEGACY_KEYS: frozenset[str] = frozenset(flag.key for flag in _LEGACY_DEFINITIONS)


def ancestors(key: str) -> tuple[str, ...]:
    """Parent, grandparent, ... nearest first."""
    chain: list[str] = []
    parent = FLAGS[key].parent
    while parent is not None:
        chain.append(parent)
        parent = FLAGS[parent].parent
    return tuple(chain)


def children(key: str) -> list[str]:
    return [flag.key for flag in FLAGS.values() if flag.parent == key]


def dependants(key: str) -> list[str]:
    return [flag.key for flag in FLAGS.values() if key in flag.requires]


def validate_registry(registry: dict[str, FlagDefinition]) -> list[str]:
    """Every problem with ``registry``; empty when it is valid."""
    problems: list[str] = []
    for key, flag in registry.items():
        if key != flag.key:
            problems.append(f"{key}: registered under another key")
        if len(key) > KEY_MAX_LENGTH or not KEY_PATTERN.match(key):
            problems.append(f"{key}: key must match {KEY_PATTERN.pattern} and be at most {KEY_MAX_LENGTH} chars")
        for dependency in (flag.parent, *flag.requires):
            if dependency is not None and dependency not in registry:
                problems.append(f"{key}: depends on undeclared flag {dependency}")
        if flag.kind in ("release", "experiment"):
            if flag.expires is None:
                problems.append(f"{key}: {flag.kind} flags need an expiry")
            elif flag.expires - flag.created > MAX_LIFETIME:
                problems.append(f"{key}: expires more than {MAX_LIFETIME.days} days after it was created")
        if flag.public and not flag.client:
            problems.append(f"{key}: a public flag must also be a client flag")
    problems.extend(_cycles(registry))
    return problems


def _cycles(registry: dict[str, FlagDefinition]) -> list[str]:
    done: set[str] = set()

    def visit(key: str, path: tuple[str, ...]) -> str | None:
        if key in path:
            return " -> ".join((*path, key))
        if key in done or key not in registry:
            return None
        flag = registry[key]
        for dependency in (flag.parent, *flag.requires):
            if dependency is not None and (cycle := visit(dependency, (*path, key))):
                return cycle
        done.add(key)
        return None

    return [f"dependency cycle: {cycle}" for key in registry if (cycle := visit(key, ()))]


_problems = validate_registry(FLAGS)
if _problems:
    raise RuntimeError("Invalid feature flag registry: " + "; ".join(_problems))
