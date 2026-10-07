"""Canonical catalog of hook transitions: the bridge between teaser and clip.

A rendered clip plays ``[hook][bridge][clip]``. The bridge is assembled from
independent parts that mix freely:

* source  -- what fills the gap (a rewind of the hook, a flash-forward of the
  clip's best moments, a frozen frame, a colour card...)
* effects -- visual treatments stacked on the gap footage
* sound   -- the gap's audio (synthesised sound design or the hook's own audio)
* impact  -- a hit on the first moments of the clip, with its own sound
* text    -- an on-screen bridge line, in one of several text styles

``PRESETS`` names 100+ curated mixes. This module is data only, so the editor
can list it without touching FFmpeg; ``graph.py`` holds the builder for every
id here, which ``tests/test_hook_transitions`` asserts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MIN_DURATION = 0.3
MAX_DURATION = 2.0
MAX_EFFECTS = 4

# Effects that re-frame the picture. Two would fight over the same crop.
FRAMING_EFFECTS = frozenset({
    "zoom_in", "zoom_out", "slow_zoom", "crash_zoom", "zoom_pulse", "shake", "spin", "tilt", "whip_pan",
})


@dataclass(frozen=True)
class Part:
    id: str
    name: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description}


def _parts(*rows: tuple[str, str, str]) -> dict[str, Part]:
    return {row[0]: Part(*row) for row in rows}


SOURCES = _parts(
    ("rewind", "Rewind", "The hook plays backwards at speed, like scrubbing the tape back"),
    ("freeze_frame", "Freeze Frame", "The hook's last frame holds on screen"),
    ("slow_motion", "Slow Motion", "The hook's final instant stretched out in slow motion"),
    ("flash_forward", "Flash-Forward", "Rapid cuts of three big moments from later in the clip"),
    ("sneak_peek", "Sneak Peek", "A glimpse of the clip's payoff before it starts"),
    ("sneak_peek_fast", "Fast Peek", "The payoff moment at double speed"),
    ("first_frame", "Before Moment", "Holds on the clip's opening frame, the calm before it starts"),
    ("blur_card", "Blur Card", "A blurred, dimmed still of the hook, made for text"),
    ("black_card", "Black Card", "A clean black screen"),
    ("white_card", "White Card", "A bright white screen"),
    ("brand_card", "Brand Card", "A solid violet brand-colour screen"),
)

EFFECTS = _parts(
    ("zoom_in", "Zoom In", "Steady push in"),
    ("zoom_out", "Zoom Out", "Starts tight and pulls back"),
    ("slow_zoom", "Slow Zoom", "Subtle Ken Burns drift"),
    ("crash_zoom", "Crash Zoom", "Holds, then slams in at the end"),
    ("zoom_pulse", "Zoom Pulse", "Beats in and out like a bass hit"),
    ("shake", "Camera Shake", "Handheld earthquake jitter"),
    ("spin", "Spin", "One full rotation"),
    ("tilt", "Tilt Wobble", "Quick side-to-side wobble"),
    ("whip_pan", "Whip Pan", "Fast horizontal smear"),
    ("rgb_split", "RGB Split", "Offset colour channels"),
    ("glitch", "Glitch", "Digital noise with colour tearing"),
    ("vhs", "VHS", "Tape noise, scanlines and bleed"),
    ("pixelate", "Pixelate", "Chunky 8-bit pixels"),
    ("blur", "Blur", "Heavy defocus"),
    ("dream", "Dreamy", "Soft glow with lifted colour"),
    ("invert", "Invert", "Negative colours"),
    ("black_white", "Black & White", "Drains all colour"),
    ("noir", "Noir", "High-contrast black and white with vignette"),
    ("sepia", "Sepia", "Old-film brown tone"),
    ("vignette", "Vignette", "Darkened edges"),
    ("strobe", "Strobe", "Flickering light pulses"),
    ("flash_in", "Flash In", "Opens on a white flash"),
    ("flash_out", "Flash Out", "Burns out to white"),
    ("fade_in", "Fade In", "Rises from black"),
    ("dip_black", "Dip to Black", "Fades to black at the end"),
    ("mirror", "Mirror", "Flipped horizontally"),
    ("warm_tone", "Warm Tone", "Golden-hour warmth"),
    ("cool_tone", "Cool Tone", "Cold blue grade"),
    ("saturate", "Saturate", "Punchy over-saturated colour"),
    ("high_contrast", "High Contrast", "Crushed blacks, bright highlights"),
    ("sketch", "Sketch", "Pencil-drawn edges"),
    ("cinema_bars", "Cinema Bars", "Letterbox bars top and bottom"),
)

SOUNDS = _parts(
    ("whoosh", "Whoosh", "Air rushing past"),
    ("swoosh", "Swoosh", "Short, bright swipe"),
    ("riser", "Riser", "Rising pitch that builds tension"),
    ("downlifter", "Downlifter", "Falling pitch that releases it"),
    ("reverse_cymbal", "Reverse Cymbal", "A cymbal swelling backwards into the cut"),
    ("boom", "Boom", "Deep cinematic hit"),
    ("sub_drop", "Sub Drop", "Bass that dives out from under you"),
    ("impact_hit", "Impact Hit", "Punchy hit with a noise crack"),
    ("click", "Click", "Tight UI click"),
    ("pop", "Pop", "Bubbly pop"),
    ("ding", "Ding", "Bright bell ding"),
    ("glitch_zap", "Glitch Zap", "Stuttering digital zap"),
    ("heartbeat", "Heartbeat", "Two low thumps"),
    ("tape_stop", "Tape Stop", "Audio grinding to a halt"),
    ("record_scratch", "Record Scratch", "Vinyl scratch, the classic 'wait, what?'"),
    ("camera_shutter", "Camera Shutter", "Snapshot click"),
    ("beep", "Beep", "Censor-style beep"),
    ("tick_tock", "Tick Tock", "Clock ticking"),
    ("static_noise", "TV Static", "Detuned television hiss"),
    ("hook_rewind", "Hook Rewind", "The hook's own audio played backwards"),
    ("hook_echo", "Hook Echo", "The hook's last words echoing out"),
    ("silence", "Silence", "A beat of dead air"),
)

# Sounds built from the hook's audio: meaningless on the clip's opening hit.
HOOK_AUDIO_SOUNDS = frozenset({"hook_rewind", "hook_echo"})
IMPACT_SOUNDS = {key: part for key, part in SOUNDS.items() if key not in HOOK_AUDIO_SOUNDS}

IMPACTS = _parts(
    ("none", "None", "Cut straight into the clip"),
    ("flash", "Flash", "White flash on the first frame"),
    ("punch_zoom", "Punch Zoom", "Snaps in from a tight zoom"),
    ("shake", "Shake", "Jolts the frame on arrival"),
    ("glitch", "Glitch", "A burst of digital glitch"),
    ("rgb_split", "RGB Split", "Channels snap back together"),
    ("strobe", "Strobe", "A few frames of strobe"),
    ("fade_in", "Fade Up", "Rises from black"),
)

# The effect ids each impact applies to the clip's opening moments.
IMPACT_EFFECTS: dict[str, tuple[str, ...]] = {
    "none": (),
    "flash": ("flash_in",),
    "punch_zoom": ("zoom_out",),
    "shake": ("shake",),
    "glitch": ("glitch",),
    "rgb_split": ("rgb_split",),
    "strobe": ("strobe",),
    "fade_in": ("fade_in",),
}

TEXT_STYLES = _parts(
    ("bold_white", "Bold White", "Heavy white type with a black outline"),
    ("yellow_box", "Yellow Box", "Black type on a yellow highlight box"),
    ("red_banner", "Red Banner", "White type on a red banner"),
    ("neon", "Neon", "Glowing cyan type"),
    ("impact_caps", "Impact Caps", "Tall condensed all-caps headline"),
    ("marker", "Marker", "Hand-drawn marker lettering"),
    ("comic", "Comic", "Bouncy comic-book lettering"),
    ("cinematic", "Cinematic", "Elegant serif title"),
)


@dataclass(frozen=True)
class Phrase:
    id: str
    text: str
    # Hook intents this line answers, used by Auto to pick one that fits.
    intents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "intents": list(self.intents)}


PHRASES: dict[str, Phrase] = {p.id: p for p in (
    Phrase("wait_for_it", "Wait for it...", ("funny", "shock", "general")),
    Phrase("heres_what_happened", "Here's what happened", ("story", "shock", "news")),
    Phrase("watch_till_end", "Watch till the end", ("general", "story")),
    Phrase("it_gets_better", "It gets better", ("funny", "hype")),
    Phrase("nobody_expected", "Nobody expected this", ("shock", "sports", "gaming")),
    Phrase("let_me_explain", "Let me explain", ("question", "educational")),
    Phrase("rewind", "Rewind", ("story", "general")),
    Phrase("but_first", "But first...", ("story", "educational")),
    Phrase("plot_twist", "Plot twist", ("shock", "funny", "story")),
    Phrase("the_truth", "The truth is...", ("emotional", "question", "news")),
    Phrase("story_time", "Story time", ("story",)),
    Phrase("keep_watching", "Keep watching", ("general", "hype")),
    Phrase("changed_everything", "This changed everything", ("emotional", "story", "money")),
    Phrase("wont_believe", "You won't believe this", ("shock", "funny")),
    Phrase("heres_why", "Here's why", ("question", "educational", "news")),
    Phrase("hold_on", "Hold on...", ("shock", "funny")),
    Phrase("the_moment", "The moment it happened", ("sports", "gaming", "shock")),
    Phrase("listen_closely", "Listen closely", ("educational", "emotional", "music")),
    Phrase("real_talk", "Real talk", ("emotional", "podcast")),
    Phrase("the_secret", "The secret?", ("money", "educational", "question")),
    Phrase("lets_go_back", "Let's go back", ("story",)),
    Phrase("why_it_matters", "Why this matters", ("news", "educational")),
    Phrase("it_started_here", "It all started here", ("story", "emotional")),
    Phrase("best_part", "The best part?", ("funny", "hype", "food")),
    Phrase("breaking_it_down", "Breaking it down", ("educational", "tech")),
    Phrase("game_changer", "Game changer", ("tech", "money", "hype")),
    Phrase("heres_how", "Here's how", ("money", "educational", "fitness")),
    Phrase("the_answer", "The answer might surprise you", ("question",)),
    Phrase("do_the_math", "Do the math", ("money",)),
    Phrase("no_way", "No way", ("shock", "sports", "gaming")),
    Phrase("clutch", "Clutch moment", ("gaming", "sports")),
    Phrase("drop_incoming", "Drop incoming", ("music", "hype")),
    Phrase("taste_test", "The taste test", ("food",)),
    Phrase("the_results", "The results", ("fitness", "tech")),
    Phrase("say_that_again", "Say that again?", ("podcast", "shock", "funny")),
    Phrase("dead_serious", "Dead serious", ("emotional", "podcast")),
    Phrase("breaking", "Breaking", ("news",)),
    Phrase("level_up", "Level up", ("gaming", "fitness", "hype")),
    Phrase("three_two_one", "3... 2... 1...", ("hype", "sports", "music")),
    Phrase("from_the_top", "From the top", ("general", "story")),
    Phrase("full_episode", "Watch the full episode", ("podcast",)),
)}

# Auto's bridge on a podcast clip points viewers at the episode it was cut
# from, held long enough to read.
CTA_PHRASE = "full_episode"
CTA_CATEGORIES = frozenset({"podcast_interview"})
CTA_MIN_DURATION = 1.2

# Hook intents Auto can detect; UI filters use the same names.
INTENTS = (
    "general", "question", "shock", "funny", "story", "emotional", "educational", "money",
    "news", "hype", "sports", "gaming", "music", "food", "fitness", "tech", "podcast",
)


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    group: str
    source: str
    effects: tuple[str, ...]
    sound: str
    impact: str = "none"
    impact_sound: str | None = None
    # A phrase id, "auto" to let Auto pick one matching the hook, or None.
    text: str | None = None
    text_style: str = "bold_white"
    duration: float = 0.8
    # Content categories (clip_generation.model.ContentCategory) this suits;
    # empty means any.
    fits: tuple[str, ...] = ()
    moods: tuple[str, ...] = field(default=("general",))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group,
            "source": self.source,
            "effects": list(self.effects),
            "sound": self.sound,
            "impact": self.impact,
            "impact_sound": self.impact_sound,
            "text": self.text,
            "text_style": self.text_style,
            "duration": self.duration,
            "fits": list(self.fits),
            "moods": list(self.moods),
        }


P = Preset
_GAME = ("gaming",)
_SPORT = ("sports",)
_TALK = ("podcast_interview", "news_politics")
_LEARN = ("tutorial_educational", "tech")
_FUN = ("comedy", "reaction")
_LIFE = ("vlog", "food", "fitness_health")

PRESET_LIST: tuple[Preset, ...] = (
    # --- Viral: the formats short-form audiences already know -----------------
    P("viral_rewind", "Viral Rewind", "Viral", "rewind", ("rgb_split",), "hook_rewind", "flash", "boom", "auto", "yellow_box", 0.9, moods=("general", "story", "shock")),
    P("wait_for_it", "Wait For It", "Viral", "freeze_frame", ("zoom_in", "vignette"), "riser", "punch_zoom", "impact_hit", "wait_for_it", "bold_white", 1.1, fits=_FUN, moods=("funny", "shock")),
    P("record_scratch_freeze", "Record Scratch", "Viral", "freeze_frame", ("black_white", "zoom_in"), "record_scratch", "flash", None, "hold_on", "yellow_box", 1.0, fits=_FUN, moods=("funny", "shock")),
    P("heres_what_happened", "Here's What Happened", "Viral", "rewind", ("vhs",), "hook_rewind", "flash", "swoosh", "heres_what_happened", "red_banner", 1.0, moods=("story", "shock")),
    P("plot_twist", "Plot Twist", "Viral", "freeze_frame", ("invert", "shake"), "glitch_zap", "glitch", "boom", "plot_twist", "impact_caps", 0.9, moods=("shock", "funny")),
    P("you_wont_believe", "You Won't Believe", "Viral", "flash_forward", ("saturate",), "riser", "punch_zoom", "boom", "wont_believe", "yellow_box", 1.2, moods=("shock",)),
    P("watch_till_end", "Watch Till The End", "Viral", "sneak_peek", ("blur", "vignette"), "reverse_cymbal", "flash", "impact_hit", "watch_till_end", "red_banner", 1.2, moods=("general", "story")),
    P("keep_watching", "Keep Watching", "Viral", "flash_forward", ("rgb_split",), "whoosh", "punch_zoom", None, "keep_watching", "bold_white", 1.0, moods=("general", "hype")),
    P("no_way", "No Way", "Viral", "freeze_frame", ("crash_zoom",), "sub_drop", "shake", "boom", "no_way", "impact_caps", 0.9, moods=("shock", "sports", "gaming")),
    P("viral_flash", "Viral Flash", "Viral", "white_card", ("flash_out",), "impact_hit", "flash", None, None, "bold_white", 0.35, moods=("general", "hype")),
    P("sneak_peek_tease", "Sneak Peek Tease", "Viral", "sneak_peek_fast", ("cinema_bars", "saturate"), "whoosh", "flash", "pop", "auto", "yellow_box", 1.0, moods=("general", "hype")),
    P("auto_bridge", "Smart Bridge", "Viral", "blur_card", ("zoom_in",), "whoosh", "punch_zoom", "pop", "auto", "yellow_box", 1.1, moods=("general", "question", "story")),
    P("hold_on", "Hold On", "Viral", "freeze_frame", ("zoom_pulse",), "tape_stop", "punch_zoom", None, "hold_on", "bold_white", 1.0, fits=_FUN, moods=("funny", "shock")),
    P("say_that_again", "Say That Again", "Viral", "rewind", ("zoom_in",), "hook_rewind", "punch_zoom", "record_scratch", "say_that_again", "yellow_box", 0.9, fits=_TALK + _FUN, moods=("shock", "funny", "podcast")),

    # --- Cinematic ------------------------------------------------------------
    P("cinematic_dip", "Cinematic Dip", "Cinematic", "slow_motion", ("cinema_bars", "dip_black"), "boom", "fade_in", None, None, "cinematic", 1.2, moods=("emotional", "story")),
    P("trailer_hit", "Trailer Hit", "Cinematic", "black_card", (), "boom", "flash", "impact_hit", "auto", "cinematic", 1.0, moods=("story", "emotional", "shock")),
    P("slow_mo_drama", "Slow-Mo Drama", "Cinematic", "slow_motion", ("cinema_bars", "high_contrast"), "heartbeat", "fade_in", None, None, "cinematic", 1.4, moods=("emotional", "sports")),
    P("noir_reveal", "Noir Reveal", "Cinematic", "freeze_frame", ("noir", "slow_zoom"), "downlifter", "fade_in", None, "the_truth", "cinematic", 1.4, moods=("emotional", "news", "story")),
    P("golden_hour", "Golden Hour", "Cinematic", "slow_motion", ("warm_tone", "vignette"), "reverse_cymbal", "fade_in", None, None, "cinematic", 1.2, fits=_LIFE, moods=("emotional",)),
    P("cold_open", "Cold Open", "Cinematic", "black_card", (), "silence", "fade_in", "boom", "it_started_here", "cinematic", 1.0, moods=("story",)),
    P("epic_trailer", "Epic Trailer", "Cinematic", "flash_forward", ("cinema_bars", "high_contrast"), "riser", "flash", "boom", "auto", "cinematic", 1.5, moods=("hype", "story")),
    P("dream_sequence", "Dream Sequence", "Cinematic", "slow_motion", ("dream",), "reverse_cymbal", "fade_in", None, None, "cinematic", 1.4, moods=("emotional",)),
    P("film_memory", "Film Memory", "Cinematic", "rewind", ("sepia", "vignette"), "hook_rewind", "fade_in", None, "lets_go_back", "cinematic", 1.2, moods=("story", "emotional")),
    P("heartbeat_hold", "Heartbeat Hold", "Cinematic", "freeze_frame", ("zoom_pulse", "vignette"), "heartbeat", "flash", None, None, "cinematic", 1.2, moods=("emotional", "shock")),
    P("blackout", "Blackout", "Cinematic", "black_card", (), "sub_drop", "fade_in", None, None, "cinematic", 0.6, moods=("general",)),
    P("cool_grade", "Cool Grade", "Cinematic", "slow_motion", ("cool_tone", "cinema_bars"), "downlifter", "fade_in", None, None, "cinematic", 1.1, moods=("emotional", "tech")),
    P("letterbox_title", "Letterbox Title", "Cinematic", "blur_card", ("cinema_bars",), "reverse_cymbal", "fade_in", None, "auto", "cinematic", 1.4, moods=("story", "general")),

    # --- Glitch & Retro -------------------------------------------------------
    P("glitch_cut", "Glitch Cut", "Glitch & Retro", "freeze_frame", ("glitch",), "glitch_zap", "glitch", None, None, "neon", 0.6, fits=_GAME + ("tech",), moods=("hype", "gaming", "tech")),
    P("vhs_rewind", "VHS Rewind", "Glitch & Retro", "rewind", ("vhs",), "hook_rewind", "rgb_split", None, "rewind", "neon", 1.0, moods=("story", "general")),
    P("tv_static", "TV Static", "Glitch & Retro", "freeze_frame", ("vhs", "black_white"), "static_noise", "glitch", None, None, "neon", 0.7, moods=("general", "shock")),
    P("pixel_warp", "Pixel Warp", "Glitch & Retro", "freeze_frame", ("pixelate", "zoom_in"), "glitch_zap", "glitch", None, "level_up", "comic", 0.8, fits=_GAME, moods=("gaming",)),
    P("rgb_shock", "RGB Shock", "Glitch & Retro", "rewind", ("rgb_split", "shake"), "glitch_zap", "rgb_split", "impact_hit", None, "neon", 0.8, moods=("shock", "hype")),
    P("cyber_glitch", "Cyber Glitch", "Glitch & Retro", "flash_forward", ("glitch", "cool_tone"), "static_noise", "glitch", "boom", "auto", "neon", 1.0, fits=_GAME + ("tech",), moods=("tech", "gaming")),
    P("retro_tape", "Retro Tape", "Glitch & Retro", "rewind", ("vhs", "warm_tone"), "tape_stop", "fade_in", None, "from_the_top", "marker", 1.1, moods=("story", "funny")),
    P("negative_flash", "Negative Flash", "Glitch & Retro", "freeze_frame", ("invert", "strobe"), "glitch_zap", "flash", None, None, "neon", 0.5, moods=("shock", "hype")),
    P("arcade_level_up", "Arcade Level Up", "Glitch & Retro", "freeze_frame", ("pixelate", "saturate"), "ding", "punch_zoom", "pop", "level_up", "comic", 0.9, fits=_GAME, moods=("gaming", "hype")),
    P("signal_lost", "Signal Lost", "Glitch & Retro", "black_card", ("vhs",), "static_noise", "glitch", None, None, "neon", 0.8, moods=("general",)),
    P("data_corrupt", "Data Corrupt", "Glitch & Retro", "rewind", ("glitch", "pixelate"), "glitch_zap", "rgb_split", None, None, "neon", 0.8, fits=("tech",), moods=("tech", "shock")),
    P("sketch_rewind", "Sketch Rewind", "Glitch & Retro", "rewind", ("sketch",), "hook_rewind", "fade_in", None, "lets_go_back", "marker", 1.0, moods=("story", "educational")),
    P("mirror_glitch", "Mirror Glitch", "Glitch & Retro", "rewind", ("mirror", "rgb_split"), "glitch_zap", "glitch", None, None, "neon", 0.7, moods=("general",)),

    # --- Hype & Energy --------------------------------------------------------
    P("crash_zoom_boom", "Crash Zoom Boom", "Hype & Energy", "freeze_frame", ("crash_zoom", "saturate"), "riser", "shake", "boom", None, "impact_caps", 0.9, moods=("hype", "shock")),
    P("bass_drop", "Bass Drop", "Hype & Energy", "freeze_frame", ("zoom_pulse", "strobe"), "sub_drop", "punch_zoom", "boom", "drop_incoming", "impact_caps", 1.0, fits=("music",), moods=("music", "hype")),
    P("strobe_rush", "Strobe Rush", "Hype & Energy", "flash_forward", ("strobe",), "riser", "flash", "impact_hit", None, "impact_caps", 0.9, moods=("hype", "music")),
    P("whip_hype", "Whip Hype", "Hype & Energy", "sneak_peek_fast", ("whip_pan",), "whoosh", "punch_zoom", None, None, "impact_caps", 0.6, moods=("hype", "sports")),
    P("countdown", "Countdown", "Hype & Energy", "blur_card", ("zoom_pulse",), "tick_tock", "flash", "boom", "three_two_one", "impact_caps", 1.5, moods=("hype", "sports", "music")),
    P("shockwave", "Shockwave", "Hype & Energy", "white_card", ("flash_out",), "boom", "shake", "impact_hit", None, "impact_caps", 0.4, moods=("shock", "hype")),
    P("adrenaline", "Adrenaline", "Hype & Energy", "flash_forward", ("high_contrast", "shake"), "riser", "punch_zoom", "boom", None, "impact_caps", 1.0, fits=_SPORT + ("fitness_health",), moods=("sports", "fitness", "hype")),
    P("spin_cycle", "Spin Cycle", "Hype & Energy", "freeze_frame", ("spin", "blur"), "whoosh", "punch_zoom", "pop", None, "comic", 0.7, fits=_FUN, moods=("funny", "hype")),
    P("pulse_riser", "Pulse Riser", "Hype & Energy", "freeze_frame", ("zoom_pulse", "saturate"), "riser", "flash", "boom", "auto", "impact_caps", 1.2, moods=("hype", "general")),
    P("slam", "Slam", "Hype & Energy", "freeze_frame", ("crash_zoom",), "impact_hit", "shake", "boom", None, "impact_caps", 0.5, moods=("shock", "sports")),
    P("hyper_peek", "Hyper Peek", "Hype & Energy", "sneak_peek_fast", ("saturate", "rgb_split"), "swoosh", "flash", "impact_hit", "keep_watching", "yellow_box", 0.9, moods=("hype", "general")),
    P("tunnel_vision", "Tunnel Vision", "Hype & Energy", "freeze_frame", ("zoom_in", "vignette", "blur"), "riser", "punch_zoom", "boom", None, "impact_caps", 1.0, moods=("shock", "emotional")),

    # --- Minimal & Clean ------------------------------------------------------
    P("clean_cut", "Clean Cut", "Minimal", "black_card", (), "click", "none", None, None, "bold_white", 0.3, moods=("general", "podcast", "educational")),
    P("soft_fade", "Soft Fade", "Minimal", "black_card", (), "silence", "fade_in", None, None, "bold_white", 0.5, moods=("general", "emotional")),
    P("white_dip", "White Dip", "Minimal", "white_card", (), "swoosh", "fade_in", None, None, "bold_white", 0.4, moods=("general",)),
    P("quick_swipe", "Quick Swipe", "Minimal", "sneak_peek_fast", ("whip_pan",), "swoosh", "none", None, None, "bold_white", 0.4, moods=("general",)),
    P("gentle_blur", "Gentle Blur", "Minimal", "blur_card", (), "whoosh", "fade_in", None, None, "bold_white", 0.6, moods=("general", "emotional")),
    P("brand_flash", "Brand Flash", "Minimal", "brand_card", (), "pop", "flash", None, None, "bold_white", 0.35, moods=("general",)),
    P("brand_title", "Brand Title", "Minimal", "brand_card", (), "swoosh", "fade_in", None, "auto", "bold_white", 1.1, moods=("general", "educational")),
    P("still_moment", "Still Moment", "Minimal", "freeze_frame", ("slow_zoom",), "silence", "fade_in", None, None, "bold_white", 0.7, moods=("emotional", "podcast")),
    P("snapshot", "Snapshot", "Minimal", "freeze_frame", ("flash_in", "black_white"), "camera_shutter", "flash", None, None, "bold_white", 0.5, moods=("general", "story")),
    P("breath", "Breath", "Minimal", "first_frame", ("fade_in",), "silence", "none", None, None, "bold_white", 0.5, moods=("emotional", "podcast")),

    # --- Story & Talk ---------------------------------------------------------
    P("story_time", "Story Time", "Story & Talk", "blur_card", ("slow_zoom",), "swoosh", "fade_in", None, "story_time", "marker", 1.2, moods=("story",)),
    P("but_first", "But First", "Story & Talk", "rewind", ("sepia",), "hook_rewind", "fade_in", None, "but_first", "yellow_box", 1.0, moods=("story", "educational")),
    P("real_talk", "Real Talk", "Story & Talk", "freeze_frame", ("noir",), "downlifter", "fade_in", None, "real_talk", "bold_white", 1.1, fits=_TALK, moods=("emotional", "podcast")),
    P("the_truth", "The Truth", "Story & Talk", "blur_card", ("vignette",), "heartbeat", "fade_in", None, "the_truth", "cinematic", 1.3, fits=_TALK, moods=("emotional", "question", "news")),
    P("podcast_echo", "Podcast Echo", "Story & Talk", "freeze_frame", ("zoom_in", "black_white"), "hook_echo", "punch_zoom", None, None, "bold_white", 1.0, fits=_TALK, moods=("podcast", "emotional")),
    P("say_it_louder", "Say It Louder", "Story & Talk", "rewind", ("zoom_in", "high_contrast"), "hook_rewind", "punch_zoom", "impact_hit", "say_that_again", "impact_caps", 0.9, fits=_TALK, moods=("podcast", "shock")),
    P("dead_serious", "Dead Serious", "Story & Talk", "freeze_frame", ("noir", "slow_zoom"), "boom", "fade_in", None, "dead_serious", "impact_caps", 1.2, fits=_TALK, moods=("emotional", "podcast")),
    P("changed_everything", "Changed Everything", "Story & Talk", "slow_motion", ("warm_tone", "vignette"), "reverse_cymbal", "flash", "boom", "changed_everything", "cinematic", 1.3, moods=("story", "emotional", "money")),
    P("it_started_here", "It Started Here", "Story & Talk", "rewind", ("sepia", "vignette"), "hook_rewind", "fade_in", None, "it_started_here", "cinematic", 1.3, moods=("story",)),
    P("from_the_top", "From The Top", "Story & Talk", "rewind", ("vhs",), "tape_stop", "flash", None, "from_the_top", "marker", 1.0, moods=("story", "general")),
    P("hot_take", "Hot Take", "Story & Talk", "freeze_frame", ("warm_tone", "zoom_pulse"), "impact_hit", "shake", None, "auto", "red_banner", 1.0, fits=_TALK, moods=("podcast", "shock", "news")),
    P("interview_cut", "Interview Cut", "Story & Talk", "first_frame", ("slow_zoom",), "click", "none", None, None, "bold_white", 0.5, fits=_TALK, moods=("podcast",)),

    # --- Comedy ---------------------------------------------------------------
    P("comedy_scratch", "Comedy Scratch", "Comedy", "freeze_frame", ("zoom_in",), "record_scratch", "punch_zoom", "pop", "hold_on", "comic", 1.0, fits=_FUN, moods=("funny",)),
    P("dramatic_zoom", "Dramatic Zoom", "Comedy", "freeze_frame", ("crash_zoom", "high_contrast"), "sub_drop", "shake", None, None, "comic", 1.0, fits=_FUN, moods=("funny", "shock")),
    P("sitcom_pop", "Sitcom Pop", "Comedy", "freeze_frame", ("saturate",), "pop", "punch_zoom", "ding", "it_gets_better", "comic", 0.8, fits=_FUN, moods=("funny",)),
    P("oops_rewind", "Oops Rewind", "Comedy", "rewind", ("saturate", "tilt"), "hook_rewind", "punch_zoom", "pop", "wait_for_it", "comic", 0.9, fits=_FUN, moods=("funny",)),
    P("beep_bleep", "Beep", "Comedy", "freeze_frame", ("pixelate",), "beep", "punch_zoom", None, None, "comic", 0.6, fits=_FUN, moods=("funny", "shock")),
    P("wobble", "Wobble", "Comedy", "freeze_frame", ("tilt", "saturate"), "swoosh", "shake", "pop", None, "comic", 0.7, fits=_FUN, moods=("funny",)),
    P("best_part", "Best Part", "Comedy", "sneak_peek", ("saturate",), "riser", "flash", "pop", "best_part", "comic", 1.1, moods=("funny", "hype", "food")),
    P("tape_stop_gag", "Tape Stop Gag", "Comedy", "slow_motion", ("black_white",), "tape_stop", "punch_zoom", "boom", None, "comic", 1.0, fits=_FUN, moods=("funny",)),
    P("wide_eyes", "Wide Eyes", "Comedy", "freeze_frame", ("zoom_in", "vignette"), "ding", "shake", None, "wont_believe", "comic", 1.0, fits=_FUN, moods=("funny", "shock")),
    P("mirror_meme", "Mirror Meme", "Comedy", "freeze_frame", ("mirror", "zoom_pulse"), "pop", "punch_zoom", None, None, "comic", 0.7, fits=_FUN, moods=("funny",)),

    # --- Educational & Tech ---------------------------------------------------
    P("lesson_card", "Lesson Card", "Educational & Tech", "blur_card", ("slow_zoom",), "ding", "fade_in", None, "let_me_explain", "yellow_box", 1.2, fits=_LEARN, moods=("educational", "question")),
    P("heres_why", "Here's Why", "Educational & Tech", "blur_card", ("zoom_in",), "swoosh", "punch_zoom", None, "heres_why", "yellow_box", 1.1, fits=_LEARN + _TALK, moods=("question", "educational", "news")),
    P("breakdown", "Breakdown", "Educational & Tech", "freeze_frame", ("sketch", "slow_zoom"), "click", "fade_in", None, "breaking_it_down", "marker", 1.2, fits=_LEARN, moods=("educational", "tech")),
    P("the_answer", "The Answer", "Educational & Tech", "sneak_peek", ("blur",), "riser", "flash", "ding", "the_answer", "yellow_box", 1.2, fits=_LEARN, moods=("question",)),
    P("tech_boot", "Tech Boot", "Educational & Tech", "black_card", ("glitch",), "glitch_zap", "rgb_split", "click", "game_changer", "neon", 1.0, fits=("tech",), moods=("tech", "hype")),
    P("secret_reveal", "Secret Reveal", "Educational & Tech", "blur_card", ("vignette",), "reverse_cymbal", "flash", "ding", "the_secret", "yellow_box", 1.2, moods=("money", "educational", "question")),
    P("how_to", "How To", "Educational & Tech", "flash_forward", ("saturate",), "swoosh", "punch_zoom", "click", "heres_how", "yellow_box", 1.1, fits=_LEARN + _LIFE, moods=("educational", "money", "fitness")),
    P("step_one", "Step One", "Educational & Tech", "brand_card", (), "click", "punch_zoom", None, "breaking_it_down", "bold_white", 0.9, fits=_LEARN, moods=("educational",)),
    P("money_math", "Money Math", "Educational & Tech", "freeze_frame", ("zoom_in", "high_contrast"), "camera_shutter", "flash", "ding", "do_the_math", "yellow_box", 1.1, moods=("money",)),
    P("why_matters", "Why It Matters", "Educational & Tech", "blur_card", ("cool_tone",), "downlifter", "fade_in", None, "why_it_matters", "cinematic", 1.2, fits=_LEARN + _TALK, moods=("news", "educational")),
    P("results_reveal", "Results Reveal", "Educational & Tech", "sneak_peek", ("saturate", "zoom_in"), "riser", "flash", "boom", "the_results", "impact_caps", 1.2, fits=("tech", "fitness_health"), moods=("fitness", "tech")),

    # --- Sports & Gaming ------------------------------------------------------
    P("clutch_moment", "Clutch Moment", "Sports & Gaming", "slow_motion", ("high_contrast", "zoom_in"), "heartbeat", "shake", "boom", "clutch", "impact_caps", 1.3, fits=_GAME + _SPORT, moods=("gaming", "sports")),
    P("instant_replay", "Instant Replay", "Sports & Gaming", "rewind", ("cinema_bars",), "hook_rewind", "flash", "impact_hit", "the_moment", "red_banner", 1.1, fits=_SPORT + _GAME, moods=("sports", "gaming")),
    P("highlight_reel", "Highlight Reel", "Sports & Gaming", "flash_forward", ("saturate", "rgb_split"), "whoosh", "punch_zoom", "boom", None, "impact_caps", 1.0, fits=_SPORT + _GAME, moods=("sports", "gaming", "hype")),
    P("final_whistle", "Final Whistle", "Sports & Gaming", "slow_motion", ("noir",), "downlifter", "flash", "boom", "no_way", "impact_caps", 1.3, fits=_SPORT, moods=("sports",)),
    P("game_over", "Game Over", "Sports & Gaming", "freeze_frame", ("pixelate", "invert"), "glitch_zap", "glitch", None, "nobody_expected", "comic", 0.9, fits=_GAME, moods=("gaming", "shock")),
    P("killcam", "Killcam", "Sports & Gaming", "rewind", ("black_white", "vignette"), "hook_rewind", "shake", "boom", "the_moment", "impact_caps", 1.0, fits=_GAME, moods=("gaming",)),
    P("speedrun", "Speedrun", "Sports & Gaming", "sneak_peek_fast", ("whip_pan", "saturate"), "swoosh", "punch_zoom", None, None, "comic", 0.6, fits=_GAME, moods=("gaming", "hype")),
    P("goal_rush", "Goal Rush", "Sports & Gaming", "flash_forward", ("strobe", "saturate"), "riser", "shake", "boom", None, "impact_caps", 1.0, fits=_SPORT, moods=("sports", "hype")),
    P("training_arc", "Training Arc", "Sports & Gaming", "flash_forward", ("high_contrast", "warm_tone"), "riser", "punch_zoom", "impact_hit", "level_up", "impact_caps", 1.2, fits=("fitness_health",) + _SPORT, moods=("fitness", "sports")),

    # --- Music ----------------------------------------------------------------
    P("beat_drop", "Beat Drop", "Music", "freeze_frame", ("zoom_pulse", "saturate"), "sub_drop", "strobe", "boom", None, "neon", 0.9, fits=("music",), moods=("music", "hype")),
    P("neon_pulse", "Neon Pulse", "Music", "flash_forward", ("strobe", "cool_tone"), "riser", "flash", None, None, "neon", 1.0, fits=("music",), moods=("music",)),
    P("vinyl_stop", "Vinyl Stop", "Music", "slow_motion", ("sepia",), "tape_stop", "punch_zoom", "boom", None, "marker", 1.1, fits=("music",), moods=("music", "funny")),
    P("listen_closely", "Listen Closely", "Music", "blur_card", ("vignette",), "silence", "fade_in", None, "listen_closely", "cinematic", 1.2, fits=("music",) + _TALK, moods=("music", "emotional")),
    P("drop_incoming", "Drop Incoming", "Music", "black_card", ("strobe",), "riser", "flash", "sub_drop", "drop_incoming", "neon", 1.3, fits=("music",), moods=("music", "hype")),
    P("echo_chamber", "Echo Chamber", "Music", "freeze_frame", ("dream",), "hook_echo", "fade_in", None, None, "neon", 1.2, fits=("music",), moods=("music", "emotional")),

    # --- Lifestyle ------------------------------------------------------------
    P("taste_test", "Taste Test", "Lifestyle", "sneak_peek", ("warm_tone", "saturate"), "pop", "punch_zoom", "ding", "taste_test", "comic", 1.1, fits=("food",), moods=("food",)),
    P("glow_up", "Glow Up", "Lifestyle", "flash_forward", ("dream", "warm_tone"), "reverse_cymbal", "flash", "ding", "auto", "marker", 1.2, fits=_LIFE, moods=("fitness", "emotional")),
    P("day_in_life", "Day In The Life", "Lifestyle", "flash_forward", ("warm_tone",), "swoosh", "fade_in", None, "auto", "marker", 1.0, fits=("vlog",), moods=("story", "general")),
    P("before_after", "Before & After", "Lifestyle", "first_frame", ("black_white", "slow_zoom"), "camera_shutter", "flash", "ding", "the_results", "yellow_box", 1.1, fits=_LIFE, moods=("fitness", "food")),
    P("vlog_swipe", "Vlog Swipe", "Lifestyle", "sneak_peek_fast", ("whip_pan", "warm_tone"), "whoosh", "none", None, None, "marker", 0.6, fits=("vlog",), moods=("general",)),
    P("cozy_fade", "Cozy Fade", "Lifestyle", "slow_motion", ("warm_tone", "vignette"), "silence", "fade_in", None, None, "marker", 1.0, fits=("vlog", "food"), moods=("emotional",)),

    # --- News -----------------------------------------------------------------
    P("breaking_news", "Breaking News", "News", "blur_card", ("cool_tone",), "beep", "flash", "impact_hit", "breaking", "red_banner", 1.2, fits=("news_politics",), moods=("news",)),
    P("news_rewind", "News Rewind", "News", "rewind", ("cool_tone", "vhs"), "hook_rewind", "flash", None, "heres_what_happened", "red_banner", 1.1, fits=("news_politics",), moods=("news", "story")),
    P("fact_check", "Fact Check", "News", "freeze_frame", ("black_white", "zoom_in"), "click", "punch_zoom", "ding", "the_truth", "red_banner", 1.1, fits=("news_politics",) + _TALK, moods=("news", "question")),
    P("headline", "Headline", "News", "black_card", (), "impact_hit", "flash", None, "auto", "red_banner", 1.1, fits=("news_politics",), moods=("news",)),
)

PRESETS: dict[str, Preset] = {preset.id: preset for preset in PRESET_LIST}

DEFAULT_PRESET = "auto_bridge"


def get_catalog() -> dict[str, Any]:
    """Everything the editor needs to list and build transitions."""
    from hook_transitions.graphics import library

    groups: list[str] = []
    for preset in PRESET_LIST:
        if preset.group not in groups:
            groups.append(preset.group)
    return {
        "sources": [part.to_dict() for part in SOURCES.values()],
        "effects": [part.to_dict() for part in EFFECTS.values()],
        "sounds": [part.to_dict() for part in SOUNDS.values()],
        "impact_sounds": [part.to_dict() for part in IMPACT_SOUNDS.values()],
        "impacts": [part.to_dict() for part in IMPACTS.values()],
        "text_styles": [part.to_dict() for part in TEXT_STYLES.values()],
        "phrases": [phrase.to_dict() for phrase in PHRASES.values()],
        "groups": groups,
        "presets": [preset.to_dict() for preset in PRESET_LIST],
        "graphics": [graphic.to_dict() for graphic in library().values()],
        "limits": {
            "min_duration": MIN_DURATION,
            "max_duration": MAX_DURATION,
            "max_effects": MAX_EFFECTS,
            "framing_effects": sorted(FRAMING_EFFECTS),
        },
        "default_preset": DEFAULT_PRESET,
    }
