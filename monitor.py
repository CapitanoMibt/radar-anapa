
import os
import time
import hashlib
import logging
from urllib.parse import urlparse

import feedparser
import psycopg

from database import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("radar-monitor")

CHECK_INTERVAL = 15 * 60

ALLOWED_DOMAINS = {
    "23.mchs.gov.ru",
    "anapa-official.ru",
}

# Только общие официальные сообщения для жителей.
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


def get_feeds():
    raw = os.getenv("RSS_FEEDS", "")
    result = []

    for url in raw.split(";"):
        url = url.strip()

        if not url:
            continue

        parsed = urlparse(url)

        if parsed.scheme != "https":
            continue

        if parsed.hostname not in ALLOWED_DOMAINS:
            logger.warning("Источник пропущен: домен не разрешён")
            continue

        result.append(url)

    return result


def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    return any(word in text for word in KEYWORDS)


def save_entry(title, summary, link, source_name):
    fingerprint = hashlib.sha256(
        (link or title + summary).encode("utf-8")
    ).hexdigest()

    with psycopg.connect(DATABASE_URL) as conn:
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
    feeds = get_feeds()

    if not feeds:
        logger.warning("RSS_FEEDS не настроен")
        return

    for url in feeds:
        try:
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                logger.warning("Не удалось прочитать RSS")
                continue

            source_name = feed.feed.get("title", "Официальный источник")

            for entry in feed.entries[:30]:
                title = entry.get("title", "").strip()
                summary = entry.get(
                    "summary", entry.get("description", "")
                ).strip()
                link = entry.get("link", "").strip()

                if not title or not link:
                    continue

                parsed_link = urlparse(link)

                if (
                    parsed_link.scheme != "https"
                    or parsed_link.hostname not in ALLOWED_DOMAINS
                ):
                    continue

                if not is_relevant(title, summary):
                    continue

                if save_entry(title, summary, link, source_name):
                    logger.info("Добавлена новая публикация")

        except Exception:
            logger.exception("Ошибка проверки источника")


def run_monitor():
    logger.info("Мониторинг запущен")

    while True:
        check_sources()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_monitor()
