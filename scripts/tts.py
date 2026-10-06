"""원고(txt)를 Edge TTS로 읽어 하나의 MP3로 만든다.

사용법: python scripts/tts.py <원고.txt> <출력.mp3> [--voice ko-KR-SunHiNeural] [--rate +15%]
"""
import argparse
import asyncio
import re
import sys

import edge_tts

CHUNK_CHARS = 1500  # 요청 하나당 글자 수 (너무 길면 Edge가 끊는다)


def clean(text: str) -> str:
    # 마크다운 기호, 괄호 속 메모 등 읽으면 안 되는 것 제거
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`>|]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return text.strip()


def split_chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    # 문단 → 문장 단위로 잘라 limit 이하 묶음을 만든다
    sentences = re.split(r"(?<=[.!?。])\s+|\n{2,}", text)
    chunks, cur = [], ""
    for s in (s.strip() for s in sentences):
        if not s:
            continue
        if cur and len(cur) + len(s) + 1 > limit:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


async def synth(chunk: str, voice: str, rate: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            buf = bytearray()
            async for msg in edge_tts.Communicate(chunk, voice, rate=rate).stream():
                if msg["type"] == "audio":
                    buf.extend(msg["data"])
            if buf:
                return bytes(buf)
        except Exception as e:  # 네트워크 오류 등은 재시도
            print(f"  재시도 {attempt + 1}: {e}", file=sys.stderr)
            await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError("TTS 실패")


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("script")
    p.add_argument("out")
    p.add_argument("--voice", default="ko-KR-SunHiNeural")
    p.add_argument("--rate", default="+15%")
    a = p.parse_args()

    text = clean(open(a.script, encoding="utf-8").read())
    chunks = split_chunks(text)
    print(f"{len(text)}자, {len(chunks)}개 조각")

    with open(a.out, "wb") as f:
        for i, c in enumerate(chunks, 1):
            f.write(await synth(c, a.voice, a.rate))
            print(f"  {i}/{len(chunks)}")

    from mutagen.mp3 import MP3

    print(f"완료: {a.out} ({MP3(a.out).info.length / 60:.1f}분)")


if __name__ == "__main__":
    asyncio.run(main())
