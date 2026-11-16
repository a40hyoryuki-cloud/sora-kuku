#!/usr/bin/env python3
"""九九の歌：段ごとの 伴奏を 合成して、ずんだもんの 歌と まぜ、曲ファイルにする（すべて オリジナル）

  python3 kuku_backing.py <歌の素材フォルダ> <ずんだもん話し声フォルダ> <1の段の素材フォルダ> <出力フォルダ>

  歌の素材   : voice_<段>.wav（kuku_songs.py sing）, rap_head_2.wav
  話し声     : c<段>x<数>.wav, a<こたえ>.wav（zunda_voice.py）… ラップの段で使う
  1の段の素材: bgm.f32（アプリの BGM を 44.1kHz で 書き出したもの）, sing_1_3003.wav（いまの 1の段の 歌）
  出力       : song_<段>.mp3, songs.json（時刻表）
"""
import json
import os
import subprocess
import sys

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuku_songs as KS  # noqa: E402
from kuku_sing import KUKU  # noqa: E402

SR = 44100
RNG = np.random.default_rng(7)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def lp(x, fc, o=2):
    b, a = butter(o, min(fc, SR / 2 - 100) / (SR / 2), "low"); return lfilter(b, a, x)


def hp(x, fc, o=2):
    b, a = butter(o, fc / (SR / 2), "high"); return lfilter(b, a, x)


def bp(x, f1, f2, o=2):
    b, a = butter(o, [f1 / (SR / 2), min(f2, SR / 2 - 100) / (SR / 2)], "band"); return lfilter(b, a, x)


def dec(n, tau, att=.003):
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    k = max(1, int(att * SR)); e[:k] *= np.linspace(0, 1, k)
    return e


def osc(kind, f, d, duty=.5):
    t = tt(d)
    ph = (f * t) % 1.0
    if kind == "sine": return np.sin(2 * np.pi * f * t)
    if kind == "tri": return 2 * np.abs(2 * ph - 1) - 1
    if kind == "saw": return 2 * ph - 1
    if kind == "sq": return np.where(ph < duty, 1.0, -1.0)
    raise ValueError(kind)


def noise(d):
    return RNG.uniform(-1, 1, int(d * SR))


# ---------- 楽器 ----------
def kick(g=1.0, f0=120, f1=45):
    d = .35; t = tt(d); f = f1 + (f0 - f1) * np.exp(-t / .03)
    return g * np.sin(2 * np.pi * np.cumsum(f) / SR) * dec(len(t), .12)


def snare(g=1.0):
    d = .25; n = bp(noise(d), 1500, 8000) * dec(int(d * SR), .06)
    return g * (.8 * n + .5 * np.sin(2 * np.pi * 190 * tt(d)) * dec(int(d * SR), .04))


def hat(g=1.0, op=False):
    d = .4 if op else .06; return g * hp(noise(d), 7000) * dec(int(d * SR), .12 if op else .018)


def clap(g=1.0):
    d = .3; x = np.zeros(int(d * SR))
    for o in (0, .01, .022):
        k = int(o * SR); n = bp(noise(.2), 1000, 5000) * dec(int(.2 * SR), .02 if o < .02 else .07)
        x[k:k + len(n)] += n[:len(x) - k]
    return g * x


def tom(f=70, g=1.0, d=.4):
    t = tt(d); fr = f * (1 + .5 * np.exp(-t / .02))
    return g * np.sin(2 * np.pi * np.cumsum(fr) / SR) * dec(len(t), d / 3)


def shaker(g=1.0):
    d = .07; e = np.minimum(np.arange(int(d * SR)) / (.015 * SR), 1) * dec(int(d * SR), .02)
    return g * hp(noise(d), 5000) * e


def tamb(g=1.0):
    d = .1; return g * (.6 * bp(noise(d), 3000, 9000) * dec(int(d * SR), .02) + .5 * np.sin(2 * np.pi * 820 * tt(d)) * dec(int(d * SR), .03))


def agogo(f, g=1.0):
    d = .3; t = tt(d)
    return g * (np.sin(2 * np.pi * f * t) + .4 * np.sin(2 * np.pi * f * 2.76 * t)) * dec(len(t), .09)


def crash(g=1.0):
    d = 1.6; return g * hp(noise(d), 3000) * dec(int(d * SR), .45, .002)


def bass(m, d, g=1.0, kind="tri", cut=900):
    x = osc(kind, hz(m), d); x = lp(x, cut) if kind != "sine" else x
    e = dec(len(x), d * .9, .005); r = min(len(x), int(.02 * SR)); e[-r:] *= np.linspace(1, 0, r)
    return g * x * e


def pad(ms, d, g=1.0, cut=1600, att=.08):
    x = sum(osc("saw", hz(m) * dt, d) for m in ms for dt in (0.997, 1.003)) / (2 * len(ms))
    x = lp(x, cut); n = len(x); e = np.ones(n)
    a = min(n, int(att * SR)); e[:a] = np.linspace(0, 1, a)
    r = min(n, int(.15 * SR)); e[-r:] *= np.linspace(1, 0, r)
    return g * x * e


def mbox(m, g=1.0, d=1.4):
    t = tt(d); f = hz(m)
    x = np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t / .2) + .15 * np.sin(2 * np.pi * 4.2 * f * t) * np.exp(-t / .1)
    return g * x * dec(len(t), .5, .002)


def piano(m, d=1.6, g=1.0):
    t = tt(d); f = hz(m)
    x = sum((.6 ** k) * np.sin(2 * np.pi * f * (k + 1) * t) * np.exp(-t * (1.5 + k * 1.2)) for k in range(5))
    return g * x * dec(len(t), 1.0, .004)


def epiano(m, d=1.2, g=1.0):
    t = tt(d); f = hz(m)
    x = (np.sin(2 * np.pi * f * t) + .25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / .15)) * (1 + .15 * np.sin(2 * np.pi * 5 * t))
    return g * x * dec(len(t), .7, .004)


def pluck(m, d=.5, g=1.0):
    f = hz(m); n = int(d * SR); p = max(2, int(SR / f))
    buf = RNG.uniform(-1, 1, p); out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = .5 * (buf[i % p] + buf[(i + 1) % p]) * .996
    return g * out


def guitar(root, d, g=1.0):
    ms = [root, root + 7, root + 12]
    x = sum(osc("saw", hz(m) * dt, d) for m in ms for dt in (.995, 1.005))
    x = np.tanh(3.5 * x / 3); x = lp(x, 2800)
    e = dec(len(x), d * .8, .003); r = min(len(x), int(.01 * SR)); e[-r:] *= np.linspace(1, 0, r)
    return g * x * e


def brass(ms, d, g=1.0):
    n = int(d * SR); t = np.arange(n) / SR
    x = sum(osc("saw", hz(m), d) for m in ms) / len(ms)
    out = np.zeros(n); seg = int(.01 * SR)
    for i in range(0, n, seg):                                 # だんだん あかるく なる 音色
        fc = 600 + 2200 * (1 - np.exp(-(i / SR) / .04))
        out[i:i + seg] = lp(x[max(0, i - 256):i + seg], fc)[-len(x[i:i + seg]):]
    e = np.ones(n); a = int(.02 * SR); e[:a] = np.linspace(0, 1, a); r = min(n, int(.05 * SR)); e[-r:] *= np.linspace(1, 0, r)
    return g * out * e


def chip(m, d, g=1.0, duty=.25):
    x = osc("sq", hz(m), d, duty); e = np.ones(len(x)); r = min(len(x), int(.01 * SR)); e[-r:] *= np.linspace(1, 0, r)
    return g * x * e * .5


# ---------- 和音 ----------
def chord_ms(name, lo=55):
    r, q = KS.chord(name)
    base = lo + ((r - lo) % 12)
    return [base + i for i in q]


def root_m(name, lo=36):
    r, _ = KS.chord(name); return lo + ((r - lo) % 12)


class Mix:
    def __init__(self, dur):
        self.x = np.zeros(int((dur + 3) * SR))

    def add(self, sig, t, g=1.0):
        k = int(t * SR)
        if k >= len(self.x): return
        n = min(len(sig), len(self.x) - k); self.x[k:k + n] += g * sig[:n]


# ---------- 曲調ごとの 1小節 ----------
def bar_rap(M, t0, q, ch, i, last):
    for b in (0, 1.75, 2.5): M.add(kick(.9), t0 + b * q)
    for b in (1, 3): M.add(snare(.7), t0 + b * q)
    for k in range(8): M.add(hat(.25 if k % 2 else .35), t0 + (k * .5 + (.08 if k % 2 else 0)) * q)
    r = root_m(ch, 33)
    for b, d in ((0, .9), (1.75, .5), (2.5, 1.2)): M.add(bass(r, d * q, .8, "sine"), t0 + b * q)
    for m in chord_ms(ch, 57): M.add(epiano(m, 1.6 * q, .22), t0); M.add(epiano(m, .8 * q, .16), t0 + 2.5 * q)


def bar_waltz(M, t0, q, ch, i, last):
    M.add(bass(root_m(ch, 41), .9 * q, .7, "tri"), t0)
    ms = chord_ms(ch, 65)
    for b in (1, 2):
        for m in ms: M.add(mbox(m, .16), t0 + b * q)
    M.add(pad(chord_ms(ch, 53), 3 * q, .08, 1200, .3), t0)
    if i % 2 == 0: M.add(mbox(ms[-1] + 12, .12), t0)


def bar_march(M, t0, q, ch, i, last):
    r = root_m(ch, 40)
    M.add(bass(r, .8 * q, .9, "saw", 700), t0); M.add(bass(r + 7, .8 * q, .8, "saw", 700), t0 + 2 * q)
    for b in (1, 3): M.add(brass(chord_ms(ch, 60), .35 * q, .22), t0 + b * q)
    for b in (0, 2): M.add(tom(55, .8, .3), t0 + b * q)
    for b in (1, 3): M.add(snare(.5), t0 + b * q)
    if i % 4 == 3:
        for k in range(8): M.add(snare(.25 + .04 * k), t0 + (2 + k * .25) * q)
    if i % 4 == 0: M.add(crash(.18), t0)


def bar_rock(M, t0, q, ch, i, last):
    for b in (0, 2, 2.5): M.add(kick(1.0), t0 + b * q)
    for b in (1, 3): M.add(snare(.8), t0 + b * q)
    for k in range(8): M.add(hat(.25), t0 + k * .5 * q)
    if i % 4 == 0: M.add(crash(.25), t0)
    r = root_m(ch, 40)
    for k in range(8):
        M.add(guitar(r + 12, .42 * q, .16), t0 + k * .5 * q)
        M.add(bass(r, .45 * q, .55, "saw", 600), t0 + k * .5 * q)


def bar_samba(M, t0, q, ch, i, last):
    for b in (0, 2): M.add(tom(70, .45), t0 + b * q)
    for b in (1, 3): M.add(tom(62, 1.0), t0 + b * q)
    for k in (0, 2, 3, 5, 6, 8, 10, 11, 13, 14): M.add(tamb(.35), t0 + k * .25 * q)
    for k in range(16): M.add(shaker(.28 if k % 4 == 0 else .14), t0 + k * .25 * q)
    for b, f in ((0, 900), (.5, 650), (1, 900), (1.75, 650), (2.5, 900), (3, 650)): M.add(agogo(f, .12), t0 + b * q)
    r = root_m(ch, 38)
    for b, m, d in ((0, r, .7), (1.5, r + 7, .4), (2, r, .7), (3.5, r + 7, .4)): M.add(bass(m, d * q, .7, "tri"), t0 + b * q)
    for k in (2, 3, 6, 9, 10, 13):
        for m in chord_ms(ch, 60): M.add(pluck(m, .35, .12), t0 + k * .25 * q)


def bar_chip(M, t0, q, ch, i, last):
    for b in (0, 2): M.add(chip(36, .12, .9, .5) * np.exp(-tt(.12) / .05), t0 + b * q)
    for b in (1, 3): M.add(hp(noise(.12), 1500) * dec(int(.12 * SR), .05) * .45, t0 + b * q)
    for k in range(8): M.add(hp(noise(.03), 6000) * .15, t0 + k * .5 * q)
    r = root_m(ch, 40)
    for k in range(8): M.add(chip(r + (12 if k % 2 else 0), .45 * q, .35, .5), t0 + k * .5 * q)
    ms = chord_ms(ch, 64); arp = ms + [ms[0] + 12]
    for k in range(16): M.add(chip(arp[k % len(arp)], .22 * q, .12, .125), t0 + k * .25 * q)


def bar_lull(M, t0, q, ch, i, last):
    ms = chord_ms(ch, 50); seq = [ms[0], ms[2], ms[0] + 12, ms[1] + 12, ms[0] + 12, ms[2]]
    for k in range(8): M.add(piano(seq[k % len(seq)], 1.8, .22), t0 + k * .5 * q)
    M.add(pad(chord_ms(ch, 58), 4 * q, .05, 900, .4), t0)
    M.add(bass(root_m(ch, 34), 3.5 * q, .45, "sine"), t0)
    if i % 2 == 0: M.add(mbox(chord_ms(ch, 74)[0], .1, 2.0), t0)


def bar_dance(M, t0, q, ch, i, last):
    for b in range(4): M.add(kick(1.0, 140, 48), t0 + b * q)
    for b in (1, 3): M.add(clap(.6), t0 + b * q)
    for b in range(4): M.add(hat(.3, True), t0 + (b + .5) * q)
    for k in range(16): M.add(hat(.08), t0 + k * .25 * q)
    if i % 4 == 0: M.add(crash(.22), t0)
    r = root_m(ch, 38)
    for b in range(4): M.add(bass(r, .4 * q, .8, "saw", 500), t0 + (b + .5) * q)
    for b in range(4): M.add(pad(chord_ms(ch, 60), .42 * q, .3, 2600, .005), t0 + (b + .5) * q)


BARS = {"rap": bar_rap, 3: bar_waltz, 4: bar_march, 5: bar_rock, 6: bar_samba, 7: bar_chip, 8: bar_lull, 9: bar_dance}


def final_hit(M, t0, q, ch, kind):
    if kind in (5, 9, 4): M.add(crash(.3), t0); M.add(kick(1.0), t0)
    if kind == 5: M.add(guitar(root_m(ch, 40) + 12, 3 * q, .2), t0)
    elif kind in (3, 8): [M.add(mbox(m, .2, 2.5), t0) for m in chord_ms(ch, 65)]
    elif kind == 7: [M.add(chip(m, 2 * q, .15, .25), t0) for m in chord_ms(ch, 64)]
    elif kind == "rap": [M.add(epiano(m, 3 * q, .25), t0) for m in chord_ms(ch, 57)]
    else: M.add(pad(chord_ms(ch, 60), 3 * q, .3, 2000, .01), t0)
    M.add(bass(root_m(ch, 36), 2.5 * q, .7, "tri"), t0)


def load(fn):
    y, _ = librosa.load(fn, sr=SR, mono=True); return y


def rms(x):
    v = x[np.abs(x) > np.abs(x).max() * .05]; return np.sqrt(np.mean(v ** 2)) if len(v) else 1e-9


def build(dan, sing_dir, talk_dir):
    st = KS.STYLES[dan]; tl = KS.timeline(dan)
    q = 60 / st["bpm"]; bar = tl["bar"]; kind = "rap" if st["kind"] == "rap" else dan
    B = BARS[kind]
    nb = KS.LEAD_BARS + st["head"] + 9 * st["line"]
    back = Mix(tl["end"]); voice = Mix(tl["end"])
    for k in range(nb + 1):                       # 前奏・歌・後奏1小節
        i = k - KS.LEAD_BARS
        ch = st["prog"][-1] if i < 0 else st["prog"][min(i, nb - KS.LEAD_BARS) % len(st["prog"])] if k < nb else st["prog"][0]
        B(back, k * bar, q, ch, max(i, 0), k == nb)
    final_hit(back, (nb + 1) * bar, q, st["prog"][0], kind)
    if st["kind"] == "sing":
        voice.add(load(os.path.join(sing_dir, f"voice_{dan}.wav")), 0)
    else:
        voice.add(load(os.path.join(sing_dir, f"rap_head_{dan}.wav")), tl["head"])
        for b, (_c, _a) in enumerate(KUKU[dan], 1):
            t = tl["lines"][b - 1]
            for fn, at in ((f"c{dan}x{b}.wav", t), (f"a{dan * b}.wav", t + 2 * q)):
                y = load(os.path.join(talk_dir, fn))
                y = y[np.argmax(np.abs(y) > np.abs(y).max() * .03):]       # 頭の 無音を けずる
                lim = 1.85 * q
                if len(y) / SR > lim: y = librosa.effects.time_stretch(y, rate=(len(y) / SR) / lim)
                voice.add(y, at)
    return back.x, voice.x, tl


def song1(src):
    """1の段：いまの BGM（アプリと同じ）＋ いまの歌"""
    tl = KS.timeline(1); bar = tl["bar"]
    bgm = np.fromfile(os.path.join(src, "bgm.f32"), dtype=np.float32).astype(float)
    v = load(os.path.join(src, "sing_1_3003.wav"))
    n = int((tl["end"] + .5) * SR); off = int(round(3 * bar * SR))
    bg = np.tile(bgm, int(np.ceil((off + n) / len(bgm))) + 1)[off:off + n]
    f = int(1.2 * bar * SR); bg[-f:] *= np.linspace(1, 0, f)
    vv = np.zeros(n); vv[:min(n, len(v))] = v[:n]
    return bg, vv, tl


def master(back, voice, rel_db, fn):
    n = max(len(back), len(voice)); b = np.zeros(n); v = np.zeros(n); b[:len(back)] = back; v[:len(voice)] = voice
    gv = .16 / rms(v); gb = (.16 * 10 ** (rel_db / 20)) / rms(b)
    x = v * gv + b * gb
    x = x[:np.max(np.nonzero(np.abs(x) > 1e-4)) + int(.3 * SR)]
    x = x / max(1, np.abs(x).max() / .95)
    sf.write(fn + ".wav", x.astype(np.float32), SR, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", fn + ".wav", "-ac", "1", "-ar", "44100", "-b:a", "96k", fn + ".mp3"], check=True)
    os.remove(fn + ".wav")
    return len(x) / SR


def main():
    sing_dir, talk_dir, one_dir, out = sys.argv[1:5]
    dans = [int(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 else list(range(1, 10))
    os.makedirs(out, exist_ok=True)
    meta = {}
    jf = os.path.join(out, "songs.json")
    if os.path.exists(jf): meta = json.load(open(jf))
    for d in dans:
        if d == 1: back, voice, tl = song1(one_dir); rel = -8
        else: back, voice, tl = build(d, sing_dir, talk_dir); rel = -7 if KS.STYLES[d]["kind"] == "rap" else -8
        dur = master(back, voice, rel, os.path.join(out, f"song_{d}"))
        meta[str(d)] = dict(name=tl["name"], bpm=tl["bpm"], bar=round(tl["bar"], 5), head=round(tl["head"], 4),
                            lines=[round(x, 4) for x in tl["lines"]], end=round(tl["end"], 4), dur=round(dur, 3))
        print("ok", d, tl["name"], round(dur, 1), "s")
    json.dump(meta, open(jf, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
