"""What a reference reel gives the asset library: the notes written after studying it.

``measure`` counts what a machine can count (cuts, beats, flashes, speech).
Somebody then watches the reel and writes ``analysis.json`` beside it in this
shape: its hook, its music, the effects and sound effects it uses and where,
and its colour look. ``editing_assets`` turns those notes into assets once
they validate.

Hook types, techniques, sounds, moods and looks are fixed vocabularies so that
assets from different reels group and search together; a technique also names
the ids it maps to in the hook-transition catalogue, where one exists.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from edit_engine.looks import LOOKS
from edit_engine.music import MOODS
from hook_transitions.catalog import SOUNDS

HOOK_TYPES: dict[str, str] = {
    "title_reveal": "The subject's name or a headline builds on screen over a still hero shot.",
    "visual_spectacle": "The single most striking shot opens the reel, before any context.",
    "pattern_interrupt": "Something unrelated or chaotic grabs attention, then turns into the real subject.",
    "bold_claim": "A strong statement in text or voice that the viewer wants to check.",
    "question": "A question the viewer wants answered by the end.",
    "before_after": "The raw and the finished version side by side, or one cut into the other.",
    "transformation": "The reel opens mid-change and promises the result.",
    "pov": "A 'POV:' line puts the viewer inside a relatable situation.",
    "relatable_text": "An on-screen line the viewer recognises from their own life.",
    "curiosity_gap": "Shows enough to raise a question and holds back the answer.",
    "tease_payoff": "Flashes the best moment first, then rewinds to build up to it.",
    "direct_address": "Someone looks into the lens and speaks to the viewer from the first frame.",
    "countdown": "A number or timer the viewer waits out.",
    "reaction": "A face reacting to something not yet shown.",
}

# id -> (how to reproduce it, ids it maps to in hook_transitions or edit_engine.looks)
TECHNIQUES: dict[str, tuple[str, tuple[str, ...]]] = {
    "beat_cut": ("Cut on the music's beats or hits, so every shot change lands on a sound.", ()),
    "speed_ramp": ("Speed the clip up into a moment and drop to slow motion on it, then ramp back.", ()),
    "slow_motion": ("Play the hero moment at 25-50% speed, shot at a high frame rate.", ("slow_motion",)),
    "freeze_frame": ("Hold one frame on the peak moment, often with a hit sound.", ("freeze_frame",)),
    "match_cut": ("Cut between two shots whose shape, motion or position line up, so the eye carries over.", ()),
    "whip_transition": ("A fast pan blurs out of one shot and into the next.", ("whip_pan",)),
    "flash_transition": ("A white flash frame covers the cut.", ("flash_in", "flash_out")),
    "zoom_transition": ("Zoom into the end of one shot and out of the start of the next.", ("zoom_in", "zoom_out")),
    "crash_zoom": ("A sudden digital zoom punch onto the subject on a hit.", ("crash_zoom",)),
    "slow_push_in": ("A slow, steady zoom toward the subject that builds tension.", ("slow_zoom",)),
    "zoom_pulse": ("The frame scales up a few percent on each beat and settles back.", ("zoom_pulse",)),
    "camera_shake": ("The frame shakes on an impact or a bass hit.", ("shake",)),
    "glitch": ("A few frames of digital break-up on the cut.", ("glitch", "rgb_split")),
    "motion_blur": ("Directional blur added to fast moves so they read as speed.", ("blur",)),
    "strobe": ("Frames flicker between bright and dark on fast beats.", ("strobe",)),
    "kinetic_text": ("Words animate in one at a time in time with the voice, each with its own position and size.", ()),
    "type_on_text": ("A title appears letter by letter or word by word, each step on a beat.", ()),
    "word_captions": ("Spoken words burned in one or a few at a time, the current word highlighted.", ()),
    "text_mask_reveal": ("Text or footage revealed through a moving mask or from behind an object.", ()),
    "text_behind_subject": ("Large text placed behind the subject, the subject cut out in front of it.", ()),
    "cutout_collage": ("Cut-out photos and illustrations collaged over a flat background, moving with the words.", ()),
    "split_screen": ("Two shots side by side or stacked, played together.", ()),
    "masking_reveal": ("A shape or object wipes across the frame and reveals the next shot behind it.", ()),
    "parallax_3d": ("A still image split into layers that move at different speeds, faking a camera move.", ()),
    "sticker_overlay": ("Emoji, arrows or stickers pop in to point at or react to the moment.", ()),
    "light_leak": ("A warm light leak or flare laid over the footage in screen blend.", ()),
    "film_grain": ("Grain and soft halation for a film look.", ()),
    "vignette": ("Darkened corners pulling the eye to the centre.", ("vignette",)),
    "letterbox": ("Black bars top and bottom for a cinematic frame.", ("cinema_bars",)),
    "color_grade": ("One strong grade across every shot so the reel reads as one piece.", ()),
    "black_and_white": ("The reel, or a part of it, in black and white.", ("black_white", "noir")),
    "reverse": ("A clip played backwards, often to rewind to the start.", ("rewind",)),
    "seamless_loop": ("The last frame leads back into the first so the reel replays without a visible seam.", ()),
    "jump_cut": ("Pauses and dead air cut out of a talking shot, often with a small zoom change per cut.", ()),
    "sound_hit": ("A whoosh, boom or click laid on a cut or a text pop to give it weight.", ()),
    "riser_build": ("Rising sound and faster cuts building to a drop.", ("riser",)),
    "drop_sync": ("The biggest visual change lands exactly on the music's drop.", ()),
    "outline_glow": ("A glowing outline traced around the subject.", ()),
    "clone_trail": ("Copies of the subject left behind as it moves.", ()),
    "screen_recording": ("A phone or app screen recording used as footage.", ()),
    "reaction_inset": ("A small picture of a face reacting, over the main footage.", ()),
    "progress_bar": ("A bar or counter that fills as the reel goes on.", ()),
    "green_screen": ("The subject keyed out and placed over other footage or a backdrop.", ()),
    "lip_sync": ("The person mouths the words of the audio.", ()),
    "on_screen_comparison": ("Labels like 'Raw' / 'Edit' or 'Before' / 'After' framing two versions.", ()),
    "looped_footage": ("One short action repeated in rhythm.", ()),
    "spin_rotation": ("The frame rotates around its centre through the move, blurred by the speed.", ("spin",)),
    "transformation_build": ("The subject changes piece by piece in one continuous shot: parts fly on, paint wipes across.", ()),
    "broll_insert": ("A clip that shows what is being said, cut in over the voice.", ()),
    "comment_cta": ("A standing line like 'Comment EDIT and I'll send the file' that asks for a comment.", ()),
    "mirror_kaleidoscope": ("The frame mirrored into two or four copies that rotate or slide, turning the subject into a pattern.", ("mirror",)),
    "logo_animation": ("A brand mark animated on a flat colour, bouncing or shaking on the beat.", ()),
    "face_composite": ("A face cut out and placed somewhere absurd: in the sky, on an object, on a crowd.", ()),
    "shatter_transition": ("The frame breaks into shards that fall away to reveal the next shot.", ()),
    "ui_mockup_animation": ("Animated app interface (search bar, buttons, cursor clicks, check marks) telling the story.", ()),
    "torn_paper_reveal": ("The frame tears like paper to reveal an image or word underneath.", ()),
    "light_sync": ("Lights in the scene (headlights, indicators, neon) flash on the beat in a locked shot.", ()),
    "pov_camera": ("Handheld or gimbal footage from the viewer's eye line walking around the subject.", ()),
}

Energy = Literal["low", "medium", "high"]


class Hook(BaseModel):
    type: str
    # The hook is the opening up to this second; it is cut out as the hook clip.
    ends_s: float = Field(..., gt=0, le=10)
    on_screen_text: list[str] = []
    text_style: str = ""
    spoken: str = ""
    visual: str = Field(..., min_length=10)
    why_it_works: str = Field(..., min_length=10)
    # The hook as a recipe for somebody else's footage.
    template: str = Field(..., min_length=10)

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in HOOK_TYPES:
            raise ValueError(f"unknown hook type {value!r}; use one of {', '.join(HOOK_TYPES)}")
        return value


class Technique(BaseModel):
    id: str
    # Where it happens; each time gets a short example clip. Empty when it runs throughout.
    at_s: list[float] = []
    note: str = ""

    @field_validator("id")
    @classmethod
    def _known_technique(cls, value: str) -> str:
        if value not in TECHNIQUES:
            raise ValueError(f"unknown technique {value!r}; use one of {', '.join(TECHNIQUES)}")
        return value


class SoundEffect(BaseModel):
    # The nearest sound in our own synthesised set, which an edit may use freely.
    id: str
    at_s: list[float] = Field(..., min_length=1)
    note: str = ""

    @field_validator("id")
    @classmethod
    def _known_sound(cls, value: str) -> str:
        if value not in SOUNDS:
            raise ValueError(f"unknown sound {value!r}; use one of {', '.join(SOUNDS)}")
        return value


class Music(BaseModel):
    kind: Literal["song", "beat", "voiceover", "voiceover_and_music", "original_sound", "silent"]
    mood: str
    energy: Energy
    vocals: bool
    # How the picture follows the sound.
    sync: str = Field(..., min_length=5)
    # Whatever identifies the track: lyrics, language, genre. Never a guess at its title.
    track_hint: str = ""

    @field_validator("mood")
    @classmethod
    def _known_mood(cls, value: str) -> str:
        if value not in MOODS:
            raise ValueError(f"unknown mood {value!r}; use one of {', '.join(MOODS)}")
        return value


class ReelAnalysis(BaseModel):
    niche: str = Field(..., min_length=2)
    tags: list[str] = Field(..., min_length=1)
    hook: Hook
    music: Music
    techniques: list[Technique] = Field(..., min_length=1)
    sound_effects: list[SoundEffect] = []
    look: str
    look_note: str = ""

    @field_validator("look")
    @classmethod
    def _known_look(cls, value: str) -> str:
        if value not in LOOKS:
            raise ValueError(f"unknown look {value!r}; use one of {', '.join(LOOKS)}")
        return value
