#!/usr/bin/env python3
"""Shopliveからキャンペーンスケジュールを取得し、schedule.jsonに保存する。

日次または手動で実行して、今後のライブ予定を更新する。
"""

import json
import logging
from datetime import datetime, timezone, timedelta

import shoplive_client
from config import SCHEDULE_FILE, DEFAULT_LIVE_DURATION_MINUTES

JST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def fetch_and_save_schedule():
    """READY・ONAIRのキャンペーンスケジュールを取得してファイルに保存する。"""
    schedules = []

    for status in ("READY", "ONAIR"):
        try:
            campaigns = shoplive_client.get_campaigns(campaign_status=status, count=50)
        except Exception as e:
            logger.error(f"{status}キャンペーン取得エラー: {e}")
            continue

        for c in campaigns:
            start_at = c.get("scheduledStartAt")
            if not start_at:
                continue

            end_at = c.get("scheduledEndAt")
            schedules.append({
                "campaignId": c.get("campaignId"),
                "campaignKey": c.get("campaignKey"),
                "title": c.get("title", ""),
                "status": c.get("campaignStatus"),
                "scheduledStartAt": start_at,
                "scheduledEndAt": end_at,
            })

    # 開始時刻順にソート
    schedules.sort(key=lambda s: s["scheduledStartAt"])

    output = {
        "updated_at": datetime.now(JST).isoformat(),
        "campaigns": schedules,
    }

    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"スケジュール保存: {len(schedules)}件 → {SCHEDULE_FILE}")
    for s in schedules:
        logger.info(f"  {s['scheduledStartAt']} {s['title']} [{s['status']}]")

    return schedules


def is_within_live_window(schedule_file=None):
    """現在時刻がライブ配信時間帯（バッファ含む）内かどうかを判定する。

    schedule.jsonが存在しない場合はTrueを返す（安全側に倒す）。
    """
    from config import SCHEDULE_BUFFER_MINUTES

    path = schedule_file or SCHEDULE_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        # スケジュールファイルがなければ常に実行（初回など）
        return True

    now = datetime.now(timezone.utc)
    buffer = timedelta(minutes=SCHEDULE_BUFFER_MINUTES)
    default_duration = timedelta(minutes=DEFAULT_LIVE_DURATION_MINUTES)

    for c in data.get("campaigns", []):
        start = datetime.fromisoformat(c["scheduledStartAt"].replace("Z", "+00:00"))
        if c.get("scheduledEndAt"):
            end = datetime.fromisoformat(c["scheduledEndAt"].replace("Z", "+00:00"))
        else:
            end = start + default_duration

        if (start - buffer) <= now <= (end + buffer):
            return True

    return False


if __name__ == "__main__":
    fetch_and_save_schedule()
