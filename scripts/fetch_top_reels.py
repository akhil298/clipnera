"""Download each creator's top Instagram reels, ranked by views then likes.

Instagram blocks anonymous profile listing, so the script borrows the Instagram
session from a browser you are logged into (a throwaway account is safer).

Usage:
    python scripts/fetch_top_reels.py creator_one creator_two --top 5
    python scripts/fetch_top_reels.py -f usernames.txt --top 10 --scan 60 --browser chrome
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import instaloader
import yt_dlp
from yt_dlp.cookies import extract_cookies_from_browser

CSV_FIELDS = ["rank", "shortcode", "url", "views", "likes", "comments", "posted_at", "caption"]


@dataclass
class ReelStats:
    shortcode: str
    url: str
    views: int
    likes: int
    comments: int
    posted_at: str
    caption: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("usernames", nargs="*", help="Instagram usernames (without @)")
    parser.add_argument("-f", "--file", type=Path, help="Text file with one username per line")
    parser.add_argument("--top", type=int, default=5, help="Reels to download per creator (default 5)")
    parser.add_argument("--scan", type=int, default=50, help="Most recent reels to rank per creator (default 50)")
    parser.add_argument("--browser", default="chrome", help="Browser to borrow the Instagram login from")
    parser.add_argument("--out", type=Path, default=Path.home() / "Downloads" / "reels", help="Output folder")
    parser.add_argument("--stats-only", action="store_true", help="Write the CSV without downloading videos")
    args = parser.parse_args()

    if args.file:
        args.usernames += [line.strip().lstrip("@") for line in args.file.read_text().splitlines() if line.strip()]
    if not args.usernames:
        parser.error("give at least one username or --file")
    return args


def browser_cookies(browser: str) -> dict[str, str]:
    jar = extract_cookies_from_browser(browser)
    cookies = {c.name: c.value for c in jar if c.domain.endswith("instagram.com")}
    if "sessionid" not in cookies:
        sys.exit(f"No Instagram login found in {browser}. Log in to instagram.com there first.")
    return cookies


def logged_in_loader(cookies: dict[str, str]) -> instaloader.Instaloader:
    loader = instaloader.Instaloader(quiet=True, max_connection_attempts=2)
    loader.load_session("", cookies)
    username = loader.test_login()
    if not username:
        sys.exit("Instagram rejected the browser session. Log in again in the browser and retry.")
    loader.context.username = username
    print(f"Logged in as @{username}")
    return loader


def scan_reels(loader: instaloader.Instaloader, username: str, limit: int) -> list[ReelStats]:
    profile = instaloader.Profile.from_username(loader.context, username)
    reels = []
    for post in itertools.islice(profile.get_reels(), limit):
        reels.append(
            ReelStats(
                shortcode=post.shortcode,
                url=f"https://www.instagram.com/reel/{post.shortcode}/",
                views=post.video_play_count or post.video_view_count or 0,
                likes=max(post.likes, 0),  # -1 when the creator hides like counts
                comments=post.comments,
                posted_at=post.date_utc.isoformat(),
                caption=(post.caption or "").replace("\n", " ")[:200],
            )
        )
        time.sleep(random.uniform(1.0, 2.5))  # one metadata request per reel; stay under rate limits
    return sorted(reels, key=lambda r: (r.views, r.likes), reverse=True)


def write_csv(path: Path, reels: list[ReelStats]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for rank, reel in enumerate(reels, start=1):
            writer.writerow({"rank": rank, **asdict(reel)})


def download(reels: list[ReelStats], folder: Path, browser: str) -> None:
    options = {
        "outtmpl": str(folder / "%(autonumber)02d_%(id)s.%(ext)s"),
        "cookiesfrombrowser": (browser,),
        # Instagram serves 1080p only as VP9, which QuickTime can't play; re-encode to H.264 while merging audio.
        "postprocessor_args": {
            "merger+ffmpeg_o": "-c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -movflags +faststart -c:a copy".split()
        },
        "quiet": True,
        "noprogress": True,
        "ignoreerrors": True,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([r.url for r in reels])


def main() -> None:
    args = parse_args()
    loader = logged_in_loader(browser_cookies(args.browser))
    run_dir = args.out / datetime.now().strftime("%Y-%m-%d_%H%M")

    for username in args.usernames:
        print(f"\n@{username}: scanning up to {args.scan} reels…")
        try:
            reels = scan_reels(loader, username, args.scan)
        except instaloader.exceptions.InstaloaderException as exc:
            print(f"  skipped: {exc}")
            continue

        folder = run_dir / username
        folder.mkdir(parents=True, exist_ok=True)
        write_csv(folder / "stats.csv", reels)
        top = reels[: args.top]
        for rank, reel in enumerate(top, start=1):
            print(f"  #{rank} {reel.url}  views={reel.views:,} likes={reel.likes:,}")

        if not args.stats_only:
            download(top, folder, args.browser)
        print(f"  saved to {folder}")


if __name__ == "__main__":
    main()
