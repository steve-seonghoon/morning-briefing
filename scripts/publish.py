"""새 에피소드를 gh-pages 브랜치(=팟캐스트 피드 사이트)에 올린다.

gh-pages는 매번 히스토리 없이 새로 만들어 force push 한다 → 레포 용량이 계속 늘지 않음.
최근 KEEP개 에피소드만 유지한다.

사용법: python scripts/publish.py --mp3 out/2026-10-07.mp3 --script out/2026-10-07.txt \
            --title "10월 7일 (수) 모닝 브리핑" --summary "오늘의 주요 뉴스: ..."
"""
import argparse
import datetime as dt
import email.utils
import html
import json
import os
import shutil
import subprocess
from pathlib import Path

from mutagen.mp3 import MP3

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SITE = ROOT / "site"
KEEP = 10
KST = dt.timezone(dt.timedelta(hours=9))


def sh(*args, cwd=ROOT, check=True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def fetch_existing_site():
    shutil.rmtree(SITE, ignore_errors=True)
    SITE.mkdir()
    if sh("git", "fetch", "origin", "gh-pages", check=False).returncode == 0:
        archive = subprocess.run(["git", "archive", "FETCH_HEAD"], cwd=ROOT, check=True, capture_output=True)
        subprocess.run(["tar", "-x", "-C", str(SITE)], input=archive.stdout, check=True)
    (SITE / "episodes").mkdir(exist_ok=True)


def add_episode(a):
    date = a.date or dt.datetime.now(KST).strftime("%Y-%m-%d")
    ep = SITE / "episodes"
    shutil.copy(a.mp3, ep / f"{date}.mp3")
    if a.script:
        shutil.copy(a.script, ep / f"{date}.txt")
    meta = {"date": date, "title": a.title, "summary": a.summary,
            "duration": int(MP3(ep / f"{date}.mp3").info.length)}
    (ep / f"{date}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def prune():
    metas = sorted((SITE / "episodes").glob("*.json"), reverse=True)
    for old in metas[KEEP:]:
        for f in (SITE / "episodes").glob(f"{old.stem}.*"):
            f.unlink()


def build_feed():
    base = CONFIG["base_url"].rstrip("/")
    items = []
    for m in sorted((SITE / "episodes").glob("*.json"), reverse=True):
        meta = json.loads(m.read_text(encoding="utf-8"))
        mp3 = m.with_suffix(".mp3")
        pub = dt.datetime.strptime(meta["date"], "%Y-%m-%d").replace(hour=7, tzinfo=KST)
        d = meta["duration"]
        items.append(f"""    <item>
      <title>{html.escape(meta['title'])}</title>
      <description>{html.escape(meta['summary'])}</description>
      <pubDate>{email.utils.format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">{CONFIG['slug']}-{meta['date']}</guid>
      <enclosure url="{base}/episodes/{mp3.name}" length="{mp3.stat().st_size}" type="audio/mpeg"/>
      <itunes:duration>{d // 60}:{d % 60:02d}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{html.escape(CONFIG['title'])}</title>
    <link>{base}/</link>
    <language>ko</language>
    <description>{html.escape(CONFIG['description'])}</description>
    <itunes:author>{html.escape(CONFIG['author'])}</itunes:author>
    <itunes:image href="{base}/cover.png"/>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (SITE / "feed.xml").write_text(feed, encoding="utf-8")
    shutil.copy(ROOT / "assets" / "cover.png", SITE / "cover.png")
    (SITE / ".nojekyll").touch()
    (SITE / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><title>{html.escape(CONFIG["title"])}</title>'
        f'<p>팟캐스트 앱에서 이 주소를 구독하세요: <code>{base}/feed.xml</code></p>', encoding="utf-8")


def push():
    remote = sh("git", "remote", "get-url", "origin").stdout.strip()
    if os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY"):
        remote = f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{os.environ['GITHUB_REPOSITORY']}.git"
    shutil.rmtree(SITE / ".git", ignore_errors=True)
    sh("git", "init", "-q", "-b", "gh-pages", cwd=SITE)
    sh("git", "add", "-A", cwd=SITE)
    sh("git", "-c", "user.name=Morning Briefing Bot", "-c", "user.email=bot@users.noreply.github.com",
       "commit", "-q", "-m", f"Update feed {dt.datetime.now(KST):%Y-%m-%d %H:%M}", cwd=SITE)
    r = sh("git", "push", "-f", remote, "gh-pages", cwd=SITE, check=False)
    if r.returncode != 0:
        raise SystemExit(f"push 실패:\n{r.stderr}")
    print(f"게시 완료: {CONFIG['base_url'].rstrip('/')}/feed.xml")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mp3", required=True)
    p.add_argument("--script")
    p.add_argument("--title", required=True)
    p.add_argument("--summary", default="")
    p.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    a = p.parse_args()
    fetch_existing_site()
    add_episode(a)
    prune()
    build_feed()
    push()
