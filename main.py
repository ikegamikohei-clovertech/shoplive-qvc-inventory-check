#!/usr/bin/env python3
"""QVC在庫チェッカー: ONAIR中のShopliveキャンペーン商品の在庫をQVCから取得し更新する。"""

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import shoplive_client
import qvc_client
from config import OUTPUT_DIR, STOCK_STATUS_FILE
JST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main(skip_schedule_check=False):
    # 0. スケジュール判定: ライブ時間帯外なら即終了（API呼び出しなし）
    #    runner.py経由の場合はスキップ（既に判定済み）
    if not skip_schedule_check:
        from scheduler import is_within_live_window
        if not is_within_live_window():
            return

    # 1. 対象キャンペーンを取得（ONAIR + 開始10分以内のREADY）
    campaigns = shoplive_client.get_target_campaigns(ready_threshold_minutes=10)

    if not campaigns:
        logger.info("対象キャンペーンなし")
        return

    for campaign in campaigns:
        campaign_key = campaign.get("campaignKey")
        campaign_title = campaign.get("title", "不明")
        campaign_status = campaign.get("campaignStatus", "")
        if campaign.get("_ready_starting_soon"):
            logger.info(f"キャンペーン検出 [READY/まもなく開始]: {campaign_title} (key={campaign_key})")
        else:
            logger.info(f"キャンペーン検出 [ONAIR]: {campaign_title} (key={campaign_key})")

        # 2. 商品リスト取得
        products_data = shoplive_client.get_campaign_products(campaign_key)
        products = products_data.get("results", []) if isinstance(products_data, dict) else products_data

        if not products:
            logger.info(f"  商品なし")
            continue

        # ステータスごとに商品IDをグルーピング
        status_groups = {"IN_STOCK": [], "LOW_IN_STOCK": [], "SOLD_OUT": []}
        all_product_results = []

        for product in products:
            shoplive_product_id = int(product.get("productId"))
            product_url = product.get("url", "")
            product_name = product.get("name", "不明")

            # 3. QVC商品IDを抽出
            qvc_id = qvc_client.extract_product_id(product_url)
            if not qvc_id:
                logger.warning(f"  QVC商品ID抽出失敗: {product_name} (url={product_url})")
                continue

            # 4. QVC APIで在庫情報取得
            try:
                stock_info = qvc_client.get_stock(qvc_id)
            except Exception as e:
                logger.error(f"  QVC在庫取得エラー: {product_name} (id={qvc_id}): {e}")
                continue

            status = stock_info["overall_status"]
            status_groups[status].append(shoplive_product_id)
            all_product_results.append(stock_info)

            logger.info(f"  {product_name} ({qvc_id}): {status} "
                        f"(SKU数: {len(stock_info['variants'])})")

        # 5. Shopliveの在庫ステータスをステータスごとに更新
        for status, product_ids in status_groups.items():
            if not product_ids:
                continue
            try:
                shoplive_client.update_stock_status(campaign_key, product_ids, status)
                logger.info(f"  Shoplive更新: {status} → {len(product_ids)}商品")
            except Exception as e:
                logger.error(f"  Shoplive更新エラー ({status}): {e}")

        # 6. OBS用データ出力
        output_data = {
            "updated_at": datetime.now(JST).isoformat(),
            "campaign": campaign_title,
            "products": all_product_results,
        }
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(STOCK_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info(f"  OBS用データ出力: {STOCK_STATUS_FILE}")

    logger.info("処理完了")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"予期しないエラー: {e}", exc_info=True)
        sys.exit(1)
