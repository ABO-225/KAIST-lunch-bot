"""KAIST 점심 메뉴를 가져와 카카오톡 채팅방에 보낸다.

사용법:
  python main.py --dry-run          # 보내지 않고 메시지만 출력
  python main.py                    # 오늘 메뉴 전송
  python main.py --date 2026-11-12  # 특정 날짜
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

import config
from menu.formatter import format_compact, format_message
from menu.summarizer import summarize
from menu.scraper import get_lunch_menu

LOG_DIR = Path(__file__).parent / "logs"


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _write_out(path: str, text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="전송하지 않고 출력만")
    parser.add_argument("--date", help="YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--force", action="store_true", help="메뉴가 비어도 전송")
    parser.add_argument("--full", action="store_true", help="요약 없이 전체 메뉴")
    parser.add_argument("--out", help="카톡으로 보내지 않고 이 파일에 저장 (iPhone 단축어용)")
    parser.add_argument("--list-rooms", action="store_true", help="열려 있는 카톡 채팅방 이름 출력")
    args = parser.parse_args()

    if args.list_rooms:
        from sender.kakao_pc import list_chat_windows

        rooms = list_chat_windows()
        print("\n".join(f"'{r}'" for r in rooms) or "열려 있는 채팅창이 없습니다.")
        return 0

    setup_logging()
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    menus = [get_lunch_menu(config.MENU_URL, code, name, date) for code, name in config.CAFETERIAS]
    for m in menus:
        if m.error:
            logging.warning("%s 실패: %s", m.name, m.error)

    if config.SKIP_IF_EMPTY and not args.force and all(m.empty for m in menus):
        logging.info("%s: 메뉴가 없어 전송하지 않습니다.", date)
        if args.out:  # 빈 파일 → 단축어가 보내지 않음 (어제 메뉴가 다시 가는 것 방지)
            _write_out(args.out, "")
        return 0

    if args.full:
        text = format_message(menus, date)
    else:
        lines = summarize(menus, config.MAIN_KEYWORDS, config.DESSERT_KEYWORDS)
        text = format_compact(menus, lines, config.SHORT_NAMES, date, config.SHOW_PRICE)

    if args.dry_run:
        print(text)
        return 0

    if args.out:
        _write_out(args.out, text)
        logging.info("%s 에 저장 완료", args.out)
        return 0

    from sender.kakao_pc import send_message

    send_message(config.ROOM_NAME, text)
    logging.info("'%s' 방에 전송 완료", config.ROOM_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
