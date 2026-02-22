import base64
import time

import jwt
import requests

from config import SHOPLIVE_ACCESS_KEY, SHOPLIVE_SECRET_KEY, SHOPLIVE_API_BASE


def _generate_token():
    """Shoplive API用のJWTトークンを生成する。"""
    secret = base64.b64decode(SHOPLIVE_SECRET_KEY)
    payload = {
        "accessKey": SHOPLIVE_ACCESS_KEY,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _headers():
    return {
        "Authorization": _generate_token(),
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


def get_campaign_products(campaign_key):
    """キャンペーンに紐づく商品リストを取得する。"""
    url = f"{SHOPLIVE_API_BASE}/{SHOPLIVE_ACCESS_KEY}/console/{campaign_key}/product"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def update_stock_status(campaign_key, product_ids, status):
    """商品の在庫ステータスを更新する。

    Args:
        campaign_key: キャンペーンキー
        product_ids: Shoplive上の商品IDリスト
        status: "IN_STOCK", "LOW_IN_STOCK", or "SOLD_OUT"
    """
    url = f"{SHOPLIVE_API_BASE}/{SHOPLIVE_ACCESS_KEY}/console/{campaign_key}/product/stockStatus"
    body = {
        "productIds": product_ids,
        "stockStatus": status,
    }
    resp = requests.put(url, headers=_headers(), json=body)
    resp.raise_for_status()
    return resp.json() if resp.content else None
