#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成人工打分表（★ 盲评用，不含任何 AI 分数）。

两位老师使用不同的随机顺序，避免顺序偏差与互相影响。

用法：
    python make_rating_sheet.py --teacher A
    python make_rating_sheet.py --teacher B
输出：
    rating_A.csv / rating_B.csv
"""

import argparse
import csv
import random
from pathlib import Path

# 打分说明会写进 CSV 顶部注释行（老师打开就能看到）
GUIDE = [
    "# 打分说明（打分前请读完）",
    "# 1) 必须盲评：打分时不要看 AI 分数，也不要与另一位老师讨论",
    "# 2) 用耳机听，每条最多听 3 遍",
    "# 3) 每连续打 20 条休息一次，疲劳会让评分漂移",
    "# 4) total_score 填 0-100 整数；star 填 1/2/3；weak_phonemes 填智聆音素（th/ae/sh/ng...），无错误填『无』",
    "# 5) 注意：æ 要写成 ae，不要用国际音标",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default="samples.csv")
    ap.add_argument("--teacher", required=True, help="A 或 B")
    ap.add_argument("--seed", type=int, default=0, help="随机种子（不同老师用不同值）")
    ap.add_argument("--exclude-bad", action="store_true",
                    help="排除 bad 组样本（坏样本单独判定，不参与打分）")
    args = ap.parse_args()

    t = args.teacher.upper()
    seed = args.seed if args.seed else (1 if t == "A" else 2)

    with open(args.samples, encoding="utf-8-sig") as f:
        samples = list(csv.DictReader(f))

    if args.exclude_bad:
        samples = [s for s in samples if (s.get("group") or "").lower() != "bad"]

    random.seed(seed)
    random.shuffle(samples)

    out = Path(f"rating_{t}.csv")
    fields = ["order", "sample_id", "audio_file", "ref_text", "group", "level",
              "total_score", "star", "weak_phonemes", "note"]

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        for line in GUIDE:
            f.write(line + "\n")
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, s in enumerate(samples, 1):
            w.writerow({
                "order": i,
                "sample_id": s["sample_id"],
                "audio_file": s["audio_file"],
                "ref_text": s["ref_text"],
                "group": s.get("group", ""),
                "level": s.get("level", ""),
                "total_score": "",
                "star": "",
                "weak_phonemes": "",
                "note": s.get("note", ""),
            })

    print(f"已生成 {out}")
    print(f"  样本数：{len(samples)}    随机种子：{seed}")
    print(f"  请发给老师{t}，填 total_score / star / weak_phonemes 三列")
    print("  ★ 打分过程中不要打开 results.csv")


if __name__ == "__main__":
    main()
