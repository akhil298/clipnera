"""What is on screen, over time, for the AI director.

The director reads the transcript only, so it cannot tell a moment that is
strong on screen (a demo, a reaction, someone walking out) from one that is not.
This package sends the video, silent and downscaled, to a cheap Gemini vision
model in short pieces, and turns the reply into notes on the transcript lines:
``12 41.0 A [sees: host holds up a phone, laughing] Look at this``.

It is optional and self-contained. With ``VISUAL_TIMELINE_ENABLED=false`` or no
``GEMINI_API_KEY`` it does nothing and costs nothing. To remove it entirely:

* delete this folder and ``tests/test_visual_timeline.py``;
* in ``content_intelligence/service.py``, drop the ``visual_timeline`` import and
  its three uses (``describe_video``, ``attach_scenes`` twice);
* delete the ``VISUAL_TIMELINE_*`` settings in ``core/config.py``.

``Sentence.scene`` and the ``[sees: ...]`` legend line can stay: they are inert
when nothing fills them.
"""

from visual_timeline.scenes import attach_scenes
from visual_timeline.timeline import describe_video

__all__ = ["attach_scenes", "describe_video"]
