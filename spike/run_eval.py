#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量调用腾讯云智聆口语评测（SOE 新版本，产品 1774），把音频打成结构化分数。

★ 为什么强调「新版」
「口语评测（基础版）」(产品 884, HTTPS REST) 与「口语评测（新版）」(产品 1774, WebSocket)
是两套完全独立的产品：两个控制台、两种 SDK、资源包不通用。
本项目 2026-09-17 实测确认走新版，下层 WebSocket 封装在 soe_new.py，
本文件只负责批量编排与结果落盘。

凭据（三件套，缺一不可）：
    TENCENTCLOUD_APPID      腾讯云账号 APPID（控制台 → 右上角头像 → 账号信息）
    TENCENTCLOUD_SECRET_ID
    TENCENTCLOUD_SECRET_KEY
推荐在 spike 目录建 .env 一次配好（已被 .gitignore 忽略）。

用法：
    python run_eval.py --limit 1      # ★ 先跑 1 条验证接口通
    python run_eval.py                # 全量跑
    python run_eval.py --dry-run      # 只打印参数不实际请求（调试/省钱）

输出：
    results.csv             每条样本 × 每个 ScoreCoeff 一行
    raw/<id>_<coeff>.json   引擎原始返回，保留用于后续回标
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    from soe_new import SoeNew, load_env
except ImportError as e:
    print(f"导入新版 SOE 封装失败：{e}")
    print("请确认 soe_new.py 与 _soesdk/ 都在 spike 目录下，且已安装 websocket-client")
    sys.exit(1)

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


RAW_DIR = Path("raw")


def resolve_audio(audio_dir, rel):
    """定位音频文件，兼容三种写法，避免出现 wav16k/wav16k/xxx.wav 这种重复拼接。

    samples.csv 里 audio_file 可能写成：
      A01.wav            → 配合 --audio-dir 使用
      wav16k/A01.wav     → 自带目录，此时 --audio-dir 不再叠加
      raw_audio/A01.m4a  → 未转码的原始录音
    依次尝试上述三种解释，取第一个真实存在的。
    """
    rel = Path(rel)
    for cand in (rel, Path(audio_dir) / rel, Path(audio_dir) / rel.name):
        if cand.exists():
            return cand
    # 都不存在时返回最可能的那一个，让报错信息指到正确位置
    return Path(audio_dir) / rel.name


def norm_percent(v):
    """把 0~1 的浮点转成百分制。

    ★ 关键坑（新版实测确认，2026-09-17）：
      PronFluency / PronCompletion 返回 0~1 浮点，不是百分制。
      实测 ref_text="hello world" 的合成音返回 fluency=1 / completion=0.5 ——
      completion 出现 0.5 这种中间值直接排除百分制可能，必须 ×100。
      忘记 ×100 会让流利度权重被吃掉两个数量级。

    返回 -1 表示「该模式下此字段无意义」（例如单词模式没有流利度）。
    """
    if v is None:
        return -1.0
    v = float(v)
    if v < 0:
        return -1.0
    return round(v * 100.0, 2)


def build_engine():
    """构建新版评测客户端（含 .env 读取与缺参提示）。"""
    load_env()
    missing = [n for n in ("TENCENTCLOUD_APPID",
                           "TENCENTCLOUD_SECRET_ID",
                           "TENCENTCLOUD_SECRET_KEY")
               if not os.environ.get(n, "").strip()]
    if missing:
        print("错误：缺少凭据 → " + "、".join(missing))
        print("  在 spike/.env 里补上（推荐），或设同名环境变量。")
        print("  APPID 在腾讯云控制台 → 右上角头像 → 账号信息，它和 SecretId 是两回事。")
        sys.exit(1)
    return SoeNew(os.environ["TENCENTCLOUD_APPID"].strip(),
                  os.environ["TENCENTCLOUD_SECRET_ID"].strip(),
                  os.environ["TENCENTCLOUD_SECRET_KEY"].strip())


def evaluate(engine, audio_path, ref_text, eval_mode, score_coeff):
    """评测单个音频文件，返回 SoeNew.evaluate 的 dict。"""
    r = engine.evaluate(Path(audio_path).read_bytes(), ref_text, eval_mode, score_coeff)
    if not r.get("ok"):
        raise RuntimeError(r.get("error", "未知错误"))
    return r


def parse_response(resp):
    """把新版返回整理成结构化字段（字段名与旧版保持一致，analyze.py 无需改动）。"""
    words = resp.get("words") or []
    phones = []
    word_scores = []
    max_end = 0

    for w in words:
        wa = w.get("PronAccuracy")
        if wa is not None and float(wa) >= 0:
            word_scores.append(round(float(wa), 2))
        for p in w.get("PhoneInfos") or []:
            pa = p.get("PronAccuracy")
            ph = p.get("Phone")
            if ph is None or pa is None:
                continue
            pa = float(pa)
            if pa >= 0:
                phones.append((ph, pa))
            end = p.get("MemEndTime") or 0
            max_end = max(max_end, int(end))

    # 薄弱音素：低于 60 分的，按分数升序去重，取前 5
    weak = []
    seen = set()
    for ph, pa in sorted(phones, key=lambda x: x[1]):
        if pa < 60 and ph not in seen:
            weak.append(ph)
            seen.add(ph)
        if len(weak) >= 5:
            break

    return {
        "accuracy": round(float(resp.get("accuracy", -1)), 2),
        "fluency": norm_percent(resp.get("fluency")),
        "completion": norm_percent(resp.get("completion")),
        "suggested": round(float(resp.get("suggested", -1)), 2),
        "duration_ms": max_end,
        "word_count": len(words),
        "word_scores": word_scores,
        "weak_phonemes": weak,
    }


def synth_selfcheck_wav(path):
    """生成一段用于链路自检的音频（非真人语音，分数无意义）。"""
    if imageio_ffmpeg is None:
        print("缺少 imageio-ffmpeg，无法生成测试音频。请先安装：")
        print('  "<python>" -m pip install imageio-ffmpeg')
        return False
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(path)],
        check=True,
    )
    return True


def self_check():
    """用合成音频打一次真实调用，验证 APPID/密钥/服务开通状态（不需要录音文件）。"""
    tmp = Path("_selfcheck.wav")
    if not synth_selfcheck_wav(tmp):
        return 1
    print("已生成 2 秒合成音频（非真人语音，仅用于验证链路）")
    try:
        ev = build_engine()
        print(f"AppID={ev.appid}  引擎={ev.engine}")
        r = ev.evaluate(tmp.read_bytes(), "cat", 0, 1.0)
        if r.get("ok"):
            print("\n✔ 新版调用成功 —— 凭据有效，口语评测（新版）已开通")
            print(f"  建议分={r['suggested']}  准确度={r['accuracy']}  "
                  f"流利度={r['fluency']}  完整度={r['completion']}")
            print("  （正弦波不是人声，分数偏低属正常）")
            print("\n下一步：可以开始录音了。")
            return 0
        print(f"\n✘ 调用失败：{r.get('error')}")
        hint = {
            4002: "鉴权失败：检查 SecretId/SecretKey 是否成对、有无多余空格",
            4003: "AppID 未开通服务：去 console.cloud.tencent.com/soenew 开通新版口语评测",
            4004: "资源包耗尽：去控制台查看剩余次数",
            4005: "账号欠费：结算中心处理",
        }.get(r.get("code"))
        if hint:
            print(f"  错误码 {r.get('code')} → {hint}")
        return 1
    finally:
        tmp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="自检：用合成音频验证凭据与服务开通（不需要录音文件）")
    ap.add_argument("--samples", default="samples.csv", help="样本清单 CSV")
    ap.add_argument("--audio-dir", default="wav16k",
                    help="音频文件所在根目录（默认 wav16k，即 transcode.py 的输出目录）")
    ap.add_argument("--out", default="results.csv", help="输出 CSV")
    ap.add_argument("--coeff", default="1.0,1.5,2.5",
                    help="要试的 ScoreCoeff，逗号分隔（苛刻指数，越大越严格）")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（先用 1 验证接口）")
    ap.add_argument("--sleep", type=float, default=0.3, help="每次调用间隔秒数")
    ap.add_argument("--dry-run", action="store_true", help="只打印参数，不实际请求")
    args = ap.parse_args()

    if args.check:
        sys.exit(self_check())

    samples_path = Path(args.samples)
    if not samples_path.exists():
        print(f"错误：找不到样本清单 {samples_path}")
        sys.exit(1)

    with open(samples_path, encoding="utf-8-sig") as f:
        # 允许 CSV 顶部有 # 开头的说明行
        lines = [l for l in f if not l.lstrip().startswith("#")]
    samples = list(csv.DictReader(lines))

    if args.limit:
        samples = samples[: args.limit]

    coeffs = [float(x) for x in args.coeff.split(",") if x.strip()]
    RAW_DIR.mkdir(exist_ok=True)

    engine = None
    if not args.dry_run:
        engine = build_engine()

    rows = []
    total = len(samples) * len(coeffs)
    done = 0

    print(f"共 {len(samples)} 条样本 × {len(coeffs)} 组 ScoreCoeff = {total} 次调用")
    if args.dry_run:
        print("（dry-run 模式，不会真正请求）")
    print("-" * 60)

    for s in samples:
        sid = s["sample_id"]
        audio = resolve_audio(args.audio_dir, s["audio_file"])
        ref = s["ref_text"]
        eval_mode = int(s.get("eval_mode", 0) or 0)

        if not audio.exists():
            print(f"  ✘ {sid} 音频不存在：{audio}")
            for c in coeffs:
                rows.append(_row(s, sid, c, ref, eval_mode, error="音频文件不存在"))
            continue

        for c in coeffs:
            done += 1
            tag = f"[{done}/{total}] {sid} coeff={c}"
            if args.dry_run:
                print(f"  · {tag} → RefText={ref!r} mode={eval_mode} file={audio}")
                continue

            raw_file = RAW_DIR / f"{sid}_{c}.json"
            try:
                resp = evaluate(engine, audio, ref, eval_mode, c)
                with open(raw_file, "w", encoding="utf-8") as f:
                    json.dump(resp.get("full") or resp.get("raw"),
                              f, ensure_ascii=False, indent=2, default=str)
                parsed = parse_response(resp)
                rows.append(_row(s, sid, c, ref, eval_mode, parsed=parsed,
                                 raw_file=str(raw_file)))
                print(f"  ✔ {tag} → 准{parsed['accuracy']} 流{parsed['fluency']} "
                      f"完{parsed['completion']} 建议{parsed['suggested']}")
            except Exception as e:  # noqa: BLE001
                rows.append(_row(s, sid, c, ref, eval_mode,
                                 error=f"{type(e).__name__}: {e}"))
                print(f"  ✘ {tag} → {type(e).__name__}: {e}")

            time.sleep(args.sleep)

    if args.dry_run:
        print("\n（dry-run 完成，未写出结果文件）")
        return

    fields = ["sample_id", "score_coeff", "group", "level", "ref_text", "eval_mode",
              "accuracy", "fluency", "completion", "suggested", "duration_ms",
              "word_count", "weak_phonemes", "error", "raw_file"]
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    ok_n = sum(1 for r in rows if not r["error"])
    print("-" * 60)
    print(f"完成：成功 {ok_n} / 失败 {len(rows) - ok_n}")
    print(f"结果：{args.out}")
    print(f"原始返回：{RAW_DIR}/")
    print("\n下一步：让两位老师背对背打分，再跑 analyze.py")


FIELDS = ["sample_id", "score_coeff", "group", "level", "ref_text", "eval_mode",
          "accuracy", "fluency", "completion", "suggested", "duration_ms",
          "word_count", "weak_phonemes", "error", "raw_file"]


def _row(sample, sid, coeff, ref, eval_mode, parsed=None, error="", raw_file=""):
    """构造一行结果 CSV 记录（成功/失败走同一出口，避免字段缺失）。"""
    parsed = parsed or {}
    return {
        "sample_id": sid,
        "score_coeff": coeff,
        "group": sample.get("group", ""),
        "level": sample.get("level", ""),
        "ref_text": ref,
        "eval_mode": eval_mode,
        "accuracy": parsed.get("accuracy", ""),
        "fluency": parsed.get("fluency", ""),
        "completion": parsed.get("completion", ""),
        "suggested": parsed.get("suggested", ""),
        "duration_ms": parsed.get("duration_ms", ""),
        "word_count": parsed.get("word_count", ""),
        "weak_phonemes": "|".join(parsed.get("weak_phonemes", [])),
        "error": error,
        "raw_file": raw_file,
    }


if __name__ == "__main__":
    main()
