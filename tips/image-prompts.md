# 画像生成プロンプト集（オリジナル・ペンギン役員5匹）

> 目的：著作権セーフで視認性の高いマスコットを作る。特定作品の衣装・髪型・固有マークは一切使わない。
> 使い方：画像生成AI（英語プロンプト推奨）に貼る。**文字はAIに描かせず、生成後にCanva等で乗せる**（AIの日本語文字は崩れるため）。
> 全キャラで「スタイル共通文」を使うと画風が揃う。

---

## ★ スタイル共通文（全プロンプトの先頭に付ける）
```
chibi kawaii mascot illustration, a round chubby penguin character, big expressive sparkly eyes, small orange beak, soft cel-shading, clean thick outlines, bright cheerful anime style, simple pastel gradient background, sticker-like, centered, high contrast, professional thumbnail quality
```

## ★ ネガティブプロンプト（共通・末尾に付ける）
```
realistic, photo, 3d, garbled text, watermark, extra limbs, deformed, blurry, low quality,
sword, katana, weapon, blindfold over eyes, checkered haori, green military cloak with emblem,
flame patterns, scar on face, hanafuda earrings, any recognizable anime character
```

---

## 1. CEO ペンギン（指揮官タイプ）
```
[スタイル共通文],
a confident leader penguin CEO, wearing a navy double-breasted commander coat with gold buttons and epaulettes, a solid deep-crimson cape flowing behind, standing tall with one flipper pointing forward in a commanding pose, sharp determined eyes, slight confident smile, a tiny golden crown badge
[ネガティブプロンプト]
```
**狙い**：一目で「リーダー」。色＝紺×金×臙脂。

## 2. 接客ペンギン（共感タイプ）
```
[スタイル共通文],
a warm friendly customer-support penguin, wearing a soft cream apron and a light headset microphone, holding a steaming cup of tea with both flippers, gentle caring smile, kind round eyes, cozy warm orange and beige palette, welcoming gesture
[ネガティブプロンプト]
```
**狙い**：一目で「優しい接客」。色＝暖色（オレンジ×クリーム）。

## 3. 制作ペンギン（完璧主義タイプ）
```
[スタイル共通文],
a focused craftsman penguin, wearing dark work overalls and a tool belt, safety goggles pushed up on the forehead, holding a wrench and a paintbrush, serious perfectionist frown, intense eyes inspecting closely, industrial grey and brown palette
[ネガティブプロンプト]
```
**狙い**：一目で「職人・品質番人」。色＝グレー×ブラウン。

## 4. 営業ペンギン（カリスマタイプ）
```
[スタイル共通文],
a charismatic salesman penguin, wearing a flashy bright-white suit with a colorful tie, stylish modern sunglasses (clear lens, not covering eyes), big confident grin, doing a finger-gun pose, sparkles and shine around, vivid bright palette, star effects
[ネガティブプロンプト]
```
**狙い**：一目で「目立つ営業」。色＝白×ゴールド＋キラキラ。
※サングラスは「普通の細いサングラス」。目隠し風にしない。

## 5. 管理ペンギン（几帳面タイプ）
```
[スタイル共通文],
a meticulous accountant penguin, wearing a plain dark-navy business suit with a neat tie and rectangular glasses, holding a calculator and a ledger book, calm precise expression, slightly tired but reliable look, muted navy and grey palette
[ネガティブプロンプト]
```
**狙い**：一目で「きっちり経理」。色＝紺×グレー。メガネは四角（丸サングラスにしない）。

---

## 6. サムネ用・5匹集合（横並び）
```
[スタイル共通文],
five distinct chibi penguin executives standing together in a row:
(1) a leader penguin in a navy commander coat with crimson cape pointing forward,
(2) a friendly penguin in a cream apron with a headset holding tea,
(3) a craftsman penguin in work overalls with a tool belt and goggles,
(4) a flashy salesman penguin in a white suit with sunglasses doing a finger-gun,
(5) an accountant penguin in a dark suit with glasses holding a calculator,
in front of a bright modern office building, a rising success arrow and a glowing light-bulb idea icon, sparkles, optimistic sunny atmosphere, wide composition, leave empty space at the top for a title
[ネガティブプロンプト]
```
**後処理**：生成後にCanva等で上部に「**この5匹で会社を作りました／設立のやり方を紹介します**」を乗せる（フォントは太ゴシック、青＋赤の差し色）。

---

## 運用メモ
- まず「6. サムネ」を数枚生成 → 一番いいものを選ぶ
- 個別1〜5は Instagram の「配役紹介カルーセル（IG-2）」に使う
- 画風がブレたら、気に入った1枚を参照画像にして残りを生成（i2i / スタイル参照）
- このマスコットは**ブランド資産**。気に入った5匹を“定番”として固定し、毎回使い回す
