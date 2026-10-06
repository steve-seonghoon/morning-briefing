"""GitHub Actions용: episodes-src/ 의 가장 최근 원고를 음성으로 만들어 게시한다.

원고:  episodes-src/YYYY-MM-DD.txt
메타:  episodes-src/YYYY-MM-DD.json (선택) {"summary": "...", "title": "..."}
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEEKDAYS = "월화수목금토일"

scripts = sorted((ROOT / "episodes-src").glob("*.txt"))
if not scripts:
    sys.exit("episodes-src/ 에 원고가 없습니다")
src = scripts[-1]
date = src.stem
d = dt.datetime.strptime(date, "%Y-%m-%d")
meta_path = src.with_suffix(".json")
meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
title = meta.get("title") or f"{d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]}) 모닝 브리핑"
summary = meta.get("summary", "")

out = ROOT / "out"
out.mkdir(exist_ok=True)
mp3 = out / f"{date}.mp3"
py = sys.executable
subprocess.run([py, "scripts/tts.py", str(src), str(mp3)], cwd=ROOT, check=True)

from mutagen.mp3 import MP3  # noqa: E402

minutes = MP3(mp3).info.length / 60
print(f"에피소드 길이: {minutes:.1f}분")
if not 20 <= minutes <= 40:
    print("::warning::에피소드 길이가 20~40분 범위를 벗어났습니다")

subprocess.run([py, "scripts/publish.py", "--mp3", str(mp3), "--script", str(src),
                "--title", title, "--summary", summary, "--date", date], cwd=ROOT, check=True)
