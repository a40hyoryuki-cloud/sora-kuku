#!/usr/bin/env python3
"""ずんだもん音声の「読み」を一括チェックして、まちがいを直して作り直す

使い方（VOICEVOX ENGINE を 127.0.0.1:50021 で起動しておく）:
  python3 zunda_voice_check.py <出力フォルダ>

やること:
  1. zunda_voice.py の全 247 件について、VOICEVOX が実際に読む カナ を取り出す
  2. 期待する読み（ひらがな→カタカナ）と くらべる
  3. ちがうものは「カタカナで入力」→「アクセント付きカナで直接指定」の順に試し、
     読みが一致したもので 作り直す（<出力>/fixed/<id>.wav）
  4. 結果を <出力>/report.txt に書く（数・九九以外の ことばは 確認用に一覧だけ）
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zunda_voice as Z  # noqa: E402

HOST = "http://127.0.0.1:50021"
SP = Z.SPEAKER


def req(path, body=None):
    r = urllib.request.Request(HOST + path, data=json.dumps(body).encode() if body is not None else b"",
                               headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(r, timeout=60) as f:
        return f.read()


def kata(s):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def clean(s):
    return "".join(c for c in s if c not in " 、。！？!?,")


def norm(s):
    # 長音の ゆれ（ジュー／ジュウ）を そろえる
    out = []
    for c in s:
        if c == "ー" and out:
            p = out[-1]
            out.append("ウ" if p in "ュョウクスツヌフムユルグズヅブプジュジョ" or p[-1:] in "ュョ" else "ー")
        else:
            out.append(c)
    return "".join(out)


def reading(q):
    return "".join(m["text"] for ap in q["accent_phrases"] for m in ap["moras"])


def query(text):
    return json.loads(req(f"/audio_query?speaker={SP}&text={urllib.parse.quote(text)}"))


def kana_query(text_kata, base_q):
    # アクセント付きカナ（AquesTalk 風）で 直接指定。アクセントは 元の位置か 1
    acc = 1
    try:
        acc = base_q["accent_phrases"][0]["accent"]
    except Exception:  # noqa: BLE001
        pass
    acc = max(1, min(acc, len(text_kata)))
    # 拗音（ャュョ）は 前の文字と 1モーラ
    moras, i = [], 0
    while i < len(text_kata):
        if i + 1 < len(text_kata) and text_kata[i + 1] in "ャュョァィゥェォ":
            moras.append(text_kata[i:i + 2]); i += 2
        else:
            moras.append(text_kata[i]); i += 1
    acc = min(acc, len(moras))
    kana = "".join(moras[:acc]) + "'" + "".join(moras[acc:])
    aps = json.loads(req(f"/accent_phrases?speaker={SP}&is_kana=true&text={urllib.parse.quote(kana)}"))
    q = dict(base_q)
    q["accent_phrases"] = aps
    return q


def synth(q, fn):
    q["speedScale"] = 1.05
    q["prePhonemeLength"] = 0.05
    q["postPhonemeLength"] = 0.08
    open(fn, "wb").write(req(f"/synthesis?speaker={SP}", q))


def main():
    out = sys.argv[1]
    os.makedirs(os.path.join(out, "fixed"), exist_ok=True)
    rep, fixed, failed, others = [], [], [], []
    for key, text in Z.items():
        want = norm(kata(clean(text)))
        q = query(text)
        got = norm(reading(q))
        strict = key[0] in "nca" and key[1:2].isdigit() or key.startswith(("kozu", "sara"))
        if got == want:
            continue
        if not strict:
            others.append(f"{key}「{text}」→ {got}")
            continue
        # 1) カタカナで 入れてみる
        q2 = query(kata(clean(text)))
        if norm(reading(q2)) == want:
            synth(q2, os.path.join(out, "fixed", key + ".wav")); fixed.append(f"{key}「{text}」{got} → {want}（カタカナ）")
            continue
        # 2) アクセント付きカナで 直接
        try:
            q3 = kana_query(kata(clean(text)), q)
            if norm(reading(q3)) == want:
                synth(q3, os.path.join(out, "fixed", key + ".wav")); fixed.append(f"{key}「{text}」{got} → {want}（直接指定）")
                continue
        except Exception as e:  # noqa: BLE001
            rep.append(f"  ! {key}: {e}")
        failed.append(f"{key}「{text}」→ {got}")
    rep = [f"直したもの {len(fixed)} 件"] + ["  " + x for x in fixed] + \
          [f"直せなかったもの {len(failed)} 件"] + ["  " + x for x in failed] + \
          [f"ことば（確認用・読みのゆれ）{len(others)} 件"] + ["  " + x for x in others] + rep
    open(os.path.join(out, "report.txt"), "w").write("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
