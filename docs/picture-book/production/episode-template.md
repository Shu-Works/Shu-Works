# エピソード標準テンプレート

**作成日**: 2026-06-17
**用途**: 全エピソード共通の「型」。1話作るたびにこの構造をコピーして埋める。
**思想**: テンプレは1つだけ作り込み（One home run）、以降は全話使い回す。毎回ゼロから考えない。

---

## 1. 標準フォルダ構成

```
docs/picture-book/episodes/ep0XX/
├── script.md          脚本（10シーン・約1000文字）。STEP2 の成果物。物語GOの対象
├── image-prompts.md   Google Flow 用 画像プロンプト10個（共通画風ブロック付き）。STEP3 の成果物
├── narration.md       通しナレーション原稿（音声生成にそのまま投入）。STEP5 の入力
├── youtube-meta.md     タイトル候補・説明文・タグ・サムネ文言。STEP7 の入力
└── assets/            生成物の置き場
    ├── img01.png 〜 img10.png   Google Flow 生成画像（16:9）
    ├── narration.mp3            AI音声
    └── ep0XX.mp4               完成動画
```

### 各ファイルの役割

| ファイル | 誰が作る | 役割 |
| --- | --- | --- |
| `script.md` | ChatGPT | 物語の本体。10シーン構成。ここの出来が動画の9割を決める |
| `image-prompts.md` | ChatGPT | 脚本を画にする指示書。共通画風ブロックで全話のトーンを統一 |
| `narration.md` | 脚本から整形 | 音声生成用。間・改行を整え、そのまま読み上げられる形 |
| `youtube-meta.md` | AI（制作部） | 公開時のメタ情報。タイトルで再生数が決まる |
| `assets/` | 各ツール | 画像・音声・動画の最終生成物 |

---

## 2. 画風固定ブロック（毎回使い回す共通スタイル指定文）

各画像プロンプトの **先頭に必ず貼る**。これがチャンネル全体の「絵の顔」になる。
温かく、感情に寄り添う、絵本タッチで統一する。

### 2.1 共通画風ブロック（英語・コピペ用）

```
Storybook illustration, soft warm watercolor and gouache style, gentle hand-painted texture,
emotional and heartwarming atmosphere, cinematic soft lighting with warm golden tones,
muted earthy color palette, delicate brush strokes, slightly dreamy and nostalgic mood,
clean composition with depth, picture-book aesthetic for an inspirational story, --ar 16:9 --no text, watermark, logo
```

### 2.2 日本語補足（意図のメモ）

```
絵本タッチ・水彩＋ガッシュの柔らかい質感／温かみのある手描き感／感情に寄り添う雰囲気／
黄金色の柔らかい光・映画的ライティング／落ち着いたアースカラー／少しドリーミーで懐かしいムード／
奥行きのある整った構図／16:9・文字や透かしは入れない
```

### 2.3 キャラシート行（各話で1回決めて、全プロンプトに貼る）

主人公の外見を1文に固定する。例：

```
Main character: a 10-year-old Japanese boy, short black hair, round gentle face,
wearing a faded navy school uniform, slightly small build, kind tired eyes.
```

> ルール：このキャラシート行を全10プロンプトに貼ることで、Google Flow 上で同一人物性を担保する。年齢が物語で変わる場合は、年齢部分だけ差し替える（例：10歳→中年）。

---

## 3. script.md の書式

各シーンに以下3点を必ず記載：

```
## 【シーン01】
**ナレーション本文**：（実際に読み上げる文。1〜3文）
**画面メモ**：（この絵で何を見せるか。構図・表情・場所・時間帯）
```

- 全10シーン合計で **約1000文字**（ナレーション本文の合計）
- 物語構造：導入（1〜3）→ 葛藤・どん底（4〜6）→ 転機・挑戦（7〜9）→ 救い・気づき（10）

---

## 4. image-prompts.md の書式

```
## シーン01 画像プロンプト
[共通画風ブロック]
[キャラシート行]
Scene: （英語で情景を記述）

日本語補足：（何を描いた絵か一行）
```

- 全10プロンプトの先頭は必ず共通画風ブロック＋キャラシート行から始める
- Scene 部分だけがシーンごとに変わる

---

## 5. narration.md の書式

- 通し原稿。シーン番号は【】で見出しに残してよいが、読み上げ対象はナレーション本文のみ
- 間は空行で表現。クライマックス前は空行2つ
- フィクション明示の一文を冒頭か末尾に必ず入れる

---

## 6. youtube-meta.md の書式

```
## タイトル候補（5本）
## 説明文
## タグ
## サムネ文言案
```

- タイトルは感情が動く水準で（基準：「誰にも期待されなかった少年が最後に見せた奇跡」級）
- 説明文の冒頭に「※この物語はフィクションです」を明記
