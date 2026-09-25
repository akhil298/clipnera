"""FFmpeg filter-graph builders for hook transitions.

The cut clip on disk is ``[hook][clip]`` back to back. At render time it is
split at the hook boundary and re-laid as ``[hook][bridge][clip]`` in the same
pass that burns captions and the watermark, so a transition never costs an
extra encode and switching transitions never needs a re-cut.

Every id in ``catalog.py`` has a builder here. Builders return filter-chain
text; all timing is in seconds on each segment's own zero-based timeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hook_transitions.catalog import IMPACT_EFFECTS
from hook_transitions.resolver import TransitionSpec

SAMPLE_RATE = 48000
# Rewinding buffers frames in memory, so the tail is capped and downscaled.
MAX_REWIND_SECONDS = 3.0
# Length of the clip's opening that an impact effect treats.
IMPACT_SECONDS = 0.4
MAX_IMPACT_SOUND_SECONDS = 1.2
# Below these the split is not worth making: too short to read as a hook.
MIN_TEASER_SECONDS = 0.3
MIN_BODY_SECONDS = 1.0


@dataclass(frozen=True)
class MediaInfo:
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool

    @classmethod
    def from_probe(cls, probe: dict[str, Any]) -> "MediaInfo":
        streams = probe.get("streams") or []
        video = next((s for s in streams if s.get("codec_type") == "video"), streams[0] if streams else {})
        duration = float((probe.get("format") or {}).get("duration") or video.get("duration") or 0.0)
        return cls(
            width=int(video.get("width") or 1080),
            height=int(video.get("height") or 1920),
            fps=_rate(video.get("avg_frame_rate")) or _rate(video.get("r_frame_rate")) or 30.0,
            duration=duration,
            has_audio=any(s.get("codec_type") == "audio" for s in streams),
        )


@dataclass(frozen=True)
class BridgePlan:
    """One transition placed on one cut file."""

    spec: TransitionSpec
    teaser: float
    media: MediaInfo

    @property
    def gap(self) -> float:
        return self.spec.duration

    @property
    def body(self) -> float:
        return max(0.0, self.media.duration - self.teaser)

    @classmethod
    def make(cls, spec: TransitionSpec | None, teaser: float | None, media: MediaInfo) -> "BridgePlan | None":
        """A plan, or None when the file has no usable hook to bridge from."""
        if spec is None or not teaser or teaser < MIN_TEASER_SECONDS:
            return None
        if media.duration - teaser < MIN_BODY_SECONDS:
            return None
        return cls(spec=spec, teaser=teaser, media=media)


@dataclass(frozen=True)
class _Ctx:
    w: int
    h: int
    fps: float
    teaser: float
    body: float
    gap: float

    def frames(self, seconds: float) -> int:
        return max(1, round(seconds * self.fps))


def _rate(value: Any) -> float:
    try:
        num, _, den = str(value or "").partition("/")
        rate = float(num) / float(den or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0
    return rate if 1.0 <= rate <= 240.0 else 0.0


def _n(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") or "0"


def _even(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def _video_norm(c: _Ctx) -> str:
    return f"fps={_n(c.fps)},scale={c.w}:{c.h},setsar=1,format=yuv420p"


AUDIO_NORM = f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=stereo"


# --- Gap sources ----------------------------------------------------------------
# Each takes the context and returns (needs_input, chain). An input chain is
# applied to a copy of the cut file whose timeline starts at zero.

def _tail(c: _Ctx, length: float) -> tuple[float, float]:
    length = max(1.0 / c.fps, min(length, c.teaser))
    return c.teaser - length, length


def _freeze(c: _Ctx, at: float) -> str:
    """Hold the frame just before ``at`` for the whole gap.

    ``loop`` plus re-stamping, not ``tpad``: tpad's clone padding silently
    adds nothing on FFmpeg 7.x (the server's version) after a ``trim``, which
    left freeze bridges with no video at all.
    """
    start = max(0.0, at - 2.0 / c.fps)
    return (
        f"trim=start={_n(start)}:end={_n(at)},setpts=PTS-STARTPTS,"
        f"loop=loop={c.frames(c.gap) + 2}:size=1:start=0,setpts=N/({_n(c.fps)}*TB)"
    )


def _src_rewind(c: _Ctx) -> tuple[bool, str]:
    start, length = _tail(c, min(c.gap * 2.5, MAX_REWIND_SECONDS))
    return True, (
        f"trim=start={_n(start)}:end={_n(c.teaser)},setpts=PTS-STARTPTS,"
        f"scale={_even(c.w / 2)}:{_even(c.h / 2)},reverse,setpts=PTS*{_n(c.gap / length)}"
    )


def _src_slow_motion(c: _Ctx) -> tuple[bool, str]:
    start, length = _tail(c, c.gap / 3.0)
    return True, f"trim=start={_n(start)}:end={_n(c.teaser)},setpts=(PTS-STARTPTS)*{_n(c.gap / length)}"


def _body_window(c: _Ctx, at: float, length: float) -> float:
    """Start of a ``length`` window at fraction ``at`` of the clip, kept inside it."""
    latest = c.teaser + max(0.0, c.body - length)
    return min(latest, max(c.teaser, c.teaser + c.body * at - length / 2))


def _src_flash_forward(c: _Ctx) -> tuple[bool, str]:
    piece = c.gap / 3.0
    windows = "+".join(
        f"between(t,{_n(start)},{_n(start + piece)})"
        for start in (_body_window(c, at, piece) for at in (0.35, 0.6, 0.85))
    )
    return True, f"select='{windows}',setpts=N/({_n(c.fps)}*TB)"


def _peek(c: _Ctx, wanted: float) -> tuple[bool, str]:
    """A window of the clip's payoff retimed to fill the gap exactly.

    Retiming instead of padding keeps the length right on every FFmpeg version
    even when the clip is shorter than the window asked for.
    """
    length = min(wanted, c.body)
    start = _body_window(c, 0.75, length)
    return True, (
        f"trim=start={_n(start)}:duration={_n(length)},"
        f"setpts=(PTS-STARTPTS)*{_n(c.gap / length)}"
    )


def _src_sneak_peek(c: _Ctx) -> tuple[bool, str]:
    return _peek(c, c.gap)


def _src_sneak_peek_fast(c: _Ctx) -> tuple[bool, str]:
    return _peek(c, c.gap * 2.0)


def _src_color(color: str) -> Callable[[_Ctx], tuple[bool, str]]:
    def build(c: _Ctx) -> tuple[bool, str]:
        return False, f"color=c={color}:s={c.w}x{c.h}:r={_n(c.fps)}:d={_n(c.gap)}"
    return build


SOURCE_BUILDERS: dict[str, Callable[[_Ctx], tuple[bool, str]]] = {
    "rewind": _src_rewind,
    "freeze_frame": lambda c: (True, _freeze(c, c.teaser)),
    "slow_motion": _src_slow_motion,
    "flash_forward": _src_flash_forward,
    "sneak_peek": _src_sneak_peek,
    "sneak_peek_fast": _src_sneak_peek_fast,
    "first_frame": lambda c: (True, _freeze(c, c.teaser + 2.0 / c.fps)),
    "blur_card": lambda c: (True, f"{_freeze(c, c.teaser)},gblur=sigma=30,eq=brightness=-0.12"),
    "black_card": _src_color("black"),
    "white_card": _src_color("white"),
    "brand_card": _src_color("0x6D28D9"),
}


# --- Visual effects ---------------------------------------------------------------
# Each takes the context and the segment length it treats; input is already at
# the output size and frame rate.

def _zoompan(c: _Ctx, zoom: str) -> str:
    return (
        f"zoompan=z='{zoom}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":s={c.w}x{c.h}:fps={_n(c.fps)}"
    )


def _zoom(expr: Callable[[int, _Ctx], str]) -> Callable[[_Ctx, float], str]:
    return lambda c, d: _zoompan(c, expr(c.frames(d), c))


def _shake(c: _Ctx, d: float) -> str:
    w2, h2 = _even(c.w * 1.1), _even(c.h * 1.1)
    amp = min(w2 - c.w, h2 - c.h) / 2 * 0.9
    return (
        f"scale={w2}:{h2},crop={c.w}:{c.h}"
        f":x='{_n((w2 - c.w) / 2)}+{_n(amp)}*sin(n*2.1)'"
        f":y='{_n((h2 - c.h) / 2)}+{_n(amp)}*cos(n*2.9)'"
    )


def _tilt(c: _Ctx, d: float) -> str:
    return f"scale={_even(c.w * 1.12)}:{_even(c.h * 1.12)},rotate='0.07*sin(2*PI*t*3)':ow={c.w}:oh={c.h}:c=black"


def _fade(kind: str, color: str, at_end: bool, cap: float) -> Callable[[_Ctx, float], str]:
    def build(c: _Ctx, d: float) -> str:
        length = min(cap, d / 2)
        start = d - length if at_end else 0.0
        return f"fade=t={kind}:st={_n(start)}:d={_n(length)}:color={color}"
    return build


def _pixelate(c: _Ctx, d: float) -> str:
    return f"scale={_even(c.w / 24)}:{_even(c.h / 24)}:flags=area,scale={c.w}:{c.h}:flags=neighbor"


def _fixed(chain: str) -> Callable[[_Ctx, float], str]:
    return lambda c, d: chain


EFFECT_BUILDERS: dict[str, Callable[[_Ctx, float], str]] = {
    "zoom_in": _zoom(lambda n, c: f"1+0.3*on/{n}"),
    "zoom_out": _zoom(lambda n, c: f"1.35-0.35*on/{n}"),
    "slow_zoom": _zoom(lambda n, c: f"1+0.08*on/{n}"),
    "crash_zoom": _zoom(lambda n, c: f"if(lt(on,{_n(0.6 * n)}),1+0.05*on/{n},1.03+1.2*(on-{_n(0.6 * n)})/{_n(0.4 * n)})"),
    "zoom_pulse": _zoom(lambda n, c: f"1.12+0.1*sin(2*PI*on/{_n(c.fps / 2)})"),
    "shake": _shake,
    "spin": lambda c, d: f"rotate='2*PI*t/{_n(d)}':c=black",
    "tilt": _tilt,
    "whip_pan": lambda c, d: f"scroll=h={_n(2.0 / c.frames(d))},gblur=sigma=40:sigmaV=0.5",
    "rgb_split": _fixed("chromashift=cbh=14:crh=-14:cbv=4"),
    "glitch": _fixed("noise=alls=40:allf=t+u,chromashift=cbh=20:crh=-20:cbv=6,hue=H='2*sin(n*1.7)'"),
    "vhs": _fixed(
        "noise=alls=18:allf=t,chromashift=cbh=6:crh=-6,eq=saturation=1.35:contrast=1.1,"
        "drawgrid=w=iw:h=6:t=2:c=black@0.3"
    ),
    "pixelate": _pixelate,
    "blur": _fixed("gblur=sigma=24"),
    "dream": _fixed("gblur=sigma=5,eq=brightness=0.06:saturation=1.3"),
    "invert": _fixed("negate"),
    "black_white": _fixed("hue=s=0"),
    "noir": _fixed("hue=s=0,eq=contrast=1.45,vignette=PI/4"),
    "sepia": _fixed("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"),
    "vignette": _fixed("vignette=PI/4"),
    "strobe": _fixed("eq=brightness='0.45*lt(mod(n,4),2)':eval=frame"),
    "flash_in": _fade("in", "white", at_end=False, cap=0.25),
    "flash_out": _fade("out", "white", at_end=True, cap=0.25),
    "fade_in": _fade("in", "black", at_end=False, cap=0.35),
    "dip_black": _fade("out", "black", at_end=True, cap=0.3),
    "mirror": _fixed("hflip"),
    "warm_tone": _fixed("colorbalance=rs=0.2:gs=0.05:bs=-0.2:rm=0.12:bm=-0.12"),
    "cool_tone": _fixed("colorbalance=rs=-0.12:bs=0.22:rm=-0.08:bm=0.14"),
    "saturate": _fixed("eq=saturation=1.9"),
    "high_contrast": _fixed("eq=contrast=1.5:saturation=1.15"),
    "sketch": _fixed("edgedetect=mode=colormix:high=0.15:low=0.05"),
    "cinema_bars": _fixed(
        "drawbox=x=0:y=0:w=iw:h=ih*0.11:color=black:t=fill,"
        "drawbox=x=0:y=ih*0.89:w=iw:h=ih*0.11:color=black:t=fill"
    ),
}


# --- Sounds ---------------------------------------------------------------------
# Each takes the context, the length to fill and the hook-audio input label
# (None when the clip has no audio) and returns a chain producing audio.

def _eval(expr: str, seconds: float) -> str:
    return f"aevalsrc='{expr}':s={SAMPLE_RATE}:d={_n(seconds)}"


def _noise(color: str, amp: float, seconds: float, shaping: str) -> str:
    return f"anoisesrc=d={_n(seconds)}:c={color}:r={SAMPLE_RATE}:a={amp},{shaping}"


def _swell(seconds: float) -> str:
    """Rise then fall over ``seconds``.

    ``afade``, not a ``volume`` expression: volume's ``t`` is NaN on generated
    sources, which FFmpeg turns into a volume of 0 -- the sound went silent.
    """
    half = seconds / 2
    return f"afade=t=in:d={_n(half)}:curve=qsin,afade=t=out:st={_n(half)}:d={_n(half)}:curve=qsin"


def _hook_rewind(c: _Ctx, d: float, hook: str | None) -> str:
    if hook is None:
        return _silence(c, d, None)
    start, length = _tail(c, min(d * 2.5, MAX_REWIND_SECONDS))
    speed = max(1.0, length / d)
    return (
        f"[{hook}]atrim=start={_n(start)}:end={_n(c.teaser)},asetpts=PTS-STARTPTS,{AUDIO_NORM},"
        f"areverse,asetrate={round(SAMPLE_RATE * speed)},aresample={SAMPLE_RATE}"
    )


def _hook_echo(c: _Ctx, d: float, hook: str | None) -> str:
    if hook is None:
        return _silence(c, d, None)
    start, _ = _tail(c, 0.6)
    return (
        f"[{hook}]atrim=start={_n(start)}:end={_n(c.teaser)},asetpts=PTS-STARTPTS,{AUDIO_NORM},"
        f"apad=whole_dur={_n(d)},aecho=0.8:0.7:180|360:0.5|0.3,volume=0.8"
    )


def _silence(c: _Ctx, d: float, hook: str | None) -> str:
    return f"anullsrc=r={SAMPLE_RATE}:cl=stereo,atrim=duration={_n(d)}"


SOUND_BUILDERS: dict[str, Callable[[_Ctx, float, str | None], str]] = {
    "whoosh": lambda c, d, h: _noise("pink", 0.6, d, f"highpass=f=300,lowpass=f=3500,{_swell(d)}"),
    "swoosh": lambda c, d, h: _noise("white", 0.4, min(d, 0.35), f"highpass=f=1500,lowpass=f=7000,{_swell(min(d, 0.35))}"),
    "riser": lambda c, d, h: _eval(f"0.35*sin(2*PI*(150*t+900*t*t/{_n(d)}))*(t/{_n(d)})", d),
    "downlifter": lambda c, d, h: _eval(f"0.35*sin(2*PI*(1500*t-650*t*t/{_n(d)}))*(1-t/{_n(d)})", d),
    "reverse_cymbal": lambda c, d, h: _noise("white", 0.5, d, f"highpass=f=5000,afade=t=in:d={_n(d)}:curve=cub"),
    "boom": lambda c, d, h: _eval("0.9*sin(2*PI*50*t)*exp(-4*t)+0.3*sin(2*PI*90*t)*exp(-9*t)", min(d, 1.5)),
    "sub_drop": lambda c, d, h: _eval(f"0.9*sin(2*PI*(110*t-35*t*t/{_n(d)}))*exp(-1.5*t)", d),
    "impact_hit": lambda c, d, h: _eval("0.8*sin(2*PI*60*t)*exp(-7*t)+0.5*(random(0)*2-1)*exp(-30*t)", min(d, 1.0)),
    "click": lambda c, d, h: _eval("0.8*sin(2*PI*2200*t)*exp(-120*t)", min(d, 0.1)),
    "pop": lambda c, d, h: _eval("0.8*sin(2*PI*(600+900*exp(-25*t))*t)*exp(-18*t)", min(d, 0.3)),
    "ding": lambda c, d, h: _eval("0.45*sin(2*PI*1760*t)*exp(-4*t)+0.25*sin(2*PI*2637*t)*exp(-5*t)", min(d, 1.5)),
    "glitch_zap": lambda c, d, h: _eval("0.35*sgn(sin(2*PI*(220+660*mod(floor(t*18),3))*t))*lt(mod(t*24,1),0.6)", d),
    "heartbeat": lambda c, d, h: _eval("0.9*sin(2*PI*55*t)*(exp(-20*t)+gte(t,0.28)*exp(-20*(t-0.28)))", d),
    "tape_stop": lambda c, d, h: _eval(f"0.4*sin(2*PI*(330*t-165*t*t/{_n(d)}))*(1-t/{_n(d)})", d),
    "record_scratch": lambda c, d, h: _eval(
        "0.5*sin(2*PI*(500*t+40*sin(2*PI*9*t)))*exp(-2.5*t)+0.15*(random(0)*2-1)*exp(-4*t)", min(d, 0.8),
    ),
    "camera_shutter": lambda c, d, h: _eval(
        "0.7*(random(0)*2-1)*(exp(-60*t)+gte(t,0.09)*exp(-60*(t-0.09)))", min(d, 0.3),
    ),
    "beep": lambda c, d, h: f"sine=f=1000:r={SAMPLE_RATE}:d={_n(min(d, 0.6))},volume=0.3",
    "tick_tock": lambda c, d, h: _eval("0.7*sin(2*PI*(1400-400*mod(floor(t*4),2))*t)*exp(-80*mod(t,0.25))", d),
    "static_noise": lambda c, d, h: _noise("white", 0.18, d, "highpass=f=800"),
    "hook_rewind": _hook_rewind,
    "hook_echo": _hook_echo,
    "silence": _silence,
}


def _sound(c: _Ctx, sound: str, seconds: float, hook_audio: str | None, out: str) -> str:
    """A sound padded or trimmed to exactly ``seconds``, labelled ``out``."""
    chain = SOUND_BUILDERS[sound](c, seconds, hook_audio)
    return f"{chain},{AUDIO_NORM},apad=whole_dur={_n(seconds)},atrim=duration={_n(seconds)}[{out}]"


def _effects(c: _Ctx, effects: tuple[str, ...], seconds: float) -> str:
    return "".join(f",{EFFECT_BUILDERS[effect](c, seconds)}" for effect in effects)


def timeline_graph(plan: BridgePlan, text_filter: str | None = None) -> tuple[list[str], str, str]:
    """Filter chains that lay input 0 out as ``[hook][bridge][clip]``.

    Returns ``(chains, video_label, audio_label)``; the caller appends captions
    and the watermark to ``video_label`` and maps ``audio_label``.
    ``text_filter`` (e.g. an ``ass`` filter) is drawn over the bridge only.
    """
    spec = plan.spec
    media = plan.media
    c = _Ctx(
        w=_even(media.width), h=_even(media.height), fps=media.fps,
        teaser=plan.teaser, body=plan.body, gap=plan.gap,
    )
    norm = _video_norm(c)
    needs_input, source = SOURCE_BUILDERS[spec.source](c)
    impact_effects = IMPACT_EFFECTS[spec.impact]
    chains: list[str] = []

    # --- video ---
    outs = ["vt", "vb"] + (["vs"] if needs_input else [])
    chains.append(f"[0:v]setpts=PTS-STARTPTS,split={len(outs)}{''.join(f'[{o}]' for o in outs)}")
    chains.append(f"[vt]trim=end={_n(c.teaser)},setpts=PTS-STARTPTS,{norm}[tv]")

    body_trim = f"trim=start={_n(c.teaser)},setpts=PTS-STARTPTS,{norm}"
    if impact_effects:
        chains.append(f"[vb]{body_trim},split=2[bvi][bvr]")
        chains.append(
            f"[bvi]trim=end={_n(IMPACT_SECONDS)},setpts=PTS-STARTPTS"
            f"{_effects(c, impact_effects, IMPACT_SECONDS)},{norm}[bvi2]"
        )
        chains.append(f"[bvr]trim=start={_n(IMPACT_SECONDS)},setpts=PTS-STARTPTS[bvr2]")
        chains.append("[bvi2][bvr2]concat=n=2:v=1:a=0[bv]")
    else:
        chains.append(f"[vb]{body_trim}[bv]")

    gap_head = f"[vs]{source}" if needs_input else source
    text = f",{text_filter}" if text_filter else ""
    chains.append(
        f"{gap_head},setpts=PTS-STARTPTS,{norm}{_effects(c, spec.effects, c.gap)},{norm},"
        f"trim=duration={_n(c.gap)},setpts=PTS-STARTPTS{text}[gv]"
    )

    # --- audio ---
    hook_audio: str | None = None
    if media.has_audio:
        hook_sound = spec.sound in ("hook_rewind", "hook_echo")
        a_outs = ["at", "ab"] + (["as"] if hook_sound else [])
        chains.append(f"[0:a]asetpts=PTS-STARTPTS,asplit={len(a_outs)}{''.join(f'[{o}]' for o in a_outs)}")
        chains.append(f"[at]atrim=end={_n(c.teaser)},asetpts=PTS-STARTPTS,{AUDIO_NORM}[ta]")
        chains.append(f"[ab]atrim=start={_n(c.teaser)},asetpts=PTS-STARTPTS,{AUDIO_NORM}[ba0]")
        hook_audio = "as" if hook_sound else None
    else:
        chains.append(f"{_silence(c, c.teaser, None)},{AUDIO_NORM}[ta]")
        chains.append(f"{_silence(c, c.body, None)},{AUDIO_NORM}[ba0]")

    chains.append(_sound(c, spec.sound, c.gap, hook_audio, "ga"))

    if spec.impact_sound:
        chains.append(_sound(c, spec.impact_sound, min(MAX_IMPACT_SOUND_SECONDS, c.body), None, "isfx"))
        chains.append("[ba0][isfx]amix=inputs=2:duration=first:normalize=0[ba]")
    else:
        chains.append("[ba0]anull[ba]")

    chains.append("[tv][ta][gv][ga][bv][ba]concat=n=3:v=1:a=1[vjoin][acat]")
    # concat reports no frame rate when its inputs' time bases differ, and the
    # encoder then assumed the microsecond time base: 1,000,000 fps.
    chains.append(f"[vjoin]fps={_n(c.fps)}[vcat]")
    return chains, "vcat", "acat"
