#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enrich_youtube_stats.py
=======================
viral-outlier-shorts.csv の「推定値」を、YouTube Data API v3 の「確定値」に
上書き／付与するための実数化ツール（管理部 / operations）。

目的（社長の本来の狙い）:
    「登録者が少ないのに高再生」= 小チャンネルの跳ね を確証データで実証する。

このスクリプトがやること（1動画あたり最大3コール）:
    1) videos.list?part=statistics,snippet&id=ID
         -> 確定再生数(viewCount) + チャンネルID(channelId)
    2) channels.list?part=statistics,contentDetails&id=CHANNEL_ID
         -> 登録者数(subscriberCount) + チャンネル総再生数 + 総動画数
            + uploads プレイリストID
    3) playlistItems.list (uploads) -> 直近最大50本の動画ID
       videos.list (statistics) でその再生数を取得
         -> 「真のチャンネル平均再生数」(直近最大50本の平均)
    外れ値比          = 確定再生数 ÷ 真のチャンネル平均
    登録者比(再生÷登録) = 確定再生数 ÷ 登録者数   ← 小チャンネルの跳ねを見る主指標
    チャンネル平均比   = 外れ値比と同義（直近平均に対する跳ね）

セキュリティ:
    - API キーは環境変数 YT_API_KEY からのみ読む。コード・出力・README に実キーを書かない。
    - キーが未設定なら「ドライラン」（API を一切叩かず、CSV パースと列設計のみ確認）で安全終了。

使い方:
    # ドライラン（キー不要・列設計とID抽出だけ確認）
    python3 enrich_youtube_stats.py

    # 本処理（キーを環境変数で渡す。コミット厳禁）
    export YT_API_KEY=あなたのAPIキー
    python3 enrich_youtube_stats.py

入力 : viral-outlier-shorts.csv            （同じ growth/research 配下を自動探索）
出力 : viral-outlier-shorts-enriched.csv   （入力と同じディレクトリ）
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# パス解決：このスクリプトの位置から相対でリポジトリ内の CSV を探す
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
# tools/ -> operations/ -> picture-book/ -> growth/research/...
REPO_PB = os.path.abspath(os.path.join(HERE, "..", ".."))
INPUT_CSV = os.path.join(REPO_PB, "growth", "research", "viral-outlier-shorts.csv")
OUTPUT_CSV = os.path.join(REPO_PB, "growth", "research", "viral-outlier-shorts-enriched.csv")

API_BASE = "https://www.googleapis.com/youtube/v3"
RECENT_SAMPLE_MAX = 50  # 真のチャンネル平均を取る直近本数

# 出力で追加／上書きする列
ENRICH_COLUMNS = [
    "確定再生数",
    "確定登録者数",
    "確定チャンネル名",
    "真のチャンネル平均(直近最大50本)",
    "外れ値比(チャンネル平均比)",
    "登録者比(再生÷登録)",
    "チャンネル総再生数",
    "チャンネル総動画数",
    "確定データ信頼度",
    "API取得日時(UTC)",
    "取得結果",  # OK / エラー理由
]


# ---------------------------------------------------------------------------
# 動画ID抽出
# ---------------------------------------------------------------------------
def extract_video_id(url):
    """YouTube の URL から動画IDを取り出す。YouTube以外は None。"""
    if not url:
        return None
    url = url.strip()
    # /shorts/VIDEOID
    m = re.search(r"/shorts/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    # watch?v=VIDEOID
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    # youtu.be/VIDEOID
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    return None  # Facebook 等は対象外


# ---------------------------------------------------------------------------
# API 呼び出し（クォータ超過・404 等を握りつぶさず例外で返す）
# ---------------------------------------------------------------------------
class QuotaExceeded(Exception):
    pass


class ApiError(Exception):
    pass


def api_get(endpoint, params, api_key):
    params = dict(params)
    params["key"] = api_key
    qs = urllib.parse.urlencode(params)
    url = "{}/{}?{}".format(API_BASE, endpoint, qs)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        # クォータ超過は 403 + quotaExceeded
        if e.code == 403 and "quotaExceeded" in body:
            raise QuotaExceeded("クォータ超過(1日10,000ユニット超過)")
        if e.code == 403 and "keyInvalid" in body:
            raise ApiError("APIキー無効(keyInvalid)")
        raise ApiError("HTTP {}: {}".format(e.code, _short_reason(body)))
    except urllib.error.URLError as e:
        raise ApiError("ネットワークエラー: {}".format(e.reason))


def _short_reason(body):
    try:
        data = json.loads(body)
        errs = data.get("error", {}).get("errors", [])
        if errs:
            return errs[0].get("reason", "") or errs[0].get("message", "")
        return data.get("error", {}).get("message", "")[:120]
    except Exception:
        return body[:120]


# ---------------------------------------------------------------------------
# 1動画ぶんのエンリッチ
# ---------------------------------------------------------------------------
def enrich_one(video_id, api_key, cache):
    """戻り値: (dict 充填値, 結果文字列)。例外はここで握って結果文字列に残す。"""
    out = {col: "" for col in ENRICH_COLUMNS}
    out["確定データ信頼度"] = "確証(API)"
    out["API取得日時(UTC)"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- 1) videos.list (statistics, snippet) ---
    v = api_get("videos", {"part": "statistics,snippet", "id": video_id}, api_key)
    items = v.get("items", [])
    if not items:
        return out, "動画が見つからない(削除/非公開/ID誤り)"
    vstat = items[0].get("statistics", {})
    vsnip = items[0].get("snippet", {})
    view_count = _to_int(vstat.get("viewCount"))
    channel_id = vsnip.get("channelId", "")
    out["確定再生数"] = view_count if view_count is not None else ""
    out["確定チャンネル名"] = vsnip.get("channelTitle", "")
    if not channel_id:
        return out, "チャンネルID取得不可"

    # --- 2) channels.list (statistics, contentDetails) ---
    if channel_id in cache:
        ch = cache[channel_id]
    else:
        ch_resp = api_get(
            "channels",
            {"part": "statistics,contentDetails", "id": channel_id},
            api_key,
        )
        ch_items = ch_resp.get("items", [])
        if not ch_items:
            return out, "チャンネルが見つからない(非公開/削除)"
        ch = ch_items[0]
        cache[channel_id] = ch

    cstat = ch.get("statistics", {})
    sub_hidden = cstat.get("hiddenSubscriberCount", False)
    sub_count = None if sub_hidden else _to_int(cstat.get("subscriberCount"))
    out["確定登録者数"] = "非公開" if sub_hidden else (sub_count if sub_count is not None else "")
    out["チャンネル総再生数"] = _to_int(cstat.get("viewCount")) or ""
    out["チャンネル総動画数"] = _to_int(cstat.get("videoCount")) or ""

    uploads = (
        ch.get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )

    # --- 3) 真のチャンネル平均（直近最大50本） ---
    true_avg = None
    if uploads:
        avg_key = "avg::" + uploads
        if avg_key in cache:
            true_avg = cache[avg_key]
        else:
            try:
                true_avg = channel_recent_average(uploads, api_key)
                cache[avg_key] = true_avg
            except (QuotaExceeded,):
                raise
            except ApiError as e:
                # 平均が取れなくても他の値は残す
                out["真のチャンネル平均(直近最大50本)"] = "取得失敗:{}".format(e)
    if true_avg is not None:
        out["真のチャンネル平均(直近最大50本)"] = true_avg

    # --- 指標計算 ---
    if isinstance(view_count, int):
        if isinstance(true_avg, int) and true_avg > 0:
            out["外れ値比(チャンネル平均比)"] = round(view_count / true_avg, 2)
        if isinstance(sub_count, int) and sub_count > 0:
            out["登録者比(再生÷登録)"] = round(view_count / sub_count, 2)

    return out, "OK"


def channel_recent_average(uploads_playlist_id, api_key):
    """uploads プレイリストの直近最大50本の平均再生数（int）を返す。"""
    # 直近50本の動画IDを取得
    pl = api_get(
        "playlistItems",
        {
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": RECENT_SAMPLE_MAX,
        },
        api_key,
    )
    vids = [
        it.get("contentDetails", {}).get("videoId")
        for it in pl.get("items", [])
        if it.get("contentDetails", {}).get("videoId")
    ]
    if not vids:
        return None
    # videos.list は最大50件まとめて引ける（1コール）
    vresp = api_get(
        "videos", {"part": "statistics", "id": ",".join(vids[:50])}, api_key
    )
    views = []
    for it in vresp.get("items", []):
        vc = _to_int(it.get("statistics", {}).get("viewCount"))
        if vc is not None:
            views.append(vc)
    if not views:
        return None
    return int(round(sum(views) / len(views)))


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
def main():
    if not os.path.exists(INPUT_CSV):
        print("[ERROR] 入力CSVが見つからない: {}".format(INPUT_CSV))
        sys.exit(1)

    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        in_fields = reader.fieldnames or []
        rows = list(reader)

    # URL 列名を特定
    url_col = next((c for c in in_fields if "URL" in c and "出典" not in c), None)
    if url_col is None:
        url_col = "動画URL"

    # 各行に動画IDを付与
    yt_count = 0
    non_yt = 0
    for r in rows:
        vid = extract_video_id(r.get(url_col, ""))
        r["_video_id"] = vid or ""
        if vid:
            yt_count += 1
        else:
            non_yt += 1

    api_key = os.environ.get("YT_API_KEY", "").strip()

    print("=" * 64)
    print("enrich_youtube_stats.py")
    print("入力 : {}".format(INPUT_CSV))
    print("対象行: {} 行 / YouTube動画ID抽出成功: {} 件 / 対象外(FB等): {} 件".format(
        len(rows), yt_count, non_yt))
    print("追加列: {}".format(", ".join(ENRICH_COLUMNS)))
    print("=" * 64)

    if not api_key:
        print("\n[ドライラン] 環境変数 YT_API_KEY が未設定のため、APIは呼びません。")
        print("CSVパースと動画ID抽出・列設計のみ検証しました。問題なし。")
        print("本処理は次で実行:")
        print("    export YT_API_KEY=あなたのAPIキー")
        print("    python3 {}".format(os.path.basename(__file__)))
        # ドライランでも、抽出できたIDの内訳を数件だけ表示（キーは一切出さない）
        sample = [r["_video_id"] for r in rows if r["_video_id"]][:5]
        print("    抽出ID例(先頭5件): {}".format(", ".join(sample)))
        sys.exit(0)

    # ---- 本処理 ----
    out_fields = list(in_fields) + [c for c in ENRICH_COLUMNS if c not in in_fields]
    cache = {}
    ok = 0
    fail = 0
    skipped = 0
    quota_hit = False

    for idx, r in enumerate(rows, start=1):
        vid = r["_video_id"]
        title = (r.get("動画タイトル") or "")[:24]
        if not vid:
            for col in ENRICH_COLUMNS:
                r[col] = ""
            r["取得結果"] = "対象外(YouTube以外のURL)"
            r["確定データ信頼度"] = ""
            skipped += 1
            print("  [{:2}/{}] skip  {} … {}".format(idx, len(rows), vid or "------", "対象外URL"))
            continue

        if quota_hit:
            for col in ENRICH_COLUMNS:
                r[col] = ""
            r["取得結果"] = "未処理(クォータ超過で中断)"
            fail += 1
            continue

        try:
            enriched, result = enrich_one(vid, api_key, cache)
            for col in ENRICH_COLUMNS:
                r[col] = enriched.get(col, "")
            r["取得結果"] = result
            if result == "OK":
                ok += 1
            else:
                fail += 1
            print("  [{:2}/{}] {:5} {} … 再生={} 登録={} 平均比={} 登録比={}".format(
                idx, len(rows),
                "OK" if result == "OK" else "NG",
                vid,
                enriched.get("確定再生数", ""),
                enriched.get("確定登録者数", ""),
                enriched.get("外れ値比(チャンネル平均比)", ""),
                enriched.get("登録者比(再生÷登録)", ""),
            ))
        except QuotaExceeded:
            quota_hit = True
            for col in ENRICH_COLUMNS:
                r[col] = ""
            r["取得結果"] = "クォータ超過で中断(翌日再実行)"
            fail += 1
            print("  [{:2}/{}] QUOTA クォータ超過。以降は中断します。".format(idx, len(rows)))
        except ApiError as e:
            for col in ENRICH_COLUMNS:
                r[col] = ""
            r["取得結果"] = "APIエラー:{}".format(e)
            fail += 1
            print("  [{:2}/{}] NG    {} … {}".format(idx, len(rows), vid, e))

        time.sleep(0.05)  # 軽いレート緩和

    # 出力（内部用 _video_id は落とす）
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print("=" * 64)
    print("出力 : {}".format(OUTPUT_CSV))
    print("サマリ: 成功 {} 件 / 失敗・対象外 {} 件（うち対象外URL {} 件）{}".format(
        ok, fail + skipped, skipped,
        " ※クォータ超過で途中中断" if quota_hit else ""))
    print("=" * 64)


if __name__ == "__main__":
    main()
