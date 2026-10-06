"""Motion graphics and sound effects for generated clips.

A clip's moments (a list read out, a number that matters, a place or a name, a
call to action, a big laugh) are found once when the clip is generated, turned
into a plan of graphic cues with their sounds, and stored on the clip. Every
export burns the plan in the same pass as the captions, so graphics, captions
and the hook bridge share one timeline and one encode.

Nothing is added on a guess: every cue carries the words it came from, every
icon matches a word that was said, and a cue that would cover a face, the
content being shown, or another cue is dropped rather than squeezed in.
"""
