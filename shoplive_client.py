import requests

from config import SHOPLIVE_ACCESS_KEY, SHOPLIVE_SECRET_KEY, SHOPLIVE_API_BASE


def _headers():
    return {
        "Authorization": SHOPLIVE_SECRET_KEY,
        "accept": "application/json",
    }


def get_campaigns(campaign_status=None, page=1, count=10):
    """キャンペーン一覧を取得する。

    Args:
        campaign_status: "READY", "ONAIR", "ENDED" など。Noneなら全件。
        page: ページ番号
        count: 1ページあたりの件数
    Returns:
        list[dict]: campaignMeta情報のリスト
    """
    url = f"{SHOPLIVE_API_BASE}/{SHOPLIVE_ACCESS_KEY}/campaign"
    params = {"page": page, "count": count}
    if campaign_status:
        params["campaignStatus"] = campaign_status
    resp = requests.get(url, headers=_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()
    # レスポンス: {"results": [{"campaignMeta": {...}, "stream": {...}, ...}], "totalCount": N}
    results = data.get("results", [])
    return [r["campaignMeta"] for r in results]


def get_onair_campaigns():
    """ONAIR中のキャンペーン一覧を取得する。"""
    return get_campaigns(campaign_status="ONAIR")


def get_ready_campaigns():
    """配信予定（READY）のキャンペーン一覧を取得する。"""
    return get_campaigns(campaign_status="READY")


def get_target_campaigns(ready_threshold_minutes=10):
    """在庫チェック対象のキャンペーンを取得する。

    対象:
    - ONAIR中の全キャンペーン
    - READY状態で開始予定が指定分数以内のキャンペーン
    """
    from datetime import datetime, timezone, timedelta

    campaigns = get_onair_campaigns()

    ready = get_ready_campaigns()
    now = datetime.now(timezone.utc)
    threshold = timedelta(minutes=ready_threshold_minutes)

    for c in ready:
        start_at = c.get("scheduledStartAt")
        if not start_at:
            continue
        start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        if start - now <= threshold:
            c["_ready_starting_soon"] = True
            campaigns.append(c)

    return campaigns


def get_campaign_products(campaign_key):
    """キャンペーンに紐づく商品リストを取得する。"""
    url = f"{SHOPLIVE_API_BASE}/{SHOPLIVE_ACCESS_KEY}/campaign/{campaign_key}/product"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def update_stock_status(campaign_key, product_ids, status):
    """キャンペーン内の商品の在庫ステータスを更新する。

    Args:
        campaign_key: キャンペーンキー
        product_ids: Shoplive上の商品IDリスト（int）
        status: "IN_STOCK", "LOW_IN_STOCK", or "SOLD_OUT"
    """
    url = (f"{SHOPLIVE_API_BASE}/{SHOPLIVE_ACCESS_KEY}"
           f"/console/{campaign_key}/product/stockStatus")
    headers = _headers()
    headers["content-type"] = "application/json"
    body = [{"productId": pid} for pid in product_ids]
    resp = requests.put(url, headers=headers, params={"stockStatus": status}, json=body)
    resp.raise_for_status()
    return resp.json() if resp.content else None
