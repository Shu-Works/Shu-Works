# 公式メール セットアップガイド（Cloudflare Email Routing）

> ドメイン取得済みの `sakusaku-kun.com` / `shu-works.co.jp` で
> 公式メアドを開通する。**完全無料**。所要時間：**約20分**。

---

## 0. 目標と完成図

最終的に以下のメアドが動く状態：

| メアド | 用途 | 転送先 |
| --- | --- | --- |
| `info@shu-works.co.jp` | 顧客対応・営業窓口 | CEO の Gmail |
| `support@sakusaku-kun.com` | 技術サポート（モニター後） | CEO の Gmail |
| `noreply@sakusaku-kun.com` | システム自動配信 | 受信専用（無し） |
| `mizuno@shu-works.co.jp` | CEO 個人用 | CEO の Gmail |
| `info@shu-works.co.jp` | コーポレート問い合わせ | CEO の Gmail |

→ 送信時は Gmail から「○○@sakusaku-kun.com を送信元として送る」よう設定。

---

## 1. ドメインを Cloudflare に移管（10分）

### なぜ Cloudflare か
- DNS管理が一元化される
- Email Routing が **完全無料**
- LP デプロイ（Pages）と統合できる
- SSL証明書も自動発行・無料

### 手順

1. https://dash.cloudflare.com/ にアクセス → サインアップ
2. 「サイトを追加」→ `sakusaku-kun.com` を入力
3. 無料プラン（Free）を選択
4. Cloudflare 指定のネームサーバー2つが表示される（例：`xxx.ns.cloudflare.com`）
5. **お名前.com にログイン**
6. ドメイン管理 → `sakusaku-kun.com` → ネームサーバー設定
7. Cloudflare のネームサーバーに変更（反映に最大48時間、通常1〜2時間）
8. **同じ手順で `shu-works.co.jp` も Cloudflare に移管**

→ 反映確認は Cloudflare ダッシュボードで「Active」表示になる。

---

## 2. Cloudflare Email Routing 有効化

DNSが Cloudflare 管理になったら：

1. Cloudflare ダッシュボード → 対象ドメインを選択
2. 左メニュー「Email」→「Email Routing」をクリック
3. 「Enable Email Routing」をクリック
4. Cloudflare が必要な MX レコードを自動で追加
5. 完了

→ これで `*@sakusaku-kun.com` のメールが受け取れる状態になる。

---

## 3. 転送ルール設定

### `info@shu-works.co.jp` を CEO の Gmail へ転送

1. Email Routing → 「Routing rules」タブ
2. 「Create address」をクリック
3. 設定：
   - **Custom address**：`info`
   - **Action**：Send to an email
   - **Destination**：CEO の Gmail アドレス（例：`shu.go.go.flower@gmail.com`）
4. 「Save」

CEO の Gmail に Cloudflare から確認メールが届く → 「Verify」をクリック → 確定。

### 同様に他のメアドも作る

| ローカル部 | 転送先 |
| --- | --- |
| `info` | CEO の Gmail |
| `support` | CEO の Gmail |
| `noreply` | （送信専用のため作らない、別途SMTP設定で対応） |

### `shu-works.co.jp` でも同じ手順

| ローカル部 | 転送先 |
| --- | --- |
| `info` | CEO の Gmail |
| `mizuno` | CEO の Gmail |

---

## 4. Gmail から「info@shu-works.co.jp 送信元」で送る設定

転送だけでは、返信時に「○○@gmail.com」から返信してしまう。
ちゃんと「info@shu-works.co.jp」から返信できるよう設定する。

### 必要な SMTP プロバイダ（無料）

Cloudflare Email Routing は **送信機能がない**。送信は別のSMTPサーバを使う：

| サービス | 無料枠 | 推奨度 |
| --- | --- | --- |
| **Brevo（旧Sendinblue）** | 300通/日まで無料 | ⭐ 推奨 |
| **Resend** | 月100通まで無料、3000通$0、それ以降従量 | サブ推奨 |
| **Postmark** | 100通/月まで無料 | ⭕ |
| **SendGrid** | 月100通/日まで無料 | ⭕ |

### Brevo で SMTP 設定

1. https://www.brevo.com/ → サインアップ
2. ダッシュボード → SMTP & API → SMTP
3. 「smtp-relay.brevo.com:587」のホスト名、ユーザー名、API キーが表示される
4. これを Gmail に登録：

### Gmail の設定

1. Gmail の右上の歯車 → すべての設定を表示 → アカウントとインポート
2. 「他のメールアドレスを追加」→ 「mizuno@shu-works.co.jp」を入力（または info@...）
3. 「次のステップ」
4. SMTP サーバー設定：
   - SMTP サーバー：`smtp-relay.brevo.com`
   - ポート：587
   - ユーザー名：Brevo から取得した SMTP ユーザー名
   - パスワード：Brevo から取得した API キー
   - TLS を使用
5. 「アカウントを追加」
6. 認証メールが「info@shu-works.co.jp」に届く → 自分の Gmail に転送されてくる → 認証コードを入力
7. 完了

→ これで Gmail から「info@shu-works.co.jp」発信元でメールを送れるようになる。

---

## 5. 配信信頼性（SPF / DKIM / DMARC）

スパムフォルダ行きを防ぐため必須：

### SPF レコード
Cloudflare DNS で TXT レコードを追加：
```
Name: @
Type: TXT
Content: v=spf1 include:spf.brevo.com ~all
```

### DKIM レコード
Brevo が指定する CNAME を Cloudflare DNS に追加（Brevo 管理画面で詳細表示）

### DMARC レコード
```
Name: _dmarc
Type: TXT
Content: v=DMARC1; p=quarantine; rua=mailto:info@shu-works.co.jp
```

→ これで Gmail / Outlook で正常に受信される率が **95%以上**になる。

---

## 6. メール署名テンプレ

Gmail で署名を設定：

```
━━━━━━━━━━━━━━━━━━━
水野 秀彦
Shu Works（2026年7月中に株式会社化予定）

🤖 サク索くん｜LINEで業務を爆速化する業種特化AIシリーズ
　https://sakusaku-kun.com
　https://shu-works.co.jp

📧 info@shu-works.co.jp
📱 [電話番号]
━━━━━━━━━━━━━━━━━━━
```

---

## 7. 完了チェックリスト

CEOがやること：
- [ ] sakusaku-kun.com を Cloudflare に移管
- [ ] shu-works.co.jp を Cloudflare に移管
- [ ] Cloudflare Email Routing を両ドメインで有効化
- [ ] `info@shu-works.co.jp` を CEO の Gmail に転送設定
- [ ] `mizuno@shu-works.co.jp` を CEO の Gmail に転送設定
- [ ] Brevo にサインアップ・SMTP キー取得
- [ ] Gmail に SMTP 設定（送信元を info@... に）
- [ ] SPF / DKIM / DMARC を Cloudflare DNS に追加
- [ ] テストメール送受信（自分宛て）
- [ ] メール署名を Gmail に登録

---

## 8. テスト方法

### 受信テスト
別の Gmail から `info@shu-works.co.jp` に送信。
→ CEO の Gmail で受信できれば成功。

### 送信テスト
Gmail で「info@shu-works.co.jp 送信元」を選んで、自分の別アドレスに送信。
→ 相手側で「info@shu-works.co.jp から届いた」と表示されれば成功。

### スパム判定テスト
https://www.mail-tester.com にアクセス → 表示されたアドレスにテスト送信
→ スコア 8/10 以上なら本番OK

---

## 9. 完了後にCEOから俺に教えてほしいこと

- 開通したメアド全部のリスト
- スパムスコア（mail-tester.com の結果）

これで契約書テンプレ・LP・DM スクリプトの連絡先を全部正式版に固定する。
