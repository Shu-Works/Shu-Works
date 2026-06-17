# 自動化アーキテクチャ — AI 感動絵本チャンネル

**作成日**: 2026-06-17
**ブランチ**: claude/ai-picture-book-automation-78ua1m
**目的**: エピソード1本を「ネタ→YouTube投稿」まで、社長の確認を最後だけにして流す自動化パイプラインの設計
**前提ツール（接続済み MCP）**: Make.com / Notion / Google Drive / Gmail / Google Calendar / Canva
**実行範囲**: 本ドキュメントは設計のみ。実シナリオ作成・外部送信は **CEO 承認後**。

> 設計原則（CLAUDE.md）
> - §6 シンプル：承認ゲートは **2 点のみ**。それ以外は全自動。
> - §22 Real Artists Ship：80% で回し、データで磨く。
> - §VIII Cash is oxygen / 粗利率 80% 維持：1 本あたり社長工数を分単位で管理。

---

## 1. 役割分担（真実源の固定）

| ツール | 役割 | これ以外には使わない |
| --- | --- | --- |
| **Notion** | 進行管理の**唯一の真実源**。全ステータス・承認フラグ・実績数値はここ | アセット本体は置かない（リンクのみ） |
| **Google Drive** | アセット保管（脚本 / 画像10枚 / 音声 / 完成動画 / サムネ）。話数ごとフォルダ | 進行ステータスは持たせない |
| **Gmail** | 社長への承認依頼ドラフト送信（ゲートA / B の2通） | 自動「送信」はしない。下書き生成まで（承認は人間） |
| **Google Calendar** | 投稿枠の予約。1日1〜3本のスロット管理 | — |
| **Canva** | スライド組版・サムネ生成・デザイン書き出し（動画化の代替手段） | — |
| **Make.com** | 上記を繋ぐオーケストレーター。トリガー＝Notionステータス変化 | ロジックの真実源にはしない（あくまで実行） |

設計の肝：**人間もAIも「Notionのステータスを見て・書く」だけ**。Make はステータス遷移を検知して次工程を起動する。状態を二重に持たない。

---

## 2. パイプライン全体図（テキスト）

凡例：`🟢自動` = AI/ツールが無人実行 ／ `🔴承認ゲート` = 社長の人手が必須

```
[ネタ決め]
  🟢 Make定期実行 → ChatGPTでテーマ候補生成 → Notionに新規エピソード行を起票
        │  Notion status: 「ネタ確定」
        ▼
[脚本生成]
  🟢 ChatGPT：10シーン・約1000字の脚本 → DriveにテキストとしてMD保存
        │  Notion status: 「脚本生成済」／脚本リンク記入
        ▼
[画像プロンプト生成]
  🟢 ChatGPT：10シーン分の画像プロンプト → Driveに保存
        │  Notion status: 「プロンプト済」
        ▼
┌──────────────── 🔴 承認ゲートA：物語＆タイトル GO ────────────────┐
│  🟢 Make → Gmailに「承認依頼A」ドラフト生成（タイトル候補＋あらすじ＋10シーン要約）│
│  🔴 社長が返信1語：「A-GO」/「A-NG（理由）」                       │
│  🟢 Make → Gmail受信をトリガーに Notion status 更新                 │
│      GO  → 「物語承認済」へ（画像生成へ進む）                       │
│      NG  → 「脚本生成済」へ差し戻し（脚本を再生成）                 │
└─────────────────────────────────────────────────────────────────────┘
        │  status:「物語承認済」
        ▼
[画像生成 ×10]
  🟢 Google Flow で画像10枚生成 → Driveの話数フォルダ /images へ
        │  Notion 画像ステータス:「生成済」
        ▼
[ナレーション音声]
  🟢 AI音声（TTS）：脚本テキスト → 音声ファイル → Drive /audio へ
        │  Notion 音声:「生成済」
        ▼
[動画化（スライド）]
  🟢 Canva で静止画10枚＋字幕＋BGMをスライド組版 → 2〜3分動画 → Drive /video へ
     （※Canva書き出し or 外部レンダラ。サムネもCanvaで同時生成）
        │  Notion 動画:「生成済」／サムネ:「生成済」
        ▼
┌──────────── 🔴 承認ゲートB：完成動画＆投稿 GO ────────────┐
│  🟢 Make → Gmailに「承認依頼B」ドラフト生成                  │
│     （完成動画リンク＋サムネ＋タイトル＋説明文＋投稿予定枠）  │
│  🔴 社長が返信1語：「B-GO」/「B-NG（理由）」                 │
│  🟢 Make → 返信をトリガーに分岐                              │
│     GO  → Calendar の投稿枠を確定 → YouTube投稿実行          │
│     NG  → 「動画生成済」へ差し戻し（該当工程を再生成）       │
└──────────────────────────────────────────────────────────────┘
        │  status:「投稿予約済」→（投稿枠到来）→「投稿済」
        ▼
[投稿後トラッキング]
  🟢 Make定期実行：投稿24h/7d後の再生数をYouTubeから取得 → Notionに記入
        │  status:「公開中」
        ▼
[分析]
  🟢 30本到達時：Make → 再生数Topビュー抽出 → ChatGPTで共通点分析 → Notionに分析メモ
```

承認ゲートは **A と B の 2 点のみ**。間の全工程（脚本・プロンプト・画像・音声・動画化・投稿・計測）は無人。

---

## 3. Make.com シナリオ構成案（実装粒度の擬似ステップ）

Make は「1本の巨大シナリオ」にせず、**ステータス駆動の小シナリオに分割**する（§6 シンプル・障害切り分け容易）。各シナリオのトリガーは Notion のステータス値。

### シナリオ S0：ネタ供給（スケジュール起動）
```
1. [Schedule] 毎日 06:00 起動
2. [Tool/ChatGPT] テーマ候補を N 件生成（既存タイトルと重複回避：S0でNotion検索して除外）
3. [Notion > Search Objects] 既存「タイトル候補」を取得し重複チェック
4. [Router] 未使用テーマのみ通す
5. [Notion > Create a Database Item] エピソード行を作成（status=「ネタ確定」, 話数=自動採番）
```

### シナリオ S1：脚本→プロンプト（status=「ネタ確定」で起動）
```
1. [Notion > Watch Database Items] status「ネタ確定」を検知
2. [ChatGPT] 10シーン・約1000字の脚本を生成
3. [Google Drive > Create a Folder] /絵本/第{話数}話/ を作成（images/audio/video サブフォルダも）
4. [Google Drive > Upload a File] script.md を保存
5. [ChatGPT] 10シーン分の画像プロンプトを生成
6. [Google Drive > Upload a File] prompts.md を保存
7. [Notion > Update a Database Item] status=「プロンプト済」, 脚本リンク・プロンプトリンク記入
```

### シナリオ S2：承認依頼A 生成（status=「プロンプト済」で起動）
```
1. [Notion > Watch Database Items] status「プロンプト済」
2. [Text Aggregator] タイトル候補＋あらすじ＋10シーン要約を整形
3. [Gmail > Create a Draft] 承認依頼Aドラフトを作成（宛先=社長, 件名に話数とトークン[EP-XX][GATE-A]）
4. [Notion > Update a Database Item] status=「承認A待ち」, 承認依頼送信日時を記録
```

### シナリオ S3：承認A 返信処理（Gmail受信で起動）
```
1. [Gmail > Watch Emails] 件名に [GATE-A] を含む社長からの返信を検知
2. [Router/Text parser] 本文1語を解釈：「A-GO」/「A-NG」
3a.[GO]  [Notion > Update] status=「物語承認済」
3b.[NG]  [Notion > Update] status=「ネタ確定」へ差し戻し（理由をメモ列に格納→S1が再走）
```

### シナリオ S4：画像→音声→動画（status=「物語承認済」で起動）
```
1. [Notion > Watch] status「物語承認済」
2. [Google Flow] prompts.md を元に画像10枚生成 → Drive /images（Make非対応時はHTTP/予約モジュールで連携）
3. [Notion > Update] 画像ステータス=「生成済」
4. [TTS] script.md からナレーション音声生成 → Drive /audio
5. [Notion > Update] 音声=「生成済」
6. [Canva > Create Design / Export] 画像＋字幕＋BGMでスライド動画＆サムネ → Drive /video
7. [Notion > Update] 動画=「生成済」, サムネ=「生成済」, status=「動画生成済」
```

### シナリオ S5：承認依頼B 生成（status=「動画生成済」で起動）
```
1. [Notion > Watch] status「動画生成済」
2. [Google Calendar > Search/Suggest] 次の空き投稿枠を取得（1日最大3枠）
3. [Gmail > Create a Draft] 承認依頼Bドラフト（動画リンク・サムネ・タイトル・説明文・投稿予定枠, 件名[EP-XX][GATE-B]）
4. [Notion > Update] status=「承認B待ち」, 投稿予定枠を仮押さえ列に記入
```

### シナリオ S6：承認B 返信処理＆投稿（Gmail受信で起動）
```
1. [Gmail > Watch Emails] 件名に [GATE-B] を含む返信
2. [Router] 「B-GO」/「B-NG」
3a.[GO]  [Google Calendar > Create Event] 投稿枠を確定
         [YouTube > Upload Video] 動画投稿（タイトル/説明/タグ/サムネ）
         [Notion > Update] status=「投稿済」, YouTube URL 記入
3b.[NG]  [Notion > Update] status=「物語承認済」or該当前工程へ差し戻し（理由メモ）
```

### シナリオ S7：実績トラッキング（スケジュール起動）
```
1. [Schedule] 毎日 22:00
2. [Notion > Search] status「投稿済」かつ投稿後24h/7d経過の行を抽出
3. [YouTube > Get Video Analytics] 再生数・視聴維持率・登録増を取得
4. [Notion > Update] 再生数24h / 再生数7d / 維持率 列を更新, status=「公開中」
```

### シナリオ S8：上位分析（30本到達でトリガー or 週次）
```
1. [Schedule] 週次 or [Notion] 投稿済件数 >= 30 を検知
2. [Notion > Search] 再生数7d 降順 Top5 を抽出
3. [ChatGPT] Top5のテーマ/タイトル語/サムネ傾向の共通点を分析
4. [Notion > Create/Update] 「分析メモ」ページに所見を記録（次のS0テーマ生成へフィードバック）
```

---

## 4. 障害・例外設計（無人運転の安全装置）

- **各シナリオに Error handler**：失敗時は Notion の該当行 status を「要対応」にし、Gmail で管理部長宛アラート下書き。無人で詰まったまま放置しない。
- **冪等性**：Make は同一行を二重処理しないよう、status を「処理中」に一旦倒してから次工程へ。
- **承認ゲートのタイムアウト**：「承認A/B待ち」が48hを超えたら Make が社長へリマインド下書き（SLA監視、管理部の責務）。
- **Drive リンクのみ Notion 記載**：個人情報・著作物の本体は Notion に置かない（既存運用ルール準拠）。
- **コスト上限**：1本の直接費（AI API/画像/音声/レンダリング）を Notion に記録。粗利率80%を割る兆候が出たら Jobs にエスカレーション。

---

## 5. 社長の手作業（最終工数）

無人化されない人手は **承認ゲートA・Bの2回の判断＋1語返信のみ**。
1本あたりの社長実働見積り：**約3〜5分（判断2〜3分＋メール返信1語×2）**。
（差し戻しが発生した本のみ追加で数分。定常運転では1本5分以内に収まる設計。）
