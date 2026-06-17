# 実数化ツール — YouTube Data API で外れ値を確証データ化

管理部（operations）／CEO 決裁により「YouTube Data API で実数化」を採用。
`growth/research/viral-outlier-shorts.csv` の**推定値**を、API の**確定値**に置き換え、
社長の本来の狙い「**登録者が少ないのに高再生**（小チャンネルの跳ね）」を実証する。

成果物:

- `enrich_youtube_stats.py` … CSV を読み、各動画について API を叩き、確定値を付与して
  `viral-outlier-shorts-enriched.csv` を出力する。標準ライブラリのみ（pip 不要）。

---

## 0. セキュリティ（絶対厳守）

- **API キーをコード・CSV・このREADME にハードコードしない／コミットしない。**
- スクリプトは環境変数 `YT_API_KEY` からのみキーを読む。
- キーが未設定なら API を一切叩かず「ドライラン」で安全終了する。
- キーらしき文字列をリポジトリに残さない。漏れた疑いがあれば即ローテーション（Google Cloud で削除→再発行）。

---

## 1. YouTube Data API v3 キーの取得手順（社長の残作業）

1. **Google Cloud Console** にログイン → https://console.cloud.google.com/
2. 上部のプロジェクト選択 → **新しいプロジェクト** を作成（例：`life-timelapse-research`）。
3. 左メニュー **「API とサービス」→「ライブラリ」** を開く。
4. 検索窓に **「YouTube Data API v3」** と入力 → 選択 → **「有効にする」**。
5. **「API とサービス」→「認証情報」** → 上部 **「+ 認証情報を作成」→「API キー」**。
6. 表示されたキー文字列をコピー（これが `YT_API_KEY`）。**画面以外に貼り付けない**。
7. （推奨）作成したキーの **「キーを制限」** から **API の制限 → YouTube Data API v3 のみ** に絞る。
   読み取り専用処理なので IP/HTTP リファラ制限は任意。
8. キーは社長から安全な経路で受領（チャット直貼りは避け、後述のSecret運用が望ましい）。

### 無料クォータと本処理の概算消費

- 無料枠：**1 日 10,000 ユニット**（プロジェクト単位／太平洋時間でリセット）。
- 各エンドポイントの単価（読み取り `list` 系は基本 **1 ユニット/コール**）：
  - `videos.list` … 1
  - `channels.list` … 1
  - `playlistItems.list` … 1
- **本処理の1動画あたり消費**（最悪ケース）：
  - videos.list（確定再生数＋チャンネルID）= 1
  - channels.list（登録者・総再生・uploads）= 1
  - playlistItems.list（直近50本のID）= 1
  - videos.list（その50本の再生数を一括取得）= 1
  - → **約 4 ユニット/動画**
- 同一チャンネルは結果をキャッシュするので、実際はこれ以下。
- **50 本 × 4 ≒ 200 ユニット**。**1 日 10,000 の枠に余裕で収まる**（消費は約 2%）。
  クォータ超過の心配は事実上なし。

---

## 2. 実行手順

```bash
# 1) ドライラン（キー不要・CSVパースとID抽出・列設計だけ検証）
python3 docs/picture-book/operations/tools/enrich_youtube_stats.py

# 2) 本処理（キーを環境変数で渡す。コミット厳禁）
export YT_API_KEY=（社長から受領したキー）
python3 docs/picture-book/operations/tools/enrich_youtube_stats.py
```

- 入力：`growth/research/viral-outlier-shorts.csv`（スクリプトが相対で自動探索）
- 出力：`growth/research/viral-outlier-shorts-enriched.csv`
- 進捗は1行ずつ標準出力に表示。最後に **成功／失敗件数のサマリ**を出す。
- 削除動画・非公開チャンネル・APIエラー・クォータ超過は**握りつぶさず**、その行の
  `取得結果` 列に理由を残して処理を継続する。

---

## 3. 出力の見方（小チャンネルの跳ねをどう読むか）

確定値で追加される主要列：

| 列 | 意味 |
| --- | --- |
| `確定再生数` | API 確定の再生数 |
| `確定登録者数` | API 確定の登録者数（非公開なら「非公開」） |
| `真のチャンネル平均(直近最大50本)` | そのチャンネルの直近最大50本の平均再生数 |
| `外れ値比(チャンネル平均比)` | 確定再生数 ÷ チャンネル平均。**自チャンネル比でどれだけ跳ねたか** |
| `登録者比(再生÷登録)` | 確定再生数 ÷ 登録者数。**登録者の何倍に届いたか** |

**読み方（社長の狙いの実証）**

- `登録者比` が大きい（例：再生数が登録者数の 10倍・100倍）＝
  **登録者が少ないのに大きく外へ届いた**＝アルゴリズムが「登録外の新規視聴者」へ配信した証拠。
  これが社長の言う「小チャンネルの跳ね」の核心指標。
- `外れ値比(チャンネル平均比)` が大きい＝**そのチャンネル内でも突出した1本**＝
  チャンネルの実力ではなく**そのネタ・フックが当たった**ことを示す。
- 両方が高い動画 = 「**小さい主体が、特定のフックで跳ねた**」最有力モデル。
  ここを抽出して、当事業の絵本ショート設計のテンプレに落とす。
- `登録者比` が低い（登録者規模に比例した再生）＝既存ファン主体で、横展開のヒントは薄い。

> 注意：再生数は推定（作者申告）と確定値でズレることがある。確定列を正とし、
> 信頼度列が `確証(API)` の行のみを分析の母集団にする。

---

## 4. 常時運用：Make.com シナリオ設計（後で乗せる用）

PoC は本スクリプトで足りるが、定常監視するなら Make.com で同じ3コールを回す。

**シナリオ骨子**

1. **トリガー**：Notion（または Google Sheets）の「監視リスト」DB を
   Search/Watch で読む。各レコードに動画URL。
2. **Iterator**：レコードをループ。
3. **Tools > Set variable**：URL から正規表現で動画IDを抽出（`/shorts/([\w-]+)`）。
4. **HTTP > Make a request（①）**：
   `GET https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={{videoId}}&key={{YT_API_KEY}}`
   → `viewCount`・`channelId` を取得。キーは Make の**接続／環境変数**に格納（シナリオに直書きしない）。
5. **HTTP（②）**：
   `GET .../channels?part=statistics,contentDetails&id={{channelId}}&key=...`
   → `subscriberCount`・`viewCount`・`videoCount`・`uploads` プレイリストID。
6. **HTTP（③）**：
   `GET .../playlistItems?part=contentDetails&playlistId={{uploads}}&maxResults=50&key=...`
   → 直近50本の動画ID。続けて
   `GET .../videos?part=statistics&id={{カンマ連結ID}}&key=...` で再生数 → 平均を算出。
7. **Tools > Numeric**：`外れ値比 = viewCount / 平均`、`登録者比 = viewCount / subscriberCount`。
8. **書き込み**：
   - **Notion**：監視リストDBの該当ページを Update（確定再生数・登録者数・各比率・取得日時）。
   - **Google Drive**：日次スナップショットを CSV で `picture-book/growth/research/` 配下に追記保存。
9. **スケジュール**：1日1回（消費は数百ユニット規模なのでクォータに余裕）。
10. **エラーハンドラ**：各HTTPに「Resume」付きエラールートを設け、403/quotaExceeded・404 は
    レコードの `取得結果` に理由を書いて継続（本スクリプトと同じ思想）。

---

## 5. キーの渡し方（選択肢）と注意

| 方法 | 用途 | 注意 |
| --- | --- | --- |
| **環境変数 `YT_API_KEY`**（推奨・PoC） | 手元での一括実数化 | シェル履歴に残さない。`export` をスクリプトに書かない |
| **リポジトリの Secret / CI Secret** | 自動実行する場合 | コードからは環境変数として参照。値はログに出さない |
| **Make.com の接続／環境変数** | 常時運用 | シナリオ本体・Blueprint エクスポートに実値を含めない |

**絶対にやらないこと**：キーを `.py` / `.md` / CSV / コミット / スクリーンショット / チャット本文に残す。
疑わしい場合は Google Cloud で当該キーを削除し再発行する。
