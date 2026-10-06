from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from broll import sources as broll_sources
from broll.ingest import matches_topic, orientation_of, quality_score, retry_wait, search_text
from broll.repository import Candidate
from broll.retrieval import BrollRetriever, SceneQuery, coverage, terms
from broll.sources import nasa, pexels, pixabay, wikimedia
from broll.sources.base import best_rendition


class TestRenditionChoice:
    def test_largest_file_up_to_1080(self):
        files = [{"width": 3840, "height": 2160}, {"width": 1920, "height": 1080}, {"width": 1280, "height": 720}]
        assert best_rendition(files)["width"] == 1920

    def test_smallest_when_all_are_bigger(self):
        files = [{"width": 3840, "height": 2160}, {"width": 2560, "height": 1440}]
        assert best_rendition(files)["width"] == 2560


class TestPexels:
    def test_parse(self):
        payload = {"videos": [{
            "id": 856193, "url": "https://www.pexels.com/video/aerial-view-of-city-at-night-856193/",
            "duration": 14, "width": 3840, "height": 2160, "user": {"name": "Jo", "url": "https://pexels.com/@jo"},
            "video_files": [
                {"file_type": "video/mp4", "width": 3840, "height": 2160, "link": "https://v/4k.mp4"},
                {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "https://v/hd.mp4"},
            ],
        }]}
        clip = pexels.parse(payload)[0]
        assert clip.title == "aerial view of city at night" and clip.download_url == "https://v/hd.mp4"
        assert clip.license_code == "pexels" and clip.attribution_text == "Video by Jo on Pexels"
        assert "aerial" in clip.tags and clip.duration_s == 14

    @pytest.mark.asyncio
    async def test_needs_a_key(self):
        with pytest.raises(RuntimeError):
            await pexels.PexelsSource(api_key="").search("city", 5)


class TestPixabay:
    def test_parse(self):
        payload = {"hits": [{
            "id": 1, "pageURL": "https://pixabay.com/videos/x-1/", "tags": "money, coins, finance", "duration": 9,
            "user": "ann", "user_id": 7,
            "videos": {"large": {"url": "https://p/l.mp4", "width": 1920, "height": 1080},
                       "small": {"url": "https://p/s.mp4", "width": 960, "height": 540}},
        }]}
        clip = pixabay.parse(payload)[0]
        assert clip.tags == ["money", "coins", "finance"] and clip.download_url == "https://p/l.mp4"
        assert clip.author_url == "https://pixabay.com/users/ann-7/"


class TestNasa:
    @pytest.mark.parametrize(("title", "footage"), [
        ("Earth from orbit", True), ("Mars Briefing", False), ("NASA Science Live: Climate", False), ("Panel on Artemis", False),
    ])
    def test_talking_heads_are_skipped(self, title, footage):
        assert nasa.is_footage({"title": title, "keywords": []}) is footage

    def test_prefers_the_medium_rendition(self):
        urls = ["http://images-assets.nasa.gov/video/a b/a b~orig.mp4", "http://images-assets.nasa.gov/video/a b/a b~medium.mp4"]
        assert nasa.pick_video(urls) == "https://images-assets.nasa.gov/video/a%20b/a%20b~medium.mp4"

    def test_public_domain_with_credit(self):
        clip = nasa.to_clip({"nasa_id": "x1", "title": "Launch", "keywords": ["NASA", "Rocket"], "center": "KSC"}, "https://v")
        assert clip.license_code == "pd_us_gov" and clip.tags == ["rocket"] and clip.attribution_text == "Courtesy NASA"


class TestWikimedia:
    @pytest.mark.parametrize(("name", "code"), [
        ("CC0", "cc0"), ("Public domain", "public_domain"), ("PD-USGov", "public_domain"),
        ("CC BY 4.0", "cc_by"), ("CC BY-SA 4.0", None), ("CC BY-NC 2.0", None), ("GFDL", None),
    ])
    def test_only_commercial_non_share_alike_licences(self, name, code):
        assert wikimedia.accepted_license(name) == code

    def test_parse_keeps_attribution_and_drops_share_alike(self):
        def page(pid, licence):
            return {"pageid": pid, "title": "File:Ocean_waves.ogv", "imageinfo": [{
                "url": "https://u/Ocean.ogv?x=1", "descriptionurl": "https://c/File:Ocean", "mime": "application/ogg",
                "width": 1920, "height": 1080, "duration": 7.5,
                "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": "<a href='x'>Mo</a>"},
                                "ImageDescription": {"value": "Waves at sea"}},
            }]}
        clips = wikimedia.parse({"query": {"pages": {"1": page(1, "CC BY 4.0"), "2": page(2, "CC BY-SA 3.0")}}})
        assert len(clips) == 1
        clip = clips[0]
        assert clip.download_url == "https://u/Ocean.ogv" and clip.author == "Mo"
        assert clip.attribution_text == "Ocean waves by Mo, CC BY 4.0, via Wikimedia Commons"


class TestSources:
    def test_only_configured_sources_run(self, monkeypatch):
        monkeypatch.setattr(broll_sources, "get_settings", lambda: SimpleNamespace(BROLL_SOURCES="nasa,wikimedia"))
        assert [s.name for s in broll_sources.enabled_sources()] == ["nasa", "wikimedia"]
        assert [s.name for s in broll_sources.enabled_sources(["pixabay", "nasa"])] == ["nasa"]


class TestIngestHelpers:
    def test_quality_and_orientation(self):
        assert quality_score(1080) == 1.0 and quality_score(720) == 0.8
        assert orientation_of(1920, 1080) == "landscape" and orientation_of(1080, 1920) == "portrait"
        assert orientation_of(1000, 1050) == "square"

    def test_search_text(self):
        assert search_text("City at night", ["neon", "street"]) == "City at night neon street"

    @pytest.mark.parametrize(("title", "tags", "topic", "kept"), [
        ("Perseverance Rover's Descent and Touchdown on Mars", ["mars", "landing"], "tea", False),
        ("Science Launching to Space Station", ["rocket"], "3d printer", False),
        ("Waves breaking on the shore", [], "ocean waves", False),
        ("Ocean wave at sunset", [], "ocean waves", True),
        ("Launch of Artemis I", ["rocket", "launch"], "rocket launch", True),
        ("Steam rising from a cup", ["tea", "kitchen"], "tea", True),
        ("Sunset over the sea", [], "sunset clouds", False),
    ])
    def test_matches_topic_needs_every_topic_word_in_title_or_tags(self, title, tags, topic, kept):
        assert matches_topic(SimpleNamespace(title=title, tags=tags), topic) is kept

    @pytest.mark.parametrize(("status", "headers", "attempt", "wait"), [
        (429, {"retry-after": "7"}, 1, 7.0), (429, {}, 2, 10.0), (503, {"retry-after": "999"}, 1, 60.0),
        (404, {}, 1, None), (429, {}, 4, None),
    ])
    def test_retry_wait(self, status, headers, attempt, wait):
        response = httpx.Response(status, headers=headers, request=httpx.Request("GET", "https://x"))
        assert retry_wait(response, attempt) == wait


def asset(asset_id, text, source_id=None, quality=0.8, embedding=None):
    return SimpleNamespace(id=asset_id, search_text=text, source="wikimedia", source_id=source_id or asset_id,
                           quality_score=quality, embedding=embedding)


class FakeRepo:
    def __init__(self, candidates, recent=(), swaps=None):
        self.candidates, self.recent, self.swaps, self.queries = candidates, set(recent), swaps or {}, []

    async def recently_used(self, user_id):
        return self.recent

    async def search(self, query, **kwargs):
        self.queries.append((query, kwargs))
        return [c for c in self.candidates if c.asset.id not in (kwargs.get("exclude_ids") or [])]

    async def swap_rates(self, ids):
        return self.swaps


class TestRetrieval:
    def test_terms_drop_stopwords_and_repeats(self):
        assert terms("The city at night, the CITY lights") == ["city", "night", "lights"]

    def test_coverage_matches_word_forms(self):
        assert coverage(["cities", "night"], "aerial city at night") == 1.0
        assert coverage(["ocean"], "mountain lake") == 0.0

    @pytest.mark.asyncio
    async def test_best_covering_asset_wins_and_is_not_reused(self):
        city = Candidate(asset("a", "aerial city skyline at night"), 0.2, True)
        lake = Candidate(asset("b", "mountain lake"), 0.3, True)
        city2 = Candidate(asset("c", "city night traffic", source_id="a"), 0.1, True)
        repo = FakeRepo([city, lake, city2])
        picks = await BrollRetriever(repo).find([SceneQuery("city at night"), SceneQuery("night city lights")], user_id="u")
        assert picks[0].best.asset.id == "a"
        # Scene 2 cannot reuse the same source clip, even through another of its shots.
        assert picks[1].best.asset.id == "b"
        assert repo.queries[0][0] == "city or night"

    @pytest.mark.asyncio
    async def test_recently_used_assets_are_excluded(self):
        repo = FakeRepo([Candidate(asset("a", "city night"), 0.2, True)], recent={"a"})
        picks = await BrollRetriever(repo).find([SceneQuery("city night")], user_id="u")
        assert picks[0].best is None

    @pytest.mark.asyncio
    async def test_often_swapped_assets_rank_lower(self):
        good = Candidate(asset("a", "coffee cup"), 0.2, True)
        swapped = Candidate(asset("b", "coffee cup"), 0.2, True)
        picks = await BrollRetriever(FakeRepo([swapped, good], swaps={"b": 0.9})).find([SceneQuery("coffee cup")])
        assert picks[0].best.asset.id == "a"

    @pytest.mark.asyncio
    async def test_embeddings_add_meaning(self):
        class Embedder:
            async def embed(self, texts):
                return [[1.0, 0.0] for _ in texts]

        near = Candidate(asset("a", "growth", embedding=[1.0, 0.0]), 0.2, True)
        far = Candidate(asset("b", "growth", embedding=[0.0, 1.0]), 0.2, True)
        picks = await BrollRetriever(FakeRepo([far, near]), Embedder()).find([SceneQuery("growth")])
        assert picks[0].best.asset.id == "a"


class TestStem:
    @pytest.mark.parametrize(("word", "root"), [("cities", "city"), ("waves", "wave"), ("running", "run"), ("stopped", "stop"), ("glass", "glass"), ("sea", "sea")])
    def test_stem(self, word, root):
        from broll.retrieval import stem

        assert stem(word) == root

    def test_verb_forms_meet(self):
        assert coverage(["running", "dogs"], "dog runs on the beach") == 1.0


def _words(n, gap=0.5, start=0.0, text="word"):
    return [{"start": start + i * gap, "end": start + i * gap + 0.4, "word": f"{text}{i}"} for i in range(n)]


class TestPlannerRules:
    def _clip(self, n=60, spans=None):
        from broll.planner import ClipWords

        return ClipWords(words=_words(n), spans=spans or [(0.0, n * 0.5)])

    def test_a_good_range_becomes_a_timed_cutaway(self):
        from broll.planner import validate

        cutaways = validate([{"from": 10, "to": 14, "query": "city street"}], self._clip())
        assert [(c.start, c.end, c.query) for c in cutaways] == [(5.0, 7.4, "city street")]

    def test_rules(self):
        from broll.planner import MAX_CUTAWAY_SECONDS, validate

        clip = self._clip()
        # Nothing in the first two seconds, nothing without a query, nothing out of range.
        assert validate([{"from": 1, "to": 3, "query": "x"}], clip) == []
        assert validate([{"from": 10, "to": 12, "query": ""}], clip) == []
        assert validate([{"from": 10, "to": 999, "query": "x"}], clip) == []
        # Long ranges are capped; short ones stretched to the minimum.
        long = validate([{"from": 10, "to": 40, "query": "x"}], clip)[0]
        assert long.end - long.start == pytest.approx(MAX_CUTAWAY_SECONDS)
        # Too close to the previous cutaway is dropped.
        close = validate([{"from": 10, "to": 12, "query": "a"}, {"from": 14, "to": 16, "query": "b"}], clip)
        assert [c.query for c in close] == ["a"]

    def test_never_more_than_40_percent_broll(self):
        from broll.planner import validate

        raw = [{"from": i, "to": i + 6, "query": f"q{i}"} for i in range(6, 60, 10)]
        cutaways = validate(raw, self._clip())
        assert sum(c.end - c.start for c in cutaways) <= 0.4 * 30.0

    def test_a_cutaway_never_crosses_a_cut_between_spans(self):
        from broll.planner import validate

        clip = self._clip(spans=[(0.0, 8.0), (20.0, 30.0)])
        # Word 18 ends at 9.4 s, past the first span's end at 8 s, where the picture cuts away.
        cut = validate([{"from": 12, "to": 18, "query": "x"}], clip)[0]
        assert cut.start == 6.0 and cut.end == 8.0

    @pytest.mark.asyncio
    async def test_unreadable_answer_gives_no_cutaways(self):
        from broll.planner import plan_cutaways

        class Client:
            async def chat(self, messages, **kwargs):
                return "not json"

        assert await plan_cutaways([self._clip()], Client()) == [[]]


class TestCutTimeline:
    def test_source_to_cut_with_hook_and_spans(self):
        from clip_generation.hook import Hook, cut_to_source, source_to_cut

        hook, spans = Hook(50.0, 53.0), [(10.0, 20.0), (30.0, 35.0)]
        assert source_to_cut(12.0, 10.0, 35.0, hook, spans) == 5.0
        assert source_to_cut(31.0, 10.0, 35.0, hook, spans) == 14.0
        assert source_to_cut(25.0, 10.0, 35.0, hook, spans) is None
        assert cut_to_source(14.0, 10.0, 35.0, hook, spans) == 31.0


class TestPlanStorage:
    def test_round_trip_and_bad_json(self):
        from broll.cutaways import Placement, dump_plan, load_plan

        plan = [Placement(1.0, 3.0, "city", "a1", 0.8, ["a2"])]
        assert load_plan(dump_plan(plan)) == plan
        assert load_plan("{broken") == [] and load_plan(None) == []

    def test_clip_words_keep_only_the_body(self):
        from broll.cutaways import clip_words

        clip = SimpleNamespace(start_time=0.0, end_time=10.0, edit_spans="[[0, 4], [6, 10]]", transcript=[
            {"words": [{"start": 1.0, "end": 1.5, "word": "a"}, {"start": 5.0, "end": 5.5, "word": "cut"}, {"start": 7.0, "end": 7.5, "word": "b"}]},
        ])
        assert [w["word"] for w in clip_words(clip).words] == ["a", "b"]


class TestOverlayRender:
    @pytest.mark.asyncio
    async def test_broll_replaces_the_picture_only_during_its_window(self, tmp_path):
        import subprocess

        import cv2
        import numpy as np

        from broll.cutaways import overlay_graph
        from broll.renditions import run

        base, shot, out = tmp_path / "base.mp4", tmp_path / "shot.mp4", tmp_path / "out.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:r=25:d=4",
                        "-f", "lavfi", "-i", "sine=d=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(base)], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1080x1920:r=25:d=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(shot)], check=True)
        graph, label = overlay_graph([(1.0, 2.5)], 360, 640)
        await run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(base), "-i", str(shot), "-filter_complex", graph,
                   "-map", f"[{label}]", "-map", "0:a?", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)])

        capture, means = cv2.VideoCapture(str(out)), []
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            means.append(float(np.mean(frame)))
        assert len(means) == 100  # length unchanged, audio kept alongside
        assert means[10] < 20 and means[45] > 230 and means[80] < 20  # black, white B-roll, black again
        audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout.strip()
        assert audio


class TestGoodMatch:
    def test_subject_match_beats_adjectives(self):
        from broll.cutaways import good_match
        from broll.retrieval import Scored

        pick = Scored(asset("a", "sandy beach at sunset"), 0.5, coverage=1 / 3)
        assert good_match(pick, "beach")
        assert not good_match(pick, "mountain")
        assert good_match(Scored(asset("b", "x"), 0.5, coverage=0.5), "")

    def test_planner_keeps_the_subject(self):
        from broll.planner import ClipWords, validate

        clip = ClipWords(words=_words(40), spans=[(0.0, 20.0)])
        cut = validate([{"from": 10, "to": 13, "query": "sunny beach waves", "subject": "beach"}], clip)[0]
        assert cut.subject == "beach"
