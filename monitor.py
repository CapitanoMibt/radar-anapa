
import os
import hashlib
import logging
import socket
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from threading import Lock

import feedparser
import psycopg

from database import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("radar-monitor")

CHECK_INTERVAL = 15 * 60
REQUEST_TIMEOUT = 12
MAX_FEED_SIZE = 2 * 1024 * 1024

ALLOWED_DOMAINS = {
    "23.mchs.gov.ru",
    "anapa-official.ru",
}

KEYWORDS = (
    "анап",
    "шторм",
    "погод",
    "пожар",
    "эвакуац",
    "затоп",
    "электроснабж",
    "водоснабж",
    "перекрыт",
)

check_lock = Lock()


def allowed_host(hostname):
    if not hostname:
        return False

    hostname = hostname.lower()

    return any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in ALLOWED_DOMAINS
    )


def get_feeds():
    raw = os.getenv("RSS_FEEDS", "")
    result = []

    for url in raw.split(";"):
        url = url.strip()

        if not url:
            continue

        parsed = urlparse(url)

        if parsed.scheme != "https" or not allowed_host(parsed.hostname):
            logger.warning("Источник пропущен: домен не разрешён")
            continue

        result.append(url)

    return result


def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    return any(word in text for word in KEYWORDS)


def download_feed(url):
    request = Request(
        url,
        headers={
            "User-Agent": "RadarAnapa/1.0 RSS reader",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        final_url = response.geturl()
        parsed_url = urlparse(final_url)

        if (
            parsed_url.scheme != "https"
            or not allowed_host(parsed_url.hostname)
        ):
            raise ValueError("Недопустимый адрес после перенаправления")

        data = response.read(MAX_FEED_SIZE + 1)

    if len(data) > MAX_FEED_SIZE:
        raise ValueError("RSS-лента слишком большая")

    if not data:
        raise ValueError("RSS-лента пустая")

    return data


def save_entry(title, summary, link, source_name):
    fingerprint = hashlib.sha256(
        (link or title + summary).encode("utf-8")
    ).hexdigest()

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=8
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages
                    (title, content, status,
                     source_name, source_url, fingerprint)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint)
                WHERE fingerprint IS NOT NULL
                DO NOTHING
                """,
                (
                    title[:200],
                    summary[:10000],
                    "На проверке",
                    source_name[:200],
                    link[:2000],
                    fingerprint,
                ),
            )

            return cur.rowcount > 0


def check_sources():
    if not check_lock.acquire(blocking=False):
        logger.info("Проверка уже выполняется")
        return

    try:
        feeds = get_feeds()

        if not feeds:
            logger.warning("RSS_FEEDS не настроен или адрес не разрешён")
            return

        logger.info("Начинаю проверку RSS. Источников: %s", len(feeds))

        for url in feeds:
            try:
                logger.info("Загружаю RSS: %s", url)

                data = download_feed(url)
                feed = feedparser.parse(data)

                if feed.bozo and not feed.entries:
                    logger.warning("Не удалось прочитать RSS: %s", url)
                    continue

                source_name = feed.feed.get(
                    "title",
                    "Официальный источник"
                )

                logger.info(
                    "Получено публикаций: %s",
                    len(feed.entries)
                )

                added = 0

                for entry in feed.entries[:30]:
                    title = entry.get("title", "").strip()
                    summary = entry.get(
                        "summary",
                        entry.get("description", "")
                    ).strip()
                    link = entry.get("link", "").strip()

                    if not title or not link:
                        continue

                    parsed_link = urlparse(link)

                    if (
                        parsed_link.scheme != "https"
                        or not allowed_host(parsed_link.hostname)
                    ):
                        continue

                    if not is_relevant(title, summary):
                        continue

                    if save_entry(
                        title,
                        summary,
                        link,
                        source_name
                    ):
                        added += 1

                logger.info(
                    "Проверка завершена. Новых публикаций: %s",
                    added
                )

            except (TimeoutError, socket.timeout):
                logger.warning("Источник не ответил за отведённое время")

            except Exception:
                logger.exception("Ошибка проверки источника")

        logger.info("Проверка всех источников завершена")

    finally:
        check_lock.release()


def run_monitor():
    logger.info("Мониторинг запущен")

    while True:
        check_sources()

        import time
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_monitor()
