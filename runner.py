#!/usr/bin/env python3
"""ライブ時間帯中に main.py を2分間隔で繰り返し実行するランナー。

GitHub Actions上での長時間ポーリング用。
1. scheduler.py でスケジュール取得
2. 本日のライブがあれば、開始5分前まで待機
3. ライブ時間帯中は2分間隔で main.py を実行
4. 毎回の実行後、output/ を gh-pages にpush（GitHub Pages公開用）
"""

import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone, timedelta

import scheduler
from config import SCHEDULE_FILE, SCHEDULE_BUFFER_MINUTES, DEFAULT_LIVE_DURATION_MINUTES, STOCK_STATUS_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 120  # 秒


def get_todays_window():
    """本日のライブ時間帯（UTC）を返す。なければNone。"""
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    buffer = timedelta(minutes=SCHEDULE_BUFFER_MINUTES)
    default_duration = timedelta(minutes=DEFAULT_LIVE_DURATION_MINUTES)

    earliest_start = None
    latest_end = None

    for c in data.get("campaigns", []):
        start = datetime.fromisoformat(c["scheduledStartAt"].replace("Z", "+00:00"))
        if not (today_start <= start < today_end):
            continue

        if c.get("scheduledEndAt"):
            end = datetime.fromisoformat(c["scheduledEndAt"].replace("Z", "+00:00"))
        else:
            end = start + default_duration

        window_start = start - buffer
        window_end = end + buffer

        if earliest_start is None or window_start < earliest_start:
            earliest_start = window_start
        if latest_end is None or window_end > latest_end:
            latest_end = window_end

    if earliest_start is None:
        return None
    return earliest_start, latest_end


def publish_to_gh_pages():
    """output/stock_status.json を gh-pages ブランチにpushする。"""
    gh_pages_dir = os.environ.get("GH_PAGES_DIR")
    if not gh_pages_dir or not os.path.isdir(gh_pages_dir):
        return

    if not os.path.exists(STOCK_STATUS_FILE):
        return

    shutil.copy2(STOCK_STATUS_FILE, os.path.join(gh_pages_dir, "stock_status.json"))

    # index.html も最新をコピー
    index_src = os.path.join(os.path.dirname(STOCK_STATUS_FILE), "index.html")
    if os.path.exists(index_src):
        shutil.copy2(index_src, os.path.join(gh_pages_dir, "index.html"))

    try:
        subprocess.run(
            ["git", "add", "stock_status.json", "index.html"],
            cwd=gh_pages_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Update stock status"],
            cwd=gh_pages_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "gh-pages"],
            cwd=gh_pages_dir, check=True, capture_output=True,
        )
        logger.info("  gh-pages にpush完了")
    except subprocess.CalledProcessError:
        # 変更なし（同じ内容）の場合はcommitが失敗するが問題なし
        pass


def run():
    # 1. スケジュール取得
    logger.info("スケジュール取得中...")
    scheduler.fetch_and_save_schedule()

    # 2. 本日のライブ確認
    window = get_todays_window()
    if window is None:
        logger.info("本日のライブ予定なし。終了します。")
        return

    window_start, window_end = window
    now = datetime.now(timezone.utc)
    jst = timezone(timedelta(hours=9))

    logger.info(f"本日のライブ時間帯: {window_start.astimezone(jst).strftime('%H:%M')} 〜 "
                f"{window_end.astimezone(jst).strftime('%H:%M')} JST")

    # 3. 開始まで待機
    if now < window_start:
        wait_seconds = (window_start - now).total_seconds()
        logger.info(f"開始まで {int(wait_seconds // 60)} 分待機...")
        time.sleep(wait_seconds)

    # 4. ポーリングループ
    import main as main_module
    while datetime.now(timezone.utc) <= window_end:
        cycle_start = time.monotonic()
        logger.info("--- 在庫チェック実行 ---")
        try:
            main_module.main(skip_schedule_check=True)
            publish_to_gh_pages()
        except Exception as e:
            logger.error(f"main.py エラー: {e}", exc_info=True)
        elapsed = time.monotonic() - cycle_start
        sleep_time = max(0, POLL_INTERVAL - elapsed)
        if elapsed > POLL_INTERVAL:
            logger.warning(f"処理時間({elapsed:.1f}秒)がポーリング間隔({POLL_INTERVAL}秒)を超過しました")
        time.sleep(sleep_time)

    logger.info("ライブ時間帯終了。終了します。")


if __name__ == "__main__":
    run()
