#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键转码 + 自动验证：把手机录音（m4a/mp3 等）转成 SOE 要求的 16k/16bit/单声道 wav。

用法（在 spike 目录）：
    python transcode.py                # 转码当前目录所有 m4a/mp3/wav/aac/amr
    python transcode.py --keep-raw     # 转码后保留原始文件（默认移入 raw_audio/ 备份）

特性：
  - ffmpeg 用 imageio-ffmpeg 自带的二进制（pip 装的，无需单独安装 ffmpeg）
  - 转完自动用 wave 模块验证 16000Hz / mono / 16bit，不合格会报错
  - 自动按 samples.csv 里的 sample_id 检查缺失（A01..D06 哪条还没录，一目了然）
"""

import argparse
import csv
import shutil
import subprocess
import sys
import wave
from pathlib import Path

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    print("错误：缺少 imageio-ffmpeg。请先执行：")
    print('  "C:/Users/Horiz/.workbuddy/binaries/python/envs/default/Scripts/python.exe" '
          "-m pip install imageio-ffmpeg")
    sys.exit(1)

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "wav16k"
RAW_DIR = HERE / "raw_audio"
AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".amr", ".flac", ".ogg", ".wma"}
SAMPLES_CSV = HERE / "samples.csv"


def transcode_one(src: Path, dst: Path) -> None:
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败：{r.stderr.strip()[:200]}")


def verify_wav(path: Path) -> tuple[bool, str]:
    """用 wave 模块直接读 wav 头，验证 16000Hz / 单声道 / 16bit。"""
    try:
        with wave.open(str(path), "rb") as w:
            rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
    except wave.Error as e:
        return False, f"不是合法 wav（{e}）"
    ok = rate == 16000 and ch == 1 and width == 2
    detail = f"{rate}Hz / {'mono' if ch == 1 else ch + 'ch'} / {width * 8}bit"
    return ok, detail


def expected_ids() -> list[str]:
    if not SAMPLES_CSV.exists():
        return []
    lines = [l for l in SAMPLES_CSV.read_text(encoding="utf-8-sig").splitlines()
             if not l.lstrip().startswith("#")]
    return [r["sample_id"] for r in csv.DictReader(lines) if r.get("sample_id")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-raw", action="store_true", help="原始文件保留在原地（默认移入 raw_audio/）")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)

    sources = sorted(p for p in HERE.iterdir()
                     if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
    # 跳过 wav16k / raw_audio 目录里的文件（只扫 spike 根目录，天然不会包含）
    if not sources:
        print("未在 spike 目录找到音频文件（支持 m4a/mp3/wav/aac/amr/flac/ogg/wma）。")
        print("请把录音文件放在", HERE)
        sys.exit(1)

    print(f"ffmpeg：{FFMPEG}")
    print(f"待转码：{len(sources)} 个文件\n" + "-" * 60)

    ok_list, fail_list = [], []
    for src in sources:
        stem = src.stem  # 例如 A01（要求录音时已按编号命名）
        dst = OUT_DIR / f"{stem}.wav"
        try:
            transcode_one(src, dst)
            good, detail = verify_wav(dst)
            if good:
                ok_list.append(stem)
                print(f"  ✓ {stem:<8} -> wav16k/{stem}.wav  [{detail}]")
                if not args.keep_raw:
                    shutil.move(str(src), RAW_DIR / src.name)
            else:
                fail_list.append((stem, detail))
                print(f"  ✘ {stem:<8} 参数不对 [{detail}]")
        except Exception as e:
            fail_list.append((stem, str(e)))
            print(f"  ✘ {stem:<8} {e}")

    print("-" * 60)
    print(f"成功 {len(ok_list)} / 失败 {len(fail_list)}")

    # 对照 samples.csv 找缺口
    want = expected_ids()
    if want:
        missing = [i for i in want if i not in set(ok_list)]
        extra = [p.stem for p in OUT_DIR.glob("*.wav") if p.stem not in set(want)]
        print(f"\n对照 samples.csv（应录 {len(want)} 条）：")
        if missing:
            print(f"  ⏳ 还没录/没转成功 {len(missing)} 条：{' '.join(missing)}")
        else:
            print("  ✓ 36 条齐了，可以跑评测：")
            print('    "C:/Users/Horiz/.workbuddy/binaries/python/envs/default/Scripts/python.exe" run_eval.py --limit 1')
        if extra:
            print(f"  ⚠ 多出来的 wav（清单里没有）：{' '.join(extra)}")

    if fail_list:
        print("\n失败明细：")
        for stem, why in fail_list:
            print(f"  {stem}: {why}")
        sys.exit(1)


if __name__ == "__main__":
    main()
