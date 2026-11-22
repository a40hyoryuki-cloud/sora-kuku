# そらのくくランド

4さいの そらくん向け、九九を「音で」覚えるゲーム。

- 公開: Firebase Hosting（GCP: stock-screening-496006 / サイト: sora-kuku）
- `main` に push すると GitHub Actions で自動公開
- 音声: Google Cloud TTS WaveNet（A=女声 / C=男声、ピッチ-1.0・速さ1.20）を `public/audio/` に置く
  - 生成: `tools/kuku_audio_build_v1.py`（Cloud Shell）
  - 音声が無いあいだは端末の読み上げで代わりに動く

## あそび
- きく：段をリズムに乗せて流す（速さ3段階）
- こたえて！：かけ声 → 間 → こたえ（じゅんばん / バラバラ）
- どれかな？：3びきが声で答える → 正しい子をタッチ
- ほし ⭐ が8こたまるごとに なかまが1ぴき増える（45ひき）
- 段は最初から全部あそべる（くくのへや・くくのうたは いつでも入れる）
