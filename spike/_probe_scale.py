# -*- coding: utf-8 -*-
"""探测量纲：新版 SOE 的 PronFluency / PronCompletion 到底是 0~1 还是百分制。

原理：同样的合成音，一段连续、一段刻意断续（大量静音）。
  - 若返回 0~1：连续≈1.0，断续≈0.3~0.6
  - 若返回百分制：连续≈100，断续≈30~60
两种解读数值差 100 倍，一次对照就能定死。
"""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

from soe_new import SoeNew, from_env

ff = imageio_ffmpeg.get_ffmpeg_exe()


def synth(out, pattern):
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    if pattern == "cont":
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2.5"]
    else:  # chop: 5 段 0.3s 声音，中间隔 0.2s 静音
        cmd += ["-filter_complex",
                "sine=frequency=440:duration=0.3[a];"
                "anullsrc=r=16000:cl=mono:d=0.2[s];"
                "[a][s][a][s][a][s][a][s][a]concat=n=9:v=0:a=1[out]",
                "-map", "[out]"]
    cmd += ["-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(out)]
    subprocess.run(cmd, check=True)


def main():
    ev = from_env()

    for name, pattern in (("连续 2.5s", "cont"), ("断续 5×0.3s", "chop")):
        wav = Path(f"_probe_{pattern}.wav")
        synth(wav, pattern)
        r = ev.evaluate(wav.read_bytes(), "hello world", 1)
        wav.unlink(missing_ok=True)
        if not r.get("ok"):
            print(f"{name:14s} 调用失败：{r.get('error')}")
            continue
        print(f"{name:14s} accuracy={r['accuracy']:.2f}  "
              f"fluency={r['fluency']}  completion={r['completion']}")

    print("\n判读：")
    print("  若 fluency 在 0~1 之间 → 新版与旧版一致，必须 ×100")
    print("  若 fluency 在 0~100 之间 → 新版已百分制，不能 ×100")


if __name__ == "__main__":
    sys.exit(main())
