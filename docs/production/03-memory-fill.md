# 想い出補完オプション 制作ワークフロー

**作成日**: 2026-05-26
**位置づけ**: オプション機能。**実写が存在しない時期**を AI で想像生成する制作フロー
**前提**: `docs/legal/06-ai-supplement-guideline.md`（生成 OK/NG マトリクス）に準拠

---

## 1. このフェーズの目的

| お客様の声 | 当社の対応 |
| --- | --- |
| 「戦時中の写真が一切ない」 | 当時の年齢相当の姿を AI で想像生成 |
| 「子供の頃の写真は焼失した」 | 学童期の姿を AI で想像生成 |
| 「働き盛りの時期の写真がない」 | 30 代の姿を AI で想像生成 |

**重要**：これは **「想像の表現」**であり、**「事実の再現」ではない**。動画内で必ず実写と区別する演出を加え、お客様事前同意を必須とする。

---

## 2. ツール選定

### メインツール：**Midjourney**（月額 約 1,500 円〜）

#### 採用理由
- 写実的な人物画像の品質が業界トップ
- 「昭和初期」「戦後復興期」等の**時代背景の再現力**が高い
- 同じ Style Code / Style Reference 機能で**一貫した雰囲気**を維持できる
- 商用利用権が明示されている

#### 制限事項
- **特定人物の再現は完全には不可能**（写真からの忠実な再現はできない）
- → **「雰囲気・年齢相当の人物像」**として割り切る

### 補助ツール 1：**IP-Adapter / FLUX**（API 経由）

#### 用途
- 既存写真（前後の年代）から**顔の特徴量を抽出**
- それを参照しながら新シーンを生成
- ある程度の同一人物性を保持

#### 実行方法
- **Replicate API**経由（月 数百〜数千円程度）
- もしくは ComfyUI（OSS）でローカル実行

### 補助ツール 2：**Adobe Firefly**

#### 用途
- 商用利用の安全性が極めて高い（Adobe Stock 学習）
- お客様への安心材料として「Adobe 純正 AI を使用」と明示できる
- 月額：既存 Creative Cloud 契約に含まれる

### 動画化：**Kling AI / Luma**

- 生成した静止画を、AI 中間補間ツールで動かす
- 静止画のままだと「合成感」が強く、動きを与えると馴染む

---

## 3. ワークフロー全体

```
[ご家族ヒアリング：当時の様子を聞き出す]
   ↓
[Midjourney で候補画像生成（3〜5 パターン）]
   ↓
[IP-Adapter で前後写真の顔特徴を反映]
   ↓
[ご家族に候補提示 → 承認]
   ↓
[Kling AI で動きを与える]
   ↓
[編集時に「memory」マーク等の演出を付与]
   ↓
[完成動画に組み込む]
```

---

## 4. ヒアリング項目（補完シーン制作前）

> 詳細なヒアリングシートは `customer/hearing-sheet-production.md` の補完オプション欄を参照

### 必須質問
- 補完したい時期：何歳頃ですか？西暦 / 年号で
- 場所：どこに住んでいましたか？都市部 / 田舎 / 海辺 / 山間部 ?
- 服装：当時の典型的な服装は？（学校制服、和服、洋装、作業着など）
- 髪型：覚えていますか？（写真や似た時期の他の人を参考に）
- 体型・特徴：年代特有の特徴（戦中の痩せ気味、戦後の活発さ等）
- シチュエーション：日常 / 特別な日 / 学校 / 職場 / 家族との場面
- 表情：どんな感じが似合うか（控えめ / 明るく / 真剣 / 笑顔）

### 補助質問
- 同年代の親族・友人で似た雰囲気の方はいますか？（写真ご提供可能なら参考に）
- 当時の写真が残っている方の写真をご家族から借りられますか？（参考用）

---

## 5. Midjourney プロンプト設計

### 5.1 基本テンプレート

```
[年代/時代] [年齢] [性別] [民族性]
in [場所], wearing [服装], [髪型], [表情],
[シーンの雰囲気], photorealistic vintage Japanese family photograph,
[年代特有のフィルム質感], natural lighting, dignified.
```

### 5.2 用途別例

#### 戦中（1940 年代前半）の少年（10 歳）
```
Japanese boy around 10 years old in 1942, wearing simple cotton kimono
or kokumin-fuku school uniform, short cropped hair, calm gentle
expression, rural countryside background with traditional thatched roof
house, photorealistic black and white vintage photograph, film grain,
soft natural lighting, dignified portrait.
```

#### 戦後復興期（1950 年代）の少女（15 歳）
```
Japanese teenage girl around 15 years old in 1955, wearing simple
sailor school uniform, braided hair, modest smile, holding school
books, post-war Japanese town street background, photorealistic
vintage photograph, slight sepia tone, natural daylight, soft focus
on background.
```

#### 高度成長期（1965 年）の青年（25 歳）
```
Japanese young man around 25 years old in 1965, wearing simple white
shirt and dark trousers, neatly combed hair, hopeful expression,
standing in front of newly built apartment building, photorealistic
vintage color photograph, mid-60s film aesthetic, warm afternoon
lighting.
```

### 5.3 Style Reference の活用

複数の補完シーンを作る場合、**Style Reference 機能**で雰囲気を統一：

```
[プロンプト] --sref [前回生成の URL]
```

これにより同じトーンの画像群が作れる。

### 5.4 IP-Adapter での顔特徴反映（高度な手法）

ご家族と一緒に、前後の年代の写真から顔の特徴を抽出して反映：

```
ベース画像：Midjourney 生成画
参照画像：前後の年代の実写写真（同一人物）
強度：0.3〜0.5（強すぎると不自然、弱すぎると別人）
```

→ Replicate API または ComfyUI で実行

---

## 6. ご家族との確認フロー（最重要）

### 段階 1：候補提示（3〜5 パターン）

メールでご家族に画像を送付し、以下のメッセージを添える：

```
〔お客様名〕様

想い出補完シーン（〔○○歳の頃〕）の候補を 4 パターン作成しました。

このシーンは「AI による想像」であり、実際の本人の姿を再現したものではありません。
あくまで「もし当時の写真が残っていたら、こんな雰囲気だったかも」という
表現としてお作りしています。

下記の中から、最も「雰囲気が合う」と感じられるものをお選びください。
複数選択や、すべて却下、修正のリクエストも可能です。

[画像 A] [画像 B] [画像 C] [画像 D]

なお、完成動画では、本シーンに「memory」マークを付け、
セピア調の色味で実写と明確に区別します。

ご感想・ご要望をお聞かせください。
```

### 段階 2：選定後の微調整

ご家族が選んだ候補に対する修正要望（例：「もう少し笑顔がいい」「髪型をもう少し短く」）に応じて、Midjourney で **--vary** または再生成。

### 段階 3：最終承認

選定された静止画について、最終承認をメールで取得：

```
本シーンの内容について、最終承認いただけましたら「OK です」とご返信ください。
ご返信をもって、当該シーンを動画に組み込ませていただきます。
```

### 段階 4：動画化（Kling AI）

承認された静止画を Kling AI に投入し、ゆっくりした動きを与える：

```
プロンプト：
Subtle natural movement, gentle breeze, soft camera push-in,
minimal facial expression change, photorealistic, dignified portrait.

設定：
- Duration：3〜5 秒
- Camera Movement：Slow Push In または Static
- Mode：Pro 推奨（重要シーンのため）
```

---

## 7. 編集時の演出仕様（必須）

`docs/legal/06-ai-supplement-guideline.md` §4 に基づき、以下を必ず適用：

### 7.1 視覚的区別（最低 1 つは必須）

| 演出 | 仕様 |
| --- | --- |
| **「memory」マーク** | 動画右上に小さく「memory」のテキストを 100% 表示時間で表示 |
| **色調変化** | 全体に薄いセピア・水彩風フィルターを適用（彩度 -20%） |
| **ソフトフォーカス** | エッジに薄いソフトフォーカス効果 |
| **フレーム枠** | 古い写真風の枠線を追加 |

### 7.2 字幕

シーン開始時に最低 1 秒間表示：

```
— 想い出補完シーン —
（写真の残っていない時期を想像で描いた映像です）
```

### 7.3 音声

- AI 音声合成は**使用しない**
- ナレーション・BGM のみ
- 必要に応じてご家族の語り（録音）を追加

---

## 8. 失敗時のフォールバック

### 8.1 ご家族が「どれも似ていない」と却下した場合

優先順位順に対応：

1. **追加情報をヒアリング**（写真や記憶の追加情報）
2. **別アプローチで再生成**（プロンプト変更、別ツール）
3. **削減提案**：シーンの数を減らす、または静止画＋字幕で代替
4. **オプション利用中止**：全額返金（プラン本体は予定通り制作）

### 8.2 倫理的に困難と判断した場合

`docs/legal/06-ai-supplement-guideline.md` §2 の NG 項目に該当する場合は、お客様にお断りすることもある：
- 故人の死後の姿を描いてほしい
- 存在しない出来事を描いてほしい
- 第三者を含めて描いてほしい

→ 代替案を提示しつつ、お引き受けできない理由を丁寧に説明。

---

## 9. 同意書取得のタイミング

| タイミング | 対応 |
| --- | --- |
| お問い合わせ時にオプション希望と明言 | 受付時に同意書概要を案内 |
| 写真送付方法案内メール送信時 | 同意書 PDF を添付 |
| 制作開始前 | 署名済み同意書を受領 |
| 候補提示時 | 「これは想像の表現」を再度明示 |
| 最終承認時 | 「動画への組み込み承認」をメールで取得 |

詳細：`docs/legal/05-ai-supplement-consent.md`

---

## 10. 工数・コスト目安

| 項目 | 1 シーンあたり |
| --- | --- |
| ヒアリング | 30 分 |
| Midjourney 生成（候補 5 パターン） | 15 分 |
| IP-Adapter 反映（必要時） | 30 分 |
| ご家族確認・修正 1 往復 | 30 分 + 待ち時間 |
| Kling AI 動画化 | 15 分 |
| 編集（演出・字幕付与） | 15 分 |
| **直接工数合計** | **約 2 時間** |
| 直接費（API 等） | 約 500〜1,000 円 |

→ お客様価格 **+5,000 円/シーン** で粗利 4,000 円程度 + 工数 2 時間
→ 1 案件で 2〜3 シーン入る想定。+ 10,000〜15,000 円の追加売上

---

## 11. 心構え

このオプションは **「お客様の心情に最大限配慮すべき領域」** です。

- 「テクノロジーで何でもできます」という姿勢は NG
- 「お客様と一緒に、想い出を形にする」という共同制作の姿勢
- 完璧を求めず、お客様が「これでいい」と思える着地を最優先
- ご家族間に意見の相違がある場合は、オプション利用を見送る選択肢も提示

→ **「テクノロジーは引き立て役、主役はお客様の人生」**

---

## 12. 関連ドキュメント

- 倫理ガイドライン：`docs/legal/06-ai-supplement-guideline.md`
- AI 補完同意書：`docs/legal/05-ai-supplement-consent.md`
- AI 中間補間：`production/02-ai-bridging.md`
- 編集・字幕：`production/04-editing-and-delivery.md`
- ヒアリングシート：`customer/hearing-sheet-production.md`
