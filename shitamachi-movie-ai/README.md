# shitamachi-movie-ai — YouTube動画 全自動生成システム

「下町ロケット」の世界観で、世界を裏で支える日本の無名中小企業・町工場の
超ニッチ最先端技術を紹介する動画（15〜20分）を、リサーチから MP4 書き出しまで
完全自動で生成するパイプライン。

## ターゲット・構成の型

- **ターゲット**: 40〜50代男性、ビジネス層、ものづくり・逆転劇が好きな層
- **構成パターン（全動画共通）**:
  1. 冒頭の不安 — 「日本終了論」的な危機感の提示
  2. 驚きの反転 — 世界の最先端製品の命綱を握るのは日本の地方の無名企業
  3. 技術の解説 — 他国が真似できない職人技・特許・開発の人間ドラマ
  4. 結末 — 日本のものづくりの底力への誇りと感動

## パイプライン全体像

```
main.py（司令塔・冪等・途中再開可）
  │
  ├─ ステップ1  scripts/generate_script.py
  │     Claude API（Web検索ツール）で実在企業をリサーチ
  │     → 構成の型に沿った6章構造の台本JSONを data/scripts/ に出力
  │
  ├─ ステップ2  scripts/generate_images.py
  │     台本の各章から英語プロンプトを自動生成（固定スタイル呪文を付与）
  │     → DALL-E 3 / FLUX で章ごとに3〜5枚、計25〜30枚を assets/images/ に連番保存
  │
  ├─ ステップ3  scripts/generate_audio.py
  │     OpenAI TTS（nova・NHK解説調の指示付き）で章ごとにナレーション生成
  │     → Whisper でタイムスタンプを取得し SRT を assets/subtitles/ に出力
  │
  └─ ステップ4  scripts/edit_video.py
        MoviePy v2 で 音声＋画像スライドショー＋BGM＋焼き付け字幕 を統合
        → output/ に 1080p MP4（YouTubeアップロード可能品質）を書き出し
```

各ステップの受け渡しは**ファイル**（JSON / PNG / MP3 / SRT）で行う。
API呼び出しは全ステップで再実行時にスキップされる冪等設計とし、
途中で失敗しても `python main.py --from-step N` で再開できる。

## 台本JSONスキーマ（ステップ間の契約）

```json
{
  "title": "動画タイトル",
  "company": "企業名",
  "sources": ["リサーチで参照したURL"],
  "sections": [
    {
      "id": 1,
      "role": "hook | reversal | tech_1 | tech_2 | drama | ending",
      "heading": "章タイトル",
      "narration": "ナレーション本文（丁寧語）",
      "image_prompts": ["英語プロンプト × 3〜5"]
    }
  ]
}
```

## 採用API と選定理由・費用（1本あたり概算）

| ステップ | 採用 | 代替 | 1本あたり費用目安 |
| --- | --- | --- | --- |
| 台本 | **Claude API（Web検索ツール付き）** | Perplexity API | 〜$0.5 |
| 画像 | **DALL-E 3**（初期）→ FLUX via Replicate（量産期） | Midjourney(非公式APIのみ=規約違反リスク) | DALL-E3: 〜$2.4 / FLUX: 〜$0.1 |
| 音声 | **OpenAI TTS (gpt-4o-mini-tts, nova)** + Whisper字幕 | ElevenLabs（高品質・文字単位タイムスタンプ） | OpenAI: 〜$0.5 / 11Labs: 月$22〜 |
| 編集 | **MoviePy v2 + imageio-ffmpeg** | ffmpeg直叩き（速いが保守性低） | $0 |

**合計: 1本 約$3.5（DALL-E 3構成）／ 約$1.1（FLUX構成）**

## セットアップ

```bash
cd shitamachi-movie-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # APIキーを記入
python main.py
```

BGM はエピック・オーケストラ調のフリー音源（YouTube Audio Library 等、
商用利用可・クレジット条件を確認したもの）を `assets/bgm/` に手動で1曲以上
配置する。編集ステップが自動で尺に合わせてループ・音量調整する。

## 運用上の重要リスク（必読）

1. **事実誤認・名誉毀損リスク（最重要）**: 実在企業を扱うため、LLMの
   ハルシネーションで「事実でない技術・取引先」を語ると法的リスクになる。
   台本JSONに必ず出典URL（sources）を残し、**公開前に人間が出典と照合する
   工程をワークフローに固定する**。ここだけは自動化しない。
2. **YouTube収益化ポリシー**: 完全自動生成の「量産型」コンテンツは
   収益化審査で弾かれる事例がある。ナレーション原稿への人間の編集・
   独自の見解の追加を運用に組み込むこと。
3. **Midjourney**: 公式APIが存在せず、非公式APIは規約違反でアカウント
   凍結リスクがあるため採用しない。
4. **BGM著作権**: 「フリー音源の自動取得」はライセンス確認を自動化できない
   ため、人間が確認済みの音源を `assets/bgm/` に置く方式とする。
