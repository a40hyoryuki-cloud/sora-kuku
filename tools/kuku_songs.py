#!/usr/bin/env python3
"""九九の歌：段ごとに ちがう 曲調の 楽譜と 時刻表を つくる（メロディは すべて オリジナル）

  python3 kuku_songs.py score <出力フォルダ>   … 歌の段の 楽譜 JSON（VOICEVOX 用）
  python3 kuku_songs.py sing <出力フォルダ>    … VOICEVOX（127.0.0.1:50021）で 歌わせて wav に
                                                （ラップの段は「◯のだん」の 話し声だけ 作る）

伴奏づくりと ミックスは kuku_backing.py（numpy を使う）。
外部ライブラリは 使わない（Mac の作業領域で そのまま 動くように）。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kuku_sing import KUKU, DAN_NAME, morae  # noqa: E402

FPS = 24000 / 256           # VOICEVOX の フレームレート
TEACHER = 6000              # 歌い方の お手本（波音リツ 歌唱）
SINGER = 3003               # ずんだもん（歌）
TALKER = 3                  # ずんだもん（話し声）

# コード（ルート音名 → 半音, 種類）
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
QUAL = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "5": [0, 7], "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11]}


def chord(name):
    r = name[:2] if name[1:2] in ("#", "b") else name[:1]
    return NOTE[r], QUAL[name[len(r):]]


# 段ごとの 曲調
#  beats：1小節の拍数 / line：1行の小節数 / head：「◯のだん」の小節数
#  prog：1小節ごとの コード（くりかえし）/ lo,hi,center：歌う音の高さの はんい（MIDI）
#  cpat,apat：かけ声・こたえ の 音の 動き（和音の 音を いくつ 上下するか）/ base：音の長さの 候補（16分音符いくつ）
STYLES = {
    1: dict(name="ポップ", bpm=112, beats=4, line=1, head=1, kind="pop"),
    2: dict(name="ラップ", bpm=92, beats=4, line=1, head=1, kind="rap",
            prog=["Am", "F", "G", "Em"]),
    3: dict(name="ワルツ", bpm=150, beats=3, line=2, head=2, kind="sing",
            prog=["F", "C7", "C7", "F", "Bb", "F", "C7", "F"],
            lo=60, hi=74, center=69, cpat=[0, 1, 2, 1, 0, 1], apat=[2, 1, 0, -1, 0, 1], fin=0, base=[4, 2, 1]),
    4: dict(name="マーチ", bpm=120, beats=4, line=1, head=1, kind="sing",
            prog=["G", "C", "D", "G"],
            lo=59, hi=74, center=67, cpat=[0, 0, 1, 1, 2, 1], apat=[2, 2, 1, 0, -1, 0], fin=0, base=[2, 1]),
    5: dict(name="ロック", bpm=152, beats=4, line=2, head=2, kind="sing",
            prog=["Em", "C", "D", "Em"],
            lo=59, hi=72, center=64, cpat=[0, 0, 0, 1, 0, -1], apat=[1, 1, 0, 0, -1, -1], fin=0, base=[4, 2, 1]),
    6: dict(name="サンバ", bpm=104, beats=4, line=1, head=1, kind="sing",
            prog=["D", "Em", "A7", "D"],
            lo=62, hi=76, center=69, cpat=[0, 1, 0, 1, 2, 1], apat=[2, 1, 2, 1, 0, -1], fin=0, base=[2, 1]),
    7: dict(name="ゲーム", bpm=140, beats=4, line=2, head=2, kind="sing",
            prog=["A", "F#m", "D", "E"],
            lo=61, hi=76, center=69, cpat=[0, 1, 2, 3, 2, 1], apat=[3, 2, 1, 0, 1, 0], fin=0, base=[4, 2, 1]),
    8: dict(name="こもりうた", bpm=76, beats=4, line=1, head=1, kind="sing",
            prog=["Bb", "Gm", "Eb", "F"],
            lo=58, hi=72, center=65, cpat=[0, 1, 1, 0, -1, 0], apat=[1, 0, -1, 0, -1, 0], fin=0, base=[2, 1]),
    9: dict(name="ダンス", bpm=126, beats=4, line=1, head=1, kind="sing",
            prog=["Em", "C", "G", "D"],
            lo=62, hi=76, center=67, cpat=[0, 0, 1, 2, 1, 0], apat=[2, 1, 1, 0, -1, 0], fin=0, base=[2, 1]),
}
LEAD_BARS = 1     # 歌いだし前の 前奏
OUTRO_BARS = 2    # おわりの 後奏


def bar16(st):
    return st["beats"] * 4


def timeline(dan):
    """秒：前奏 → 「◯のだん」→ 9行 → 後奏"""
    st = STYLES[dan]
    bar = 60 / st["bpm"] * st["beats"]
    head = LEAD_BARS * bar
    lines = [head + st["head"] * bar + i * st["line"] * bar for i in range(9)]
    end = lines[-1] + st["line"] * bar + OUTRO_BARS * bar
    return dict(bpm=st["bpm"], beats=st["beats"], bar=bar, head=head, lines=lines, end=end,
                name=st["name"], line_bars=st["line"], head_bars=st["head"])


def dist(n, units, rest, base):
    """n 個の 音を units（16分）に くばる。最後の音を のばす"""
    u = units - rest
    b = next((x for x in base if n * x <= u), 1)
    d = [b] * n
    if n * b > u:  # 1でも 入らない（ありえないが 念のため）
        d = [1] * n
    d[-1] += u - sum(d)
    return d


def tones(st, ch):
    root, q = chord(ch)
    out = sorted({p for p in range(st["lo"], st["hi"] + 1) if (p - root) % 12 in q})
    return out


def pick(ts, center):
    return min(range(len(ts)), key=lambda i: abs(ts[i] - center))


def bar_chord(st, bar_index):
    return st["prog"][bar_index % len(st["prog"])]


def notes_for(st, part_morae, pat, ch, final, var, shift=0):
    ts = tones(st, ch)
    i0 = pick(ts, st["center"]) + (1 if var else 0) + shift
    out = []
    for k, _ in enumerate(part_morae):
        idx = max(0, min(len(ts) - 1, i0 + pat[k % len(pat)]))
        out.append(ts[idx])
    if final:
        root, _ = chord(ch)
        roots = [p for p in ts if (p - root) % 12 == 0] or ts
        out[-1] = min(roots, key=lambda p: abs(p - (st["center"] - 2)))
    return out


def build_score(dan):
    """歌の段の 楽譜（VOICEVOX）。返り値：notes"""
    st = STYLES[dan]
    B = bar16(st)
    ev = [(None, LEAD_BARS * B, "")]
    # 「◯のだん」
    hm = morae(DAN_NAME[dan])
    hu = st["head"] * B
    hd = dist(len(hm), hu, 4, [4, 2, 1] if st["head"] > 1 else st["base"])
    ch = bar_chord(st, 0)
    hp = notes_for(st, hm, [0, 1, 2, 3, 4], ch, False, False, shift=-2)
    ev += [(p, r, m) for p, r, m in zip(hp, hd, hm)]
    if sum(hd) < hu:
        ev.append((None, hu - sum(hd), ""))
    # 九九 9行
    for i, (call, ans) in enumerate(KUKU[dan]):
        b0 = st["head"] + i * st["line"]                 # この行の 最初の 小節番号（前奏の あとから）
        half = st["line"] * B // 2
        cm, am = morae(call), morae(ans)
        ch_c = bar_chord(st, b0)
        ch_a = bar_chord(st, b0 + (st["line"] - 1 if st["line"] > 1 else 0))
        cd = dist(len(cm), half, 0, st["base"])
        ad = dist(len(am), half, 2, st["base"])
        cp = notes_for(st, cm, st["cpat"], ch_c, False, i % 2 == 1)
        ap = notes_for(st, am, st["apat"], ch_a, True, i % 2 == 1)
        ev += [(p, r, m) for p, r, m in zip(cp, cd, cm)]
        ev += [(p, r, m) for p, r, m in zip(ap, ad, am)]
        ev.append((None, half - sum(ad), ""))
    ev.append((None, OUTRO_BARS * B, ""))
    s16 = 60 / st["bpm"] / 4
    notes, pos = [], 0
    for p, r, m in ev:
        f0 = round(pos * s16 * FPS); pos += r; f1 = round(pos * s16 * FPS)
        notes.append({"key": p, "frame_length": f1 - f0, "lyric": m})
    return {"notes": notes}


HOST = "http://127.0.0.1:50021"


def post(path, body=None):
    req = urllib.request.Request(HOST + path, data=json.dumps(body).encode() if body is not None else b"",
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=170) as r:
        return r.read()


def main():
    mode, out = sys.argv[1], sys.argv[2]
    dans = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else list(range(2, 10))
    os.makedirs(out, exist_ok=True)
    tl = {d: timeline(d) for d in range(1, 10)}
    json.dump(tl, open(os.path.join(out, "timeline.json"), "w"), ensure_ascii=False, indent=1)
    for d in dans:
        st = STYLES[d]
        if st["kind"] == "sing":
            sc = build_score(d)
            if mode == "score":
                json.dump(sc, open(os.path.join(out, f"score_{d}.json"), "w"))
            else:
                q = json.loads(post(f"/sing_frame_audio_query?speaker={TEACHER}", sc))
                open(os.path.join(out, f"voice_{d}.wav"), "wb").write(post(f"/frame_synthesis?speaker={SINGER}", q))
            print("ok", d, st["name"])
        elif st["kind"] == "rap" and mode == "sing":
            text = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in DAN_NAME[d]) + "！"
            q = json.loads(post(f"/audio_query?speaker={TALKER}&text={urllib.parse.quote(text)}"))
            q["prePhonemeLength"] = 0.02; q["postPhonemeLength"] = 0.05; q["speedScale"] = 1.1
            open(os.path.join(out, f"rap_head_{d}.wav"), "wb").write(post(f"/synthesis?speaker={TALKER}", q))
            print("ok", d, "rap head")


if __name__ == "__main__":
    main()
