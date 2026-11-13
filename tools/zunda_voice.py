#!/usr/bin/env python3
"""ずんだもん（VOICEVOX）のナレーション音声をまとめて作る

使い方（VOICEVOX ENGINE を 127.0.0.1:50021 で起動しておく）:
  python3 zunda_voice.py <出力フォルダ> [開始番号] [終了番号]

出力: <id>.wav（アプリ側で mp3 にして public/audio/z/ に置く）
"""
import json
import os
import sys
import urllib.parse
import urllib.request

HOST = "http://127.0.0.1:50021"
SPEAKER = 3   # ずんだもん ノーマル

ONES = ["", "いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう"]


def yomi(n):
    t, o = divmod(n, 10)
    s = ""
    if t == 1:
        s = "じゅう"
    elif t > 1:
        s = ONES[t] + "じゅう"
    return s + ONES[o]


KOZU = {1: "いっこずつ", 2: "にこずつ", 3: "さんこずつ", 4: "よんこずつ", 5: "ごこずつ",
        6: "ろっこずつ", 7: "ななこずつ", 8: "はっこずつ", 9: "きゅうこずつ"}

KUKU = {
 1:[("いんいちが","いち"),("いんにが","に"),("いんさんが","さん"),("いんしが","し"),("いんごが","ご"),("いんろくが","ろく"),("いんしちが","しち"),("いんはちが","はち"),("いんくが","く")],
 2:[("にいちが","に"),("ににんが","し"),("にさんが","ろく"),("にしが","はち"),("にご","じゅう"),("にろく","じゅうに"),("にしち","じゅうし"),("にはち","じゅうろく"),("にく","じゅうはち")],
 3:[("さんいちが","さん"),("さんにが","ろく"),("さざんが","く"),("さんし","じゅうに"),("さんご","じゅうご"),("さぶろく","じゅうはち"),("さんしち","にじゅういち"),("さんぱ","にじゅうし"),("さんく","にじゅうしち")],
 4:[("しいちが","し"),("しにが","はち"),("しさん","じゅうに"),("しし","じゅうろく"),("しご","にじゅう"),("しろく","にじゅうし"),("ししち","にじゅうはち"),("しは","さんじゅうに"),("しく","さんじゅうろく")],
 5:[("ごいちが","ご"),("ごに","じゅう"),("ごさん","じゅうご"),("ごし","にじゅう"),("ごご","にじゅうご"),("ごろく","さんじゅう"),("ごしち","さんじゅうご"),("ごは","しじゅう"),("ごっく","しじゅうご")],
 6:[("ろくいちが","ろく"),("ろくに","じゅうに"),("ろくさん","じゅうはち"),("ろくし","にじゅうし"),("ろくご","さんじゅう"),("ろくろく","さんじゅうろく"),("ろくしち","しじゅうに"),("ろくは","しじゅうはち"),("ろっく","ごじゅうし")],
 7:[("しちいちが","しち"),("しちに","じゅうし"),("しちさん","にじゅういち"),("しちし","にじゅうはち"),("しちご","さんじゅうご"),("しちろく","しじゅうに"),("しちしち","しじゅうく"),("しちは","ごじゅうろく"),("しちく","ろくじゅうさん")],
 8:[("はちいちが","はち"),("はちに","じゅうろく"),("はちさん","にじゅうし"),("はちし","さんじゅうに"),("はちご","しじゅう"),("はちろく","しじゅうはち"),("はちしち","ごじゅうろく"),("はっぱ","ろくじゅうし"),("はっく","しちじゅうに")],
 9:[("くいちが","く"),("くに","じゅうはち"),("くさん","にじゅうしち"),("くし","さんじゅうろく"),("くご","しじゅうご"),("くろく","ごじゅうし"),("くしち","ろくじゅうさん"),("くは","しちじゅうに"),("くく","はちじゅういち")],
}

PHRASES = {
    "kazoete": "ぜんぶで いくつか、かぞえるのだ！",
    "tapcount": "ひとつずつ タッチして、かぞえるのだ！",
    "zenbude": "ぜんぶで、いくつ？",
    "noseru": "のせるのだ！",
    "tobi": "おさらを じゅんばんに タッチするのだ！",
    "retsu": "いちれつずつ タッチするのだ！",
    "kurutto": "くるっと まわしても、おなじ かずなのだ！",
    "kuku": "くくで こたえるのだ！",
    "kakeru": "かける",
    "wa": "は",
    "ok1": "せいかいなのだ！", "ok2": "すごいのだ！", "ok3": "てんさいなのだ！",
    "ok4": "やったのだ！", "ok5": "そのちょうしなのだ！",
    "ng": "おしいのだ！ もういっかい！",
    "ooi": "おおすぎるのだ！",
    "dekita": "できたのだ！",
    "lvup": "レベルアップなのだ！",
    "max": "マックスなのだ！ おうかん、ゲットなのだ！",
    "stamp": "スタンプ ゲットなのだ！",
    "newstage": "あたらしい ステージが、ひらいたのだ！",
    "allmax": "レベル ごじゅう！ ぜんぶ マックスなのだ！ おおきな おうかんなのだ！",
    "start": "いくのだ！",
    "kukuopen": "くくの へやが、ひらいたのだ！",
    "st1": "かぞえて！", "st2": "つくって！", "st3": "とびかぞえ！", "st4": "ならべて！", "st5": "くくで、こたえて！",
    "okaeri": "おかえりなのだ！",
}


def items():
    out = []
    for n in range(1, 82):
        out.append((f"n{n}", yomi(n)))
    for n, t in KOZU.items():
        out.append((f"kozu{n}", t))
    for n in range(1, 10):
        out.append((f"sara{n}", f"おさら {yomi(n)}まいに"))
    for k, t in PHRASES.items():
        out.append((k, t))
    seen = set()
    for d, rows in KUKU.items():
        for i, (c, a) in enumerate(rows, 1):
            out.append((f"c{d}x{i}", c))
            if d * i not in seen:
                seen.add(d * i)
                out.append((f"a{d * i}", a))
    return out


def post(path, body=None):
    req = urllib.request.Request(HOST + path, data=json.dumps(body).encode() if body is not None else b"",
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    out = sys.argv[1]
    lst = items()
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    b = int(sys.argv[3]) if len(sys.argv) > 3 else len(lst)
    os.makedirs(out, exist_ok=True)
    if a == 0:
        print("total", len(lst))
    for key, text in lst[a:b]:
        # 数・九九は カタカナで 入れる（ひらがなだと「はち」が「ワチ」になるなど 読みまちがいが出る）
        if key[0] in "nca" and key[1:2].isdigit() or key.startswith(("kozu", "sara")):
            text = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in text)
        fn = os.path.join(out, key + ".wav")
        if os.path.exists(fn):
            continue
        q = json.loads(post(f"/audio_query?speaker={SPEAKER}&text={urllib.parse.quote(text)}"))
        q["speedScale"] = 1.05
        q["prePhonemeLength"] = 0.05
        q["postPhonemeLength"] = 0.08
        open(fn, "wb").write(post(f"/synthesis?speaker={SPEAKER}", q))
    print("done", a, b)


if __name__ == "__main__":
    main()
