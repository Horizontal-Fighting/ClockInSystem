#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 评分 vs 人工评分 对齐分析（纯标准库，无需 numpy/pandas）。

用法：
    python analyze.py
    python analyze.py --star3 85 --star2 70
    python analyze.py --rating-a rating_A.csv --rating-b rating_B.csv

输出：
    控制台 + report.txt
"""

import argparse
import csv
import math
import sys
from collections import defaultdict

SEP = "=" * 66
SUB = "-" * 66
_lines = []


def out(s=""):
    print(s)
    _lines.append(s)


# ------------------------------------------------------------------ 基础统计 ---
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def ranks(xs):
    """平均秩，用于 Spearman"""
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[idx[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))


def mae(xs, ys):
    return mean([abs(x - y) for x, y in zip(xs, ys)])


def bias(xs, ys):
    """系统偏差：mean(x - y)，正数表示 x 整体偏高"""
    return mean([x - y for x, y in zip(xs, ys)])


def sd(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def bland_altman(xs, ys):
    d = [x - y for x, y in zip(xs, ys)]
    m, s = mean(d), sd(d)
    return m, m - 1.96 * s, m + 1.96 * s


def fmt(v, nd=2):
    return "n/a" if v != v else f"{v:.{nd}f}"  # v != v 判断 NaN


# ---------------------------------------------------------------- 线性回归 ---
def solve(A, b):
    """高斯消元解线性方程组（部分主元）"""
    n = len(A)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            return None
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col] / pv
            for c in range(col, n + 1):
                M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def fit_linear(X, y):
    """最小二乘：X 为 n×k（每行已含常数项 1），返回系数列表"""
    k = len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(len(X))) for b in range(k)] for a in range(k)]
    bb = [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(k)]
    return solve(A, bb)


def r_squared(X, y, coef):
    pred = [sum(c * x for c, x in zip(coef, row)) for row in X]
    my = mean(y)
    ss_res = sum((p - yy) ** 2 for p, yy in zip(pred, y))
    ss_tot = sum((yy - my) ** 2 for yy in y)
    return 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def grid_search_weights(rows, human, use_dims):
    """网格搜索权重（和为 1，步长 0.05），返回 (w, offset, mae)"""
    best = None
    step = 0.05
    steps = int(round(1 / step))
    if use_dims == 1:
        for i in range(steps + 1):
            w = (round(i * step, 2), 0.0, 0.0)
            sc = [r[0] * w[0] for r in rows]
            off = mean([h - s for h, s in zip(human, sc)])
            e = mae([s + off for s in sc], human)
            if best is None or e < best[2]:
                best = (w, off, e)
    else:
        for i in range(steps + 1):
            for j in range(steps + 1 - i):
                k = steps - i - j
                w = (round(i * step, 2), round(j * step, 2), round(k * step, 2))
                sc = [r[0] * w[0] + r[1] * w[1] + r[2] * w[2] for r in rows]
                off = mean([h - s for h, s in zip(human, sc)])
                e = mae([s + off for s in sc], human)
                if best is None or e < best[2]:
                    best = (w, off, e)
    return best


# -------------------------------------------------------------------- 读数 ---
def read_csv(path, skip_comment=True):
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None
    if skip_comment:
        lines = [l for l in lines if not l.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def f(row, key, default=-1.0):
    v = row.get(key, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_phonemes(s):
    if not s:
        return []
    s = s.strip().lower()
    if s in ("无", "none", "无错误", "-"):
        return []
    for ch in "|/,，、 ":
        s = s.replace(ch, " ")
    return [x for x in s.split() if x]


def cal_score(row, group, plan):
    """按拟合出的权重计算校准分（产品里实际使用的综合分）"""
    w, off = plan.get(group, ((1.0, 0.0, 0.0), 0.0))[:2]
    acc = f(row, "accuracy")
    flu = f(row, "fluency")
    com = f(row, "completion")
    acc = acc if acc >= 0 else 0.0
    flu = flu if flu >= 0 else 0.0
    com = com if com >= 0 else 0.0
    return w[0] * acc + w[1] * flu + w[2] * com + off


def star_of(score, s3, s2):
    if score >= s3:
        return 3
    if score >= s2:
        return 2
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results.csv")
    ap.add_argument("--rating-a", default="rating_A.csv")
    ap.add_argument("--rating-b", default="rating_B.csv")
    ap.add_argument("--star3", type=float, default=85.0, help="三星阈值")
    ap.add_argument("--star2", type=float, default=70.0, help="二星阈值")
    ap.add_argument("--baseline-ratio", type=float, default=1.3,
                    help="AI-人工 MAE 允许达到 人-人 MAE 的倍数")
    ap.add_argument("--report", default="report.txt")
    args = ap.parse_args()

    results = read_csv(args.results)
    if not results:
        print(f"错误：找不到 {args.results}，请先跑 run_eval.py")
        sys.exit(1)

    ra = read_csv(args.rating_a)
    rb = read_csv(args.rating_b)

    # AI 结果：(sample_id, coeff) -> row
    ai = {}
    for r in results:
        if r.get("error"):
            continue
        ai[(r["sample_id"], float(r["score_coeff"]))] = r

    # 人工分
    human_a, human_b = {}, {}
    star_a, star_b, phon_a, phon_b = {}, {}, {}, {}
    if ra:
        for r in ra:
            ts = (r.get("total_score") or "").strip()
            if not ts:
                continue
            human_a[r["sample_id"]] = float(ts)
            st = (r.get("star") or "").strip()
            if st:
                star_a[r["sample_id"]] = int(float(st))
            phon_a[r["sample_id"]] = parse_phonemes(r.get("weak_phonemes"))
    if rb:
        for r in rb:
            ts = (r.get("total_score") or "").strip()
            if not ts:
                continue
            human_b[r["sample_id"]] = float(ts)
            st = (r.get("star") or "").strip()
            if st:
                star_b[r["sample_id"]] = int(float(st))
            phon_b[r["sample_id"]] = parse_phonemes(r.get("weak_phonemes"))

    if not human_a and not human_b:
        print("错误：未读到任何人工打分。请先让老师填 rating_A.csv / rating_B.csv")
        sys.exit(1)

    common_a_only = set(human_a) - set(human_b)
    if common_a_only and not human_b:
        out("⚠ 只读到一位老师的打分，无法计算人类基线（强烈建议补第二位老师）")

    human_mean = {}
    for sid in set(human_a) | set(human_b):
        vals = [v for v in (human_a.get(sid), human_b.get(sid)) if v is not None]
        human_mean[sid] = sum(vals) / len(vals)

    out(SEP)
    out("  评测精度 Spike 分析报告")
    out(SEP)
    out(f"  AI 结果条数     : {len(ai)}")
    out(f"  教师A 已评      : {len(human_a)}")
    out(f"  教师B 已评      : {len(human_b)}")
    out(f"  有效样本（取交集）: 见下")

    # ---------------------------------------------------------- 1 人类基线 ---
    out()
    out(SEP)
    out("  1. 人类基线（教师A vs 教师B）★ 这是「人能达到的一致性上限」")
    out(SEP)
    both = sorted(set(human_a) & set(human_b))
    base_mae = None
    if len(both) >= 3:
        xa = [human_a[s] for s in both]
        xb = [human_b[s] for s in both]
        r_hh = pearson(xa, xb)
        base_mae = mae(xa, xb)
        out(f"  共同样本         : {len(both)} 条")
        out(f"  Pearson r        : {fmt(r_hh)}")
        out(f"  Spearman ρ       : {fmt(spearman(xa, xb))}")
        out(f"  MAE（人-人）     : {fmt(base_mae)} 分")
        out(f"  Bias             : {fmt(bias(xa, xb))} 分（A 相对 B）")
        out()
        out("  → 解读：两位老师之间本身就存在上述波动，")
        out("    AI 的误差只要不显著大于它，就达到「相当于多一位老师」的水平。")
    else:
        out("  ⚠ 共同样本不足 3 条，或只有一位老师打分，无法计算人类基线。")
        out("    强烈建议补齐第二位老师的打分——没有基线，MAE 这个数字无法判断好坏。")

    # ------------------------------------------------- 2 各 coeff 的 AI 表现 ---
    coeffs = sorted({k[1] for k in ai})
    # 只用非 bad 组、且有人人工分的样本
    def valid_pairs(coeff):
        xs, ys, sids = [], [], []
        for sid, h in human_mean.items():
            row = ai.get((sid, coeff))
            if not row:
                continue
            if (row.get("group") or "").lower() == "bad":
                continue
            xs.append(f(row, "accuracy"))
            ys.append(h)
            sids.append(sid)
        return xs, ys, sids

    out()
    out(SEP)
    out("  2. AI（原始 suggested 分）vs 人工平均分")
    out(SEP)
    best_coeff, best_mae = None, None
    for c in coeffs:
        # suggested 分是引擎给的建议分，直接比
        xs, ys, _ = [], [], []
        for sid, h in human_mean.items():
            row = ai.get((sid, c))
            if not row:
                continue
            if (row.get("group") or "").lower() == "bad":
                continue
            xs.append(f(row, "suggested"))
            ys.append(h)
        if len(xs) < 3:
            continue
        r = pearson(xs, ys)
        e = mae(xs, ys)
        b, lo, hi = bland_altman(xs, ys)
        out(f"  ScoreCoeff={c}  (n={len(xs)})")
        out(f"    Pearson r     : {fmt(r)}")
        out(f"    Spearman ρ    : {fmt(spearman(xs, ys))}")
        out(f"    MAE           : {fmt(e)} 分")
        out(f"    Bias          : {fmt(b)} 分（正数=AI 整体偏高）")
        out(f"    Bland-Altman  : [{fmt(lo)}, {fmt(hi)}]")
        if best_mae is None or e < best_mae:
            best_coeff, best_mae = c, e
    if best_coeff is not None:
        out()
        out(f"  → 最优 ScoreCoeff = {best_coeff}（MAE {fmt(best_mae)} 分）")

    # -------------------------------------------------------- 3 权重拟合 ---
    out()
    out(SEP)
    out("  3. 权重拟合（用数据算出权重，替代拍脑袋）")
    out(SEP)

    coeff = best_coeff if best_coeff is not None else coeffs[0]
    groups = defaultdict(list)
    for sid, h in human_mean.items():
        row = ai.get((sid, coeff))
        if not row:
            continue
        g = (row.get("group") or "unknown").lower()
        if g == "bad":
            continue
        groups[g].append((row, h))

    weight_plan = {}
    for g in ["word", "sentence", "paragraph"]:
        items = groups.get(g, [])
        if len(items) < 4:
            continue
        rows3, human = [], []
        for row, h in items:
            acc = f(row, "accuracy")
            flu = f(row, "fluency")
            com = f(row, "completion")
            if acc < 0:
                continue
            flu = flu if flu >= 0 else 0.0
            com = com if com >= 0 else 0.0
            rows3.append((acc, flu, com))
            human.append(h)
        if len(rows3) < 4:
            continue

        use_dims = 1 if g == "word" else 3
        out()
        out(f"  【{g}】n={len(rows3)}")
        if use_dims == 1:
            out("    （单词模式：流利度/完整度无意义，只用准确度）")
            X = [[r[0], 1.0] for r in rows3]
        else:
            X = [[r[0], r[1], r[2], 1.0] for r in rows3]
        if len(rows3) < 15:
            out(f"    ⚠ 样本量 {len(rows3)} < 15，回归系数可能过拟合，"
                f"请勿直接写入配置；以「网格最优」为准")
            if len(rows3) <= len(X[0]):
                out("    ⚠⚠ 样本数 ≤ 参数个数，R² 与系数均无统计意义，仅占位")
        coef = fit_linear(X, human)
        if coef:
            r2 = r_squared(X, human, coef)
            pred = [sum(c * x for c, x in zip(coef, row)) for row in X]
            out(f"    回归公式 : 人工分 ≈ " +
                " + ".join(f"{c:.3f}×{n}" for c, n in
                           zip(coef[:-1], ["准确度", "流利度", "完整度"][:len(coef) - 1])) +
                f" + {coef[-1]:.3f}")
            out(f"    R²        : {fmt(r2, 3)}")
            out(f"    拟合后 MAE: {fmt(mae(pred, human))} 分")

        w, off, e = grid_search_weights(rows3, human, use_dims)
        weight_plan[g] = (w, off, e)
        if use_dims == 1:
            out(f"    网格最优 : 分数 = {w[0]:.2f}×准确度 + {off:.2f}   → MAE {fmt(e)}")
        else:
            out(f"    网格最优 : 分数 = {w[0]:.2f}×准确度 + {w[1]:.2f}×流利度 "
                f"+ {w[2]:.2f}×完整度 + {off:.2f}")
            out(f"              → MAE {fmt(e)} 分  ★ 建议写入 sys_config")

    # -------------------------------------------------------- 4 分层表现 ---
    out()
    out(SEP)
    out("  4. 分层表现（用原始 suggested 分，看哪类内容最不准）")
    out(SEP)
    out(f"  {'分组':<12}{'n':>4}{'Pearson':>10}{'MAE':>9}{'Bias':>9}")
    out("  " + SUB)
    for g in ["word", "sentence", "paragraph"]:
        xs, ys = [], []
        for sid, h in human_mean.items():
            row = ai.get((sid, coeff))
            if not row or (row.get("group") or "").lower() != g:
                continue
            xs.append(f(row, "suggested"))
            ys.append(h)
        if len(xs) >= 3:
            out(f"  {g:<12}{len(xs):>4}{fmt(pearson(xs, ys)):>10}"
                f"{fmt(mae(xs, ys)):>9}{fmt(bias(xs, ys)):>9}")
    by_level = defaultdict(lambda: ([], []))
    for sid, h in human_mean.items():
        row = ai.get((sid, coeff))
        if not row or (row.get("group") or "").lower() == "bad":
            continue
        lv = (row.get("level") or "unknown").lower()
        by_level[lv][0].append(f(row, "suggested"))
        by_level[lv][1].append(h)
    for lv in ["high", "mid", "low"]:
        xs, ys = by_level.get(lv, ([], []))
        if len(xs) >= 3:
            out(f"  水平={lv:<8}{len(xs):>4}{fmt(pearson(xs, ys)):>10}"
                f"{fmt(mae(xs, ys)):>9}{fmt(bias(xs, ys)):>9}")

    # ------------------------------------------------------ 5 星级一致率 ---
    out()
    out(SEP)
    out(f"  5. 星级一致率（阈值：三星 ≥{args.star3}，二星 ≥{args.star2}）")
    out(SEP)
    out("  —— 用「校准后」分数计算（第 3 节拟合的权重），这才是产品里的真实表现 ——")
    for name, star_map in (("教师A", star_a), ("教师B", star_b)):
        if not star_map:
            continue
        hit, tot = 0, 0
        hit_raw, tot_raw = 0, 0
        for sid, hs in star_map.items():
            row = ai.get((sid, coeff))
            if not row or (row.get("group") or "").lower() == "bad":
                continue
            g = (row.get("group") or "unknown").lower()
            ai_s = star_of(cal_score(row, g, weight_plan), args.star3, args.star2)
            tot += 1
            if ai_s == hs:
                hit += 1
            tot_raw += 1
            if star_of(f(row, "suggested"), args.star3, args.star2) == hs:
                hit_raw += 1
        if tot:
            out(f"  {name} : 校准后 {hit}/{tot} = {hit / tot * 100:.1f}%"
                f"    （未校准引擎裸分：{hit_raw / tot_raw * 100:.1f}%）")

    # ---------------------------------------------------- 6 音素命中率 ---
    out()
    out(SEP)
    out("  6. 音素纠错命中率（老师标的错误音素 vs AI 最低分音素 Top3）")
    out(SEP)
    for name, phon_map in (("教师A", phon_a), ("教师B", phon_b)):
        if not phon_map:
            continue
        hit, tot, false_alarm, clean = 0, 0, 0, 0
        for sid, phs in phon_map.items():
            row = ai.get((sid, coeff))
            if not row or (row.get("group") or "").lower() == "bad":
                continue
            ai_ph = parse_phonemes(row.get("weak_phonemes"))[:3]
            if not phs:
                # 老师认为没有明显错误
                clean += 1
                if ai_ph:
                    false_alarm += 1
                continue
            tot += 1
            if any(p in ai_ph for p in phs):
                hit += 1
        if tot:
            out(f"  {name} : 命中 {hit}/{tot} = {hit / tot * 100:.1f}%")
        if clean:
            out(f"  {name} : 老师判『无错误』的 {clean} 条中，AI 仍报错 {false_alarm} 条"
                f"（误报率 {false_alarm / clean * 100:.1f}%）")
    out("  → 命中率 ≥60% 才能对外宣称「AI 音素级纠音」；误报率高说明阈值需调严。")

    # ------------------------------------------------------ 7 坏样本 ---
    bad_rows = [(sid, ai[(sid, coeff)]) for sid in human_mean if (sid, coeff) in ai
                and (ai[(sid, coeff)].get("group") or "").lower() == "bad"]
    if bad_rows:
        out()
        out(SEP)
        out("  7. 坏样本（环境/态度问题）识别 —— 用于定「要不要提示重录」的阈值")
        out(SEP)
        out(f"  {'样本':<8}{'准确度':>8}{'完整度':>8}{'时长ms':>9}{'AI分':>8}  备注")
        out("  " + SUB)
        for sid, row in sorted(bad_rows):
            out(f"  {sid:<8}{fmt(f(row,'accuracy'),1):>8}{fmt(f(row,'completion'),1):>8}"
                f"{int(f(row,'duration_ms',0)):>9}{fmt(f(row,'suggested'),1):>8}  见 samples.csv 备注")
        out()
        out("  → 人工对照：这些样本是否该被判为「环境问题需重录」而非「发音差」？")
        out("    若是，找出可区分的阈值（例如 完整度 < 60 或 时长异常）。")

    # ------------------------------------------------------ 8 判定 ---
    out()
    out(SEP)
    out("  8. Go / No-Go 判定")
    out(SEP)
    xs, ys, xs_raw = [], [], []
    for sid, h in human_mean.items():
        row = ai.get((sid, coeff))
        if not row or (row.get("group") or "").lower() == "bad":
            continue
        g = (row.get("group") or "unknown").lower()
        xs.append(cal_score(row, g, weight_plan))
        xs_raw.append(f(row, "suggested"))
        ys.append(h)
    if len(xs) >= 3:
        r_ai = pearson(xs, ys)
        m_ai = mae(xs, ys)
        out("  ★ 以下判定基于「校准后」分数（第 3 节权重），这是产品上线后的真实表现")
        out(f"    【校准后】r={fmt(r_ai)}  MAE={fmt(m_ai)} 分")
        out(f"    【引擎裸分】r={fmt(pearson(xs_raw, ys))}  MAE={fmt(mae(xs_raw, ys))} 分"
            f"  ← 两者差距大说明校准很关键")
        out()
        checks = []
        checks.append(("相关系数 r ≥ 0.75", r_ai >= 0.75, fmt(r_ai)))
        checks.append(("MAE ≤ 8 分", m_ai <= 8, f"{fmt(m_ai)} 分"))
        if base_mae is not None:
            thr = base_mae * args.baseline_ratio
            checks.append((f"AI 误差 ≤ {args.baseline_ratio}× 人类基线({fmt(thr)})",
                           m_ai <= thr, f"{fmt(m_ai)} vs {fmt(thr)}"))
        for name, star_map in (("教师A", star_a), ("教师B", star_b)):
            if not star_map:
                continue
            hit, tot = 0, 0
            for sid, hs in star_map.items():
                row = ai.get((sid, coeff))
                if not row or (row.get("group") or "").lower() == "bad":
                    continue
                g = (row.get("group") or "unknown").lower()
                tot += 1
                if star_of(cal_score(row, g, weight_plan), args.star3, args.star2) == hs:
                    hit += 1
            if tot:
                rate = hit / tot * 100
                checks.append((f"星级一致率 ≥70%（{name}）", rate >= 70, f"{rate:.1f}%"))
        for name, phon_map in (("教师A", phon_a), ("教师B", phon_b)):
            hit, tot = 0, 0
            for sid, phs in (phon_map or {}).items():
                row = ai.get((sid, coeff))
                if not row or not phs or (row.get("group") or "").lower() == "bad":
                    continue
                tot += 1
                if any(p in parse_phonemes(row.get("weak_phonemes"))[:3] for p in phs):
                    hit += 1
            if tot:
                rate = hit / tot * 100
                checks.append((f"音素命中率 ≥60%（{name}）", rate >= 60, f"{rate:.1f}%"))

        for name, passed, val in checks:
            out(f"  [{'✔' if passed else '✘'}] {name:<34} 实测 {val}")

        failed = [n for n, p, _ in checks if not p]
        out()
        if not failed:
            out("  ★ 结论：GO —— 可直接进入 M2 开发，把本次拟合的权重写入 sys_config。")
        elif any("相关系数" in x for x in failed):
            out("  ⚠ 结论：NO-GO（r 过低）—— AI 连排序都不对，建议换供应商（讯飞 ISE）")
            out("    重跑本 Spike 对比；仍不行则改为「AI 只做音素诊断、不给总分」。")
        elif any("MAE" in x or "基线" in x for x in failed):
            out("  ⚠ 结论：有条件 GO（存在偏差）—— 用第 3 节的校准公式修正后复核。")
            out("    若校准后仍不达标：降低 AI 权重，星级/升级改由老师确认。")
        else:
            out("  ⚠ 结论：有条件 GO —— 部分指标未达标（见上），按对应项调整后复核。")

    out()
    out(SEP)
    out("  下一步")
    out(SEP)
    out("  1) 把第 3 节的权重写入 02-技术架构与数据设计.md §2.5 与 sys_config")
    out("  2) 把最优 ScoreCoeff 与星级阈值按级别/学段落库")
    out("  3) 音素命中率决定 PRD F3-8/F3-9（音素可视化）的优先级")
    out("  4) 坏样本阈值补进「环境问题判定」逻辑")
    out("  5) 把本报告与结论写入 ADR 决策记录")
    out(SEP)

    # 注意：这里不能用 `as f`，会遮蔽全局的 f() 取值函数
    with open(args.report, "w", encoding="utf-8") as fp:
        fp.write("\n".join(_lines))
    print(f"\n报告已保存：{args.report}")


if __name__ == "__main__":
    main()
