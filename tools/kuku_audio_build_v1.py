#!/usr/bin/env python3
"""九九アプリ用の音声を一括生成する（Cloud Shell で実行）

使い方:
  python3 kuku_audio_build_v1.py <GCPプロジェクトID>

声: Google Cloud TTS WaveNet
  A = ja-JP-Wavenet-A（女声） / C = ja-JP-Wavenet-C（男声）
  どちらもピッチ -1.0・速さ 1.20
  すべての音声を両方の声で作り、アプリ側で男女を散りばめて使う。

作るもの（それぞれ A と C の2本ずつ）:
  full_3x8_A.mp3   … まるごと「さんぱ にじゅうし」（81本）
  call_3x8_A.mp3   … かけ声だけ「さんぱ」（81本）
  ans_24_A.mp3     … こたえだけ「にじゅうし」（こたえの数ごと）
  ph_<id>_A.mp3    … ほめことば・ナレーション
  manifest.json    … アプリが読む一覧（読み・ファイル名）
"""
import base64
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
VOICES = {
    "A": {"languageCode": "ja-JP", "name": "ja-JP-Wavenet-A"},
    "C": {"languageCode": "ja-JP", "name": "ja-JP-Wavenet-C"},
}
AUDIO = {"audioEncoding": "MP3", "pitch": -1.0, "speakingRate": 1.2}

# 九九の唱え方 [だん][かける数-1] = (かけ声, こたえ)
KUKU = {
    1: [("いんいちが", "いち"), ("いんにが", "に"), ("いんさんが", "さん"), ("いんしが", "し"),
        ("いんごが", "ご"), ("いんろくが", "ろく"), ("いんしちが", "しち"), ("いんはちが", "はち"),
        ("いんくが", "く")],
    2: [("にいちが", "に"), ("ににんが", "し"), ("にさんが", "ろく"), ("にしが", "はち"),
        ("にご", "じゅう"), ("にろく", "じゅうに"), ("にしち", "じゅうし"), ("にはち", "じゅうろく"),
        ("にく", "じゅうはち")],
    3: [("さんいちが", "さん"), ("さんにが", "ろく"), ("さざんが", "く"), ("さんし", "じゅうに"),
        ("さんご", "じゅうご"), ("さぶろく", "じゅうはち"), ("さんしち", "にじゅういち"),
        ("さんぱ", "にじゅうし"), ("さんく", "にじゅうしち")],
    4: [("しいちが", "し"), ("しにが", "はち"), ("しさん", "じゅうに"), ("しし", "じゅうろく"),
        ("しご", "にじゅう"), ("しろく", "にじゅうし"), ("ししち", "にじゅうはち"),
        ("しは", "さんじゅうに"), ("しく", "さんじゅうろく")],
    5: [("ごいちが", "ご"), ("ごに", "じゅう"), ("ごさん", "じゅうご"), ("ごし", "にじゅう"),
        ("ごご", "にじゅうご"), ("ごろく", "さんじゅう"), ("ごしち", "さんじゅうご"),
        ("ごは", "しじゅう"), ("ごっく", "しじゅうご")],
    6: [("ろくいちが", "ろく"), ("ろくに", "じゅうに"), ("ろくさん", "じゅうはち"),
        ("ろくし", "にじゅうし"), ("ろくご", "さんじゅう"), ("ろくろく", "さんじゅうろく"),
        ("ろくしち", "しじゅうに"), ("ろくは", "しじゅうはち"), ("ろっく", "ごじゅうし")],
    7: [("しちいちが", "しち"), ("しちに", "じゅうし"), ("しちさん", "にじゅういち"),
        ("しちし", "にじゅうはち"), ("しちご", "さんじゅうご"), ("しちろく", "しじゅうに"),
        ("しちしち", "しじゅうく"), ("しちは", "ごじゅうろく"), ("しちく", "ろくじゅうさん")],
    8: [("はちいちが", "はち"), ("はちに", "じゅうろく"), ("はちさん", "にじゅうし"),
        ("はちし", "さんじゅうに"), ("はちご", "しじゅう"), ("はちろく", "しじゅうはち"),
        ("はちしち", "ごじゅうろく"), ("はっぱ", "ろくじゅうし"), ("はっく", "しちじゅうに")],
    9: [("くいちが", "く"), ("くに", "じゅうはち"), ("くさん", "にじゅうしち"),
        ("くし", "さんじゅうろく"), ("くご", "しじゅうご"), ("くろく", "ごじゅうし"),
        ("くしち", "ろくじゅうさん"), ("くは", "しちじゅうに"), ("くく", "はちじゅういち")],
}

# ほめことば・ナレーション（id, 読み）
PHRASES = [
    ("dan1", "いちのだん"), ("dan2", "にのだん"), ("dan3", "さんのだん"),
    ("dan4", "よんのだん"), ("dan5", "ごのだん"), ("dan6", "ろくのだん"),
    ("dan7", "ななのだん"), ("dan8", "はちのだん"), ("dan9", "きゅうのだん"),
    ("praise1", "すごーい！ せいかい！"), ("praise2", "やったね！"),
    ("praise3", "そのちょうし！"), ("praise4", "かんぺき！"), ("praise5", "てんさい！"),
    ("oshii", "おしい！ もういっかい！"), ("daijoubu", "だいじょうぶ。 いっしょに いってみよう。"),
    ("issho", "いっしょに いってみよう！"), ("tsuzuki", "つづきを いってね！"),
    ("dore", "どれかな？"), ("kiitene", "よーく きいてね。"),
    ("clear", "ぜんぶ いえたね！ すごい！"), ("nakama", "あたらしい なかまが ふえたよ！"),
    ("start", "はじめるよ！"), ("mouikkai", "もういっかい きく？"),
]


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def synth(token, project, voice, text):
    body = {"input": {"text": text}, "voice": VOICES[voice], "audioConfig": AUDIO}
    for attempt in range(5):
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project,
                     "Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return base64.b64decode(json.load(r)["audioContent"])
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code} {e.read().decode(errors='replace')[:200]}")


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 kuku_audio_build_v1.py <GCPプロジェクトID>")
        sys.exit(1)
    project = sys.argv[1]
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    outdir = f"kuku_audio_{stamp}"
    os.makedirs(outdir, exist_ok=True)

    r = sh(f"gcloud services enable texttospeech.googleapis.com --project={project}")
    if r.returncode != 0:
        print("⚠ API 有効化でエラー（すでに有効なら問題なし）。生成を続けます。")
    token = sh("gcloud auth print-access-token").stdout.strip()

    # 作るものの一覧
    jobs = []  # (ファイル名の頭, 読み)
    manifest = {"voices": list(VOICES), "kuku": {}, "answers": {}, "phrases": {}}
    for dan, rows in KUKU.items():
        for i, (call, ans) in enumerate(rows, 1):
            key = f"{dan}x{i}"
            val = dan * i
            manifest["kuku"][key] = {"a": dan, "b": i, "answer": val,
                                     "call": call, "ansYomi": ans}
            jobs.append((f"full_{key}", f"{call} {ans}"))
            jobs.append((f"call_{key}", call))
            if str(val) not in manifest["answers"]:
                manifest["answers"][str(val)] = ans
                jobs.append((f"ans_{val}", ans))
    for pid, text in PHRASES:
        manifest["phrases"][pid] = text
        jobs.append((f"ph_{pid}", text))

    total = len(jobs) * len(VOICES)
    chars = sum(len(t) for _, t in jobs) * len(VOICES)
    print(f"▶ {total} 本を生成します（約 {chars} 文字）")
    errors, n = [], 0
    for base, text in jobs:
        for v in VOICES:
            n += 1
            fname = f"{base}_{v}.mp3"
            try:
                with open(os.path.join(outdir, fname), "wb") as f:
                    f.write(synth(token, project, v, text))
            except Exception as e:  # noqa: BLE001
                errors.append(f"{fname}「{text}」: {e}")
            if n % 50 == 0 or n == total:
                print(f"  {n}/{total}")

    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    zname = f"{outdir}.zip"
    with zipfile.ZipFile(zname, "w") as z:
        for fn in sorted(os.listdir(outdir)):
            z.write(os.path.join(outdir, fn), os.path.join(outdir, fn))
    print(f"\n✅ 完了: {zname}（エラー {len(errors)} 件）")
    for e in errors[:20]:
        print("  ×", e)
    subprocess.run(["cloudshell", "download", zname], check=False)


if __name__ == "__main__":
    main()
