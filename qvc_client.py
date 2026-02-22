import re
import logging

import requests

logger = logging.getLogger(__name__)

QVC_API_BASE = "https://qvc.jp/api/sales/presentation/v3/jp/products"


def extract_product_id(url):
    """QVC商品URLからプロダクトIDを抽出する。

    例: https://qvc.jp/product.748849.html → 748849
    """
    match = re.search(r"product\.(\d+)\.html", url)
    if match:
        return match.group(1)
    # URLパスの末尾が数字のパターンにも対応
    match = re.search(r"/(\d{5,7})(?:\?|$|/)", url)
    if match:
        return match.group(1)
    return None


def get_stock(product_id):
    """QVC APIから商品の全SKU在庫情報を取得する。

    Returns:
        dict: {
            "name": 商品名,
            "product_id": プロダクトID,
            "variants": [{"color": ..., "size": ..., "ats": "Y"|"N"|"L"}, ...],
            "overall_status": "IN_STOCK"|"LOW_IN_STOCK"|"SOLD_OUT"
        }
    """
    url = f"{QVC_API_BASE}/{product_id}"
    resp = requests.get(url, params={"response-depth": "full"})
    resp.raise_for_status()
    data = resp.json()

    product_name = data.get("productName", "")
    variants = []

    # SKU情報をパース
    for color_group in data.get("colours", []):
        color_name = color_group.get("colourName", "")
        for size_info in color_group.get("sizes", []):
            size_name = size_info.get("sizeName", "")
            ats = size_info.get("ats", "N")
            variants.append({
                "color": color_name,
                "size": size_name,
                "ats": ats,
            })

    overall_status = _determine_status(variants)

    return {
        "name": product_name,
        "product_id": product_id,
        "variants": variants,
        "overall_status": overall_status,
    }


def _determine_status(variants):
    """全SKUのATS情報から商品全体の在庫ステータスを判定する。"""
    if not variants:
        return "SOLD_OUT"

    ats_values = [v["ats"] for v in variants]

    # 全SKUが"N"の場合のみSOLD_OUT
    if all(a == "N" for a in ats_values):
        return "SOLD_OUT"

    # 1つ以上"L"があればLOW_IN_STOCK
    if any(a == "L" for a in ats_values):
        return "LOW_IN_STOCK"

    # それ以外（"Y"が存在）
    return "IN_STOCK"
