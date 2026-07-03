# shitamachi-movie-ai — YouTube動画 全自動生成システム

チャンネルの看板:**「無名の日本人の手が、世界を動かしている物語」**

「下町ロケット」の世界観で、世界を裏で支える日本の技術の物語（15〜20分）を、
リサーチから素材出力まで自動生成するパイプライン。1チャンネル2シリーズ運用:

- `machikoba` — 町工場・世界を支える無名企業（主軸）
- `dento` — 伝統×ハイテク・職人技が最先端を支える（第二の柱）

構成の型（不安→反転→技術解説→人間ドラマ→誇り）と品質ゲートは全シリーズ共通。
**チャンネルの憲法: ナレーションで「すごい」「世界が絶賛」等の称賛語を使わない。**
事実と数字と物語だけを積み、誇りを感じるのは視聴者の仕事として残す。

```bash
python main.py --series machikoba            # 町工場シリーズで1本生成
python main.py --series dento --topic 金剛組  # 伝統×ハイテクで題材指定
```

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
  │     台本の各章のプロンプトに固定スタイル呪文を付与し、
  │     data/prompts/image_prompts.csv（スプレッドシート互換）と
  │     CODEX_TASK.md（Codex用指示書）をエクスポート
  │     → 画像生成は Codex（ChatGPT定額枠）に委譲。納品された画像を
  │       命名規則・解像度・16:9 で自動検収（--check）
  │
  └─ ステップ3  scripts/export_canva.py
        Canva入稿パッケージを data/canva/ に出力:
        章別ナレ原稿（AIナレーターに貼るだけ）/ storyboard.csv（章×画像×
        推定尺の設計図）/ CANVA_TASK.md（組み立て手順書+公開前チェックリスト）
        → 音声・字幕・BGM・組み立て・MP4書き出しは Canva（定額枠）で行う
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
| 画像 | **Codex に委譲**（ChatGPT定額枠・CSV指示書経由） | DALL-E 3(〜$2.4) / FLUX via Replicate(〜$0.1)。Midjourneyは非公式APIのみ=規約違反リスクで不採用 | $0（定額内） |
| 音声・字幕・編集 | **Canva に委譲**（AIナレーター+自動キャプション+組み立て+MP4書き出し。定額枠） | OpenAI TTS+Whisper+MoviePy による全自動化（コード実装が必要・音声$0.5/本） | $0（定額内） |

**合計: 1本 約$0.5（API実費）+ ChatGPT/Canva/Claude の定額利用料**

長尺ナレーションのTTSはCanvaのクレジット消費が未知数のため、パイロット1本で
実測すること。枠が足りない場合は代替（OpenAI TTS）に切り戻す。

### ステップ2の運用フロー（Codex委譲）

1. `python -m scripts.generate_images` → `data/prompts/image_prompts.csv` と
   `data/prompts/CODEX_TASK.md` が生成される（CSVはスプレッドシートに
   そのままインポート可能）
2. Codex に `CODEX_TASK.md` を渡す（リポジトリを開かせて「このタスクを
   実行しろ」だけでよい。ファイル名・保存先・仕様はすべて指示書にある）
3. Codex が `assets/images/` に連番PNGを納品
4. `python -m scripts.generate_images --check` で自動検収
   （不足・低解像度・16:9でない画像を列挙 → Codexに差し戻し）

Codex をローカル（CLI/デスクトップ）で動かせば画像は直接 `assets/images/`
に書き込まれ、git を経由しない（推奨。画像30枚をコミットするとリポジトリが
肥大化するため `.gitignore` 済み）。クラウド版 Codex に PR で納品させる場合
のみ `.gitignore` の画像除外を一時的に外すこと。

## セットアップ

```bash
cd shitamachi-movie-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY を記入（必要なキーはこれ1つ）
python main.py         # 台本 → 画像発注書 → Canva入稿パッケージ
```

パイプライン完了後、`data/canva/CANVA_TASK.md` の手順に沿って Canva 上で
音声・字幕・BGM を付けて組み立て、MP4 を `output/` に書き出す。
BGM は Canva オーディオ素材から商用利用可のエピック・オーケストラ調を選ぶ
（音量の目安は手順書に記載）。

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
4. **BGM著作権**: ライセンス確認は自動化できないため、Canva オーディオ素材の
   商用利用可のものを人間が選ぶ（公開前チェックリストに組み込み済み）。
