# -*- coding: utf-8 -*-
"""腾讯云智聆口语评测（新版）调用封装。

★ 为什么要单独写这一层
「口语评测（基础版）」(产品 884) 与「口语评测（新版）」(产品 1774) 是两套完全不同的东西：
  基础版：HTTPS REST，SDK = tencentcloud-sdk-python-soe v20180724，语言用 ServerType
  新版  ：WebSocket，SDK = tencentcloud-speech-sdk-python（仅 GitHub，无 PyPI 包）
         语言用 server_engine_type(16k_en/16k_zh)，音频格式 voice_format(1=wav)
新版官方 SDK 不在 PyPI，已把需要的源码拉到 _soesdk/ 目录直接引用。

★ 与基础版的字段差异（评分模型不受影响，仍取这四个维度）
  SuggestedScore / PronAccuracy / PronFluency / PronCompletion —— 新版同样返回

用法：
    from soe_new import SoeNew
    ev = SoeNew(appid, secret_id, secret_key)
    r = ev.evaluate(wav_bytes_or_path, ref_text="cat", eval_mode=0, score_coeff=1.0)
    print(r["suggested"], r["accuracy"], r["fluency"], r["completion"])
"""

import json
import os
import re
import sys
import time
import io
import contextlib
import urllib.parse  # noqa: F401  SDK 里用了 urllib.parse.quote，这里先确保子模块被加载
from pathlib import Path

_SDK_DIR = Path(__file__).with_name("_soesdk")
if str(_SDK_DIR) not in sys.path:
    sys.path.insert(0, str(_SDK_DIR))

try:
    from common import credential
    from soe import speaking_assessment as _sa
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "缺少新版 SDK 源码或依赖。请确认：\n"
        "  1) spike/_soesdk/ 下有 common/ 与 soe/ 目录\n"
        "  2) pip install websocket-client\n"
        f"原始错误：{e}"
    )

# 音色/语言引擎：英文固定 16k_en
ENGINE_EN = "16k_en"
# voice_format: 0=pcm 1=wav 2=mp3 4=speex  ← 注意与基础版 VoiceFileType(2=wav) 不同
VOICE_FORMAT_WAV = 1

# 基础版 EvalMode 与新版的映射一致：0单词 1句子 2段落
EVAL_MODE = {"word": 0, "sentence": 1, "paragraph": 2}


class _Collector(_sa.SpeakingAssessmentListener):
    """收集回调：最终分数在「最后一条带 result 的消息」里。

    官方 SDK 的坑：final=1 的那条消息**不含 result**（只有 final 字段），
    真正的评分数据在它前一条。所以这里保存最后一次 intermediate result。
    """

    def __init__(self):
        self.started = False
        self.last_result = None      # dict：最后一条带 result 的 intermediate 消息
        self.final_result = None     # dict：final=1 那条（有些场景 result 在这里）
        self.all_msgs = []           # 诊断用：服务端下发的所有原始消息
        self.error = None            # (code, message)
        self.completed = False

    def on_recognition_start(self, response):
        self.started = True

    def on_intermediate_result(self, response):
        self.all_msgs.append(("intermediate", response))
        if response.get("result"):
            self.last_result = response

    def on_recognition_complete(self, response):
        self.all_msgs.append(("final", response))
        # 官方 SDK 注释说 final 消息不含 result，但实测部分场景会带，保险起见留下
        if response.get("result"):
            self.final_result = response
        self.completed = True

    def on_fail(self, response):
        self.all_msgs.append(("fail", response))
        self.error = (response.get("code"), response.get("message"))


def _balanced_slice(s, start):
    """从 s[start] == '[' 或 '{' 开始，返回到配对括号结束的片段。"""
    open_ch = s[start]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    for i in range(start, len(s)):
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return s[start:]


def _num(s, key, default=None):
    m = re.search(r"\b" + key + r":\s*(-?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else default


def parse_result(result):
    """解析新版返回的 result 字段。

    实测两种形态都可能：
      A) JSON 字符串            → 直接 json.loads
      B) Go 结构体字符串 %+v    → 正则提取
        例：{SuggestedScore:88.5 PronAccuracy:91.2 ... Words:[{...}] ...}
    """
    if result is None:
        return {}
    if isinstance(result, dict):
        return result

    text = result if isinstance(result, str) else str(result)
    text = text.strip()

    # A) JSON
    if text.startswith("{"):
        try:
            return json.loads(text)
        except Exception:
            pass

    # B) Go 结构体
    out = {
        "SuggestedScore": _num(text, "SuggestedScore"),
        "PronAccuracy": _num(text, "PronAccuracy"),
        "PronFluency": _num(text, "PronFluency"),
        "PronCompletion": _num(text, "PronCompletion"),
    }
    # Words 数组
    m = re.search(r"\bWords:\s*\[", text)
    words = []
    if m:
        arr = _balanced_slice(text, m.end() - 1)
        i, n = 0, len(arr)
        while i < n:
            if arr[i] == "{":
                seg = _balanced_slice(arr, i)
                words.append({
                    "Word": (re.search(r"\bWord:\s*(\S*)", seg).group(1)
                             if re.search(r"\bWord:\s*(\S*)", seg) else ""),
                    "PronAccuracy": _num(seg, "PronAccuracy"),
                    "PronFluency": _num(seg, "PronFluency"),
                    "MatchTag": int(_num(seg, "Tag", 0) or 0),
                })
                i += len(seg)
            else:
                i += 1
    out["Words"] = words
    out["_raw"] = text
    return out


class SoeNew:
    """新版口语评测客户端（每次评测建立一条 WebSocket 连接）。"""

    def __init__(self, appid, secret_id, secret_key, engine=ENGINE_EN, timeout=30):
        if not appid:
            raise ValueError("缺少 AppID（腾讯云控制台 → 账号信息 → AppID）")
        self.appid = str(appid)
        self.cred = credential.Credential(secret_id, secret_key)
        self.engine = engine
        self.timeout = timeout

    def evaluate(self, audio, ref_text, eval_mode=0, score_coeff=1.0):
        """评测一段音频。

        :param audio: bytes 或 wav 文件路径
        :param ref_text: 参考文本（英文）
        :param eval_mode: 0单词 1句子 2段落
        :param score_coeff: 苛刻指数 1.0~4.0
        :return: dict（含 ok / suggested / accuracy / fluency / completion / words / raw / error）
        """
        if isinstance(audio, (str, Path)):
            audio = Path(audio).read_bytes()
        if not audio:
            return self._err("音频为空")

        listener = _Collector()
        # ★ SDK 的 start() 里会 print 两次带 signature 的完整 URL，
        #   这里临时屏蔽 stdout，避免密钥签名串泄漏到日志文件里
        with contextlib.redirect_stdout(io.StringIO()):
            rec = _sa.SpeakingAssessment(self.appid, self.cred, self.engine, listener)
        rec.set_text_mode(0)
        rec.set_ref_text(ref_text)
        rec.set_eval_mode(int(eval_mode))
        # ★ SDK 没有 set_score_coeff()，score_coeff 是普通实例属性
        rec.score_coeff = float(score_coeff)
        rec.set_keyword("")
        rec.set_sentence_info_enabled(0)
        rec.set_voice_format(VOICE_FORMAT_WAV)
        # ★ 录音模式：一次性发送完整音频（上限约 300s），本项目是离线文件评测必须开
        rec.set_rec_mode(1)

        try:
            # ★ SDK 的 start() 里 print 了两次带 signature 的完整 URL，屏蔽掉防止泄漏
            with contextlib.redirect_stdout(io.StringIO()):
                rec.start()
        except Exception as e:
            return self._err(f"建立连接失败：{type(e).__name__}: {e}")

        # 等握手
        deadline = time.time() + self.timeout
        while rec.status == _sa.STARTED and time.time() < deadline:
            time.sleep(0.05)
        if rec.status != _sa.OPENED:
            return self._err(listener.error[1] if listener.error else "握手超时或被拒绝")

        # 发送音频 + 结束标记
        try:
            rec.write(audio)
            rec.ws.sock.send(json.dumps({"type": "end"}))
        except Exception as e:
            return self._err(f"发送音频失败：{type(e).__name__}: {e}")

        # 等结果
        deadline = time.time() + self.timeout
        while (not listener.completed) and listener.error is None and time.time() < deadline:
            time.sleep(0.05)

        try:
            rec.ws.close()
        except Exception:
            pass

        if listener.error:
            return self._err(listener.error[1], code=listener.error[0])

        # 取分：优先 intermediate（多数场景在这里），其次 final
        src = listener.last_result or listener.final_result
        parsed = parse_result(src.get("result") if src else None)
        if not parsed:
            out = self._err("未收到评测结果（result 为空）")
            out["_trace"] = [
                {"phase": ph, "raw": json.dumps(m, ensure_ascii=False)[:600]}
                for ph, m in listener.all_msgs[-5:]
            ]
            out["_hint"] = (
                "若[:600]里 result 为 null 且音频是合成正弦波，属正常——服务端判定无人声。"
                "请换真人录音重试。"
            )
            return out

        return {
            "ok": True,
            "suggested": parsed.get("SuggestedScore"),
            "accuracy": parsed.get("PronAccuracy"),
            "fluency": parsed.get("PronFluency"),
            "completion": parsed.get("PronCompletion"),
            "words": parsed.get("Words") or [],
            "full": parsed,
            "raw": parsed.get("_raw") or json.dumps(parsed, ensure_ascii=False),
        }

    @staticmethod
    def _err(msg, code=None):
        return {"ok": False, "error": msg, "code": code}


def load_env():
    """把同目录 .env 里的 TENCENTCLOUD_* 读进环境变量（不覆盖已有系统变量）。"""
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("\"'")
            if k.startswith("TENCENTCLOUD_") and v:
                os.environ.setdefault(k, v)


def from_env():
    """从环境变量 / .env 读取 appid + 密钥，返回 SoeNew 实例。"""
    load_env()

    appid = os.environ.get("TENCENTCLOUD_APPID", "").strip()
    sid = os.environ.get("TENCENTCLOUD_SECRET_ID", "").strip()
    skey = os.environ.get("TENCENTCLOUD_SECRET_KEY", "").strip()
    missing = [n for n, v in (("TENCENTCLOUD_APPID", appid),
                              ("TENCENTCLOUD_SECRET_ID", sid),
                              ("TENCENTCLOUD_SECRET_KEY", skey)) if not v]
    if missing:
        raise SystemExit(
            "缺少凭据：" + "、".join(missing) + "\n"
            "  在 spike/.env 里补上，或设环境变量。\n"
            "  AppID 在腾讯云控制台 → 账号信息（右上角头像）里能看到，"
            "它和 SecretId 是两回事。"
        )
    return SoeNew(appid, sid, skey)


if __name__ == "__main__":
    import argparse
    import subprocess

    import imageio_ffmpeg

    ap = argparse.ArgumentParser(description="新版 SOE 自检：验证 AppID/密钥/服务开通")
    ap.add_argument("--coeff", type=float, default=1.0)
    ap.add_argument("--ref", default="cat")
    args = ap.parse_args()

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = Path("_selfcheck_new.wav")
    subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(tmp)],
        check=True,
    )
    print("已生成 2 秒合成音频（正弦波，非真人语音，仅验证链路）")
    try:
        ev = from_env()
        print(f"AppID={ev.appid}  引擎={ev.engine}  ref_text={args.ref!r}  "
              f"eval_mode=0(单词)  score_coeff={args.coeff}")
        r = ev.evaluate(tmp.read_bytes(), args.ref, 0, args.coeff)
        print("\n结果：")
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1200])
        if r.get("ok"):
            print("\n✔ 新版调用成功 —— 可以开始录音了")
        else:
            print(f"\n✘ 调用失败：{r.get('error')}")
            print("  常见原因：4003=AppID 服务未开通（去 console.cloud.tencent.com/soenew 开通）；"
                  "4002=鉴权失败；4004=资源包耗尽；4005=欠费")
    finally:
        tmp.unlink(missing_ok=True)
