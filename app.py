
import os
import secrets
import html
import asyncio
import logging

import psycopg

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from database import init_db, DATABASE_URL
from monitor import check_sources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("radar-bot")

app = FastAPI(title="Радар-Бот")

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    max_age=3600,
    https_only=True,
    same_site="lax"
)

monitor_task = None

PAGES = {
    "dashboard": "Главная",
    "messages": "Сообщения",
    "monitor": "Мониторинг",
    "sources": "Источники",
    "drafts": "Черновики",
    "history": "История",
    "settings": "Настройки"
}


def db_query(query, params=()):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def db_execute(query, params=()):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)


def get_count(table):
    allowed = {"messages", "sources", "drafts", "audit_log"}

    if table not in allowed:
        return 0

    try:
        result = db_query(f"SELECT COUNT(*) FROM {table}")
        return result[0][0]
    except Exception:
        return 0


def log_action(action, details=""):
    db_execute(
        """
        INSERT INTO audit_log (action, details)
        VALUES (%s, %s)
        """,
        (action, details[:500])
    )


def safe_text(value):
    return html.escape(str(value or ""))


async def monitor_loop():
    while True:
        try:
            await asyncio.to_thread(check_sources)
        except Exception:
            logger.exception("Ошибка автоматической проверки")

        await asyncio.sleep(15 * 60)


@app.on_event("startup")
async def startup():
    global monitor_task

    init_db()
    monitor_task = asyncio.create_task(monitor_loop())


@app.on_event("shutdown")
async def shutdown():
    global monitor_task

    if monitor_task:
        monitor_task.cancel()

        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


def panel_content(page):

    if page == "dashboard":
        return f"""
        <section class="welcome">
            <h2>Добро пожаловать!</h2>
            <p>Центр управления проектом «Радар Анапа».</p>
        </section>

        <div class="stats">
            <div class="stat">
                <span>Сообщения</span>
                <b>{get_count("messages")}</b>
            </div>

            <div class="stat">
                <span>Источники</span>
                <b>{get_count("sources")}</b>
            </div>

            <div class="stat">
                <span>Черновики</span>
                <b>{get_count("drafts")}</b>
            </div>
        </div>

        <section class="panel">
            <h2>Состояние системы</h2>
            <p><span class="green-dot"></span> Панель работает</p>
            <p>База данных: PostgreSQL</p>
            <p>Автоматическая проверка: каждые 15 минут</p>
        </section>
        """

    if page == "messages":
        rows = db_query("""
            SELECT title, content, status, created_at
            FROM messages
            ORDER BY created_at DESC
            LIMIT 50
        """)

        items = ""

        for title, content, status, created in rows:
            items += f"""
            <article class="item">
                <h3>{safe_text(title)}</h3>
                <p>{safe_text(content)}</p>
                <small>{safe_text(status)} · {safe_text(created)}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Входящие сообщения</h2>
            {items or '<p class="muted">Сообщений пока нет.</p>'}
        </section>
        """

    if page == "monitor":
        rows = db_query("""
            SELECT title, content, status,
                   source_name, source_url, created_at
            FROM messages
            ORDER BY created_at DESC
            LIMIT 50
        """)

        items = ""

        for title, content, status, source, url, created in rows:
            safe_url = safe_text(url)

            items += f"""
            <article class="item">
                <h3>{safe_text(title)}</h3>
                <p>{safe_text(content)}</p>
                <small>
                    {safe_text(source)} · {safe_text(status)}
                </small>
                <p>
                    <a href="{safe_url}"
                       target="_blank"
                       rel="noopener noreferrer">
                       Открыть оригинал
                    </a>
                </p>
                <small>{safe_text(created)}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Автоматический мониторинг</h2>
            <p>Проверка источников каждые 15 минут.</p>
            <p>Новые официальные публикации сохраняются
            для ручной проверки.</p>

            <form action="/monitor/run" method="post">
                <button type="submit">
                    Проверить сейчас
                </button>
            </form>
        </section>

        <section class="panel">
            <h2>Найденные публикации</h2>
            {items or '<p class="muted">Публикаций пока нет.</p>'}
        </section>
        """

    if page == "sources":
        rows = db_query("""
            SELECT id, name, url, status
            FROM sources
            ORDER BY created_at DESC
        """)

        items = ""

        for source_id, name, url, status in rows:
            items += f"""
            <article class="item">
                <h3>{safe_text(name)}</h3>
                <p>{safe_text(url)}</p>
                <small>Статус: {safe_text(status)}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Источники информации</h2>
            {items or '<p class="muted">Источников пока нет.</p>'}
        </section>
        """

    if page == "drafts":
        rows = db_query("""
            SELECT id, title, content, status, created_at
            FROM drafts
            ORDER BY created_at DESC
        """)

        items = ""

        for draft_id, title, content, status, created in rows:
            items += f"""
            <article class="item">
                <h3>{safe_text(title)}</h3>
                <p>{safe_text(content)}</p>
                <small>{safe_text(status)} · {safe_text(created)}</small>

                <form action="/drafts/{draft_id}/delete"
                      method="post"
                      onsubmit="return confirm('Удалить черновик?')">
                    <button class="danger" type="submit">
                        Удалить
                    </button>
                </form>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Создать черновик</h2>

            <form action="/drafts/create" method="post">
                <input name="title"
                       placeholder="Заголовок"
                       maxlength="200"
                       required>

                <textarea name="content"
                          placeholder="Текст сообщения"
                          maxlength="10000"
                          rows="5"
                          required></textarea>

                <button type="submit">
                    Сохранить черновик
                </button>
            </form>
        </section>

        <section class="panel">
            <h2>Сохранённые черновики</h2>
            {items or '<p class="muted">Черновиков пока нет.</p>'}
        </section>
        """

    if page == "history":
        rows = db_query("""
            SELECT action, details, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT 50
        """)

        items = ""

        for action, details, created in rows:
            items += f"""
            <article class="item">
                <b>{safe_text(action)}</b>
                <p>{safe_text(details)}</p>
                <small>{safe_text(created)}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>История действий</h2>
            {items or '<p class="muted">История пока пуста.</p>'}
        </section>
        """

    if page == "settings":
        return """
        <section class="panel">
            <h2>Настройки проекта</h2>
            <p>Название: Радар Анапа</p>
            <p>Панель: Радар-Бот</p>
            <p>Версия: 1.2</p>
            <p>Хостинг: Render</p>
            <p>База данных: PostgreSQL</p>
            <p>Режим: закрытая административная панель</p>
        </section>
        """

    return "<section class='panel'>Раздел не найден.</section>"


def render_login(error=""):
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width,initial-scale=1">
        <title>Вход — Радар-Бот</title>
        <style>
            * {{ box-sizing:border-box; }}
            body {{
                margin:0;
                min-height:100vh;
                display:grid;
                place-items:center;
                background:#102c52;
                font-family:Arial,sans-serif;
                padding:20px;
            }}
            form {{
                background:white;
                padding:35px;
                border-radius:18px;
                width:min(100%,380px);
            }}
            h1 {{ color:#17477d; }}
            input {{
                width:100%;
                padding:14px;
                border:1px solid #ccd6e3;
                border-radius:8px;
                margin:15px 0;
            }}
            button {{
                width:100%;
                padding:14px;
                background:#2468a8;
                color:white;
                border:0;
                border-radius:8px;
                font-size:16px;
            }}
            .error {{ color:#d33; }}
        </style>
    </head>
    <body>
        <form action="/login" method="post">
            <h1>◈ РАДАР-БОТ</h1>
            <p>Закрытая панель управления</p>
            <input type="password"
                   name="password"
                   placeholder="Пароль"
                   required>
            <button type="submit">Войти</button>
            <p class="error">{safe_text(error)}</p>
        </form>
    </body>
    </html>
    """


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(render_login())


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if secrets.compare_digest(password, ADMIN_PASSWORD):
        request.session.clear()
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)

    return HTMLResponse(
        render_login("Неверный пароль"),
        status_code=401
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, page: str = "dashboard"):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)

    if page not in PAGES:
        page = "dashboard"

    nav = ""

    for key, title in PAGES.items():
        active = "active" if key == page else ""

        nav += f"""
        <a class="{active}" href="/?page={key}">
            {title}
        </a>
        """

    content = panel_content(page)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width,initial-scale=1">
        <title>{PAGES[page]} — Радар-Бот</title>

        <style>
            * {{ box-sizing:border-box; }}

            body {{
                margin:0;
                background:#f3f6fb;
                color:#17243a;
                font-family:Arial,sans-serif;
            }}

            .sidebar {{
                position:fixed;
                inset:0 auto 0 0;
                width:245px;
                background:#102c52;
                color:white;
                padding:25px 16px;
            }}

            .brand {{
                font-size:23px;
                font-weight:bold;
                padding:8px 12px 30px;
            }}

            .brand small {{
                display:block;
                font-size:12px;
                color:#a9c6e9;
                margin-top:7px;
                font-weight:normal;
            }}

            .sidebar a {{
                display:block;
                color:#c9d8eb;
                text-decoration:none;
                padding:13px 15px;
                border-radius:9px;
                margin:5px 0;
            }}

            .sidebar a.active,
            .sidebar a:hover {{
                background:#24548a;
                color:white;
            }}

            .logout {{
                position:absolute;
                bottom:22px;
                left:25px;
            }}

            main {{
                margin-left:245px;
                padding:30px;
                max-width:1300px;
            }}

            header {{
                display:flex;
                justify-content:space-between;
                align-items:center;
                margin-bottom:28px;
                gap:15px;
            }}

            h1 {{ font-size:27px; margin:0 0 7px; }}
            .muted {{ color:#8391a5; }}

            .welcome {{
                background:linear-gradient(110deg,#17477d,#2877bd);
                color:white;
                border-radius:16px;
                padding:25px;
                margin-bottom:22px;
            }}

            .stats {{
                display:grid;
                grid-template-columns:repeat(3,1fr);
                gap:16px;
                margin-bottom:22px;
            }}

            .stat,.panel,.item {{
                background:white;
                border:1px solid #e5ebf3;
                border-radius:14px;
                padding:22px;
                margin-bottom:16px;
            }}

            .stat span {{
                display:block;
                color:#7d8ba0;
            }}

            .stat b {{
                display:block;
                font-size:32px;
                margin-top:14px;
            }}

            .green-dot {{
                display:inline-block;
                width:9px;
                height:9px;
                background:#19b879;
                border-radius:50%;
                margin-right:8px;
            }}

            input,textarea {{
                width:100%;
                padding:13px;
                border:1px solid #d5deea;
                border-radius:8px;
                margin:8px 0;
                font:inherit;
            }}

            button {{
                background:#2468a8;
                color:white;
                border:0;
                padding:11px 17px;
                border-radius:8px;
                cursor:pointer;
            }}

            button.danger {{
                background:#c74343;
                margin-top:12px;
            }}

            a {{ color:#2468a8; }}

            @media(max-width:750px) {{
                .sidebar {{
                    position:static;
                    width:auto;
                    padding:15px;
                }}

                .brand {{ padding-bottom:12px; }}

                .sidebar nav {{
                    display:flex;
                    overflow-x:auto;
                    gap:5px;
                }}

                .sidebar a {{ white-space:nowrap; }}

                .logout {{
                    position:static;
                    display:block;
                    margin:12px;
                }}

                main {{
                    margin:0;
                    padding:18px;
                }}

                .stats {{ grid-template-columns:1fr; }}
            }}
        </style>
    </head>

    <body>
        <aside class="sidebar">
            <div class="brand">
                ◈ РАДАР-БОТ
                <small>Центр управления</small>
            </div>

            <nav>{nav}</nav>
            <a class="logout" href="/logout">↪ Выйти</a>
        </aside>

        <main>
            <header>
                <div>
                    <h1>{PAGES[page]}</h1>
                    <span class="muted">
                        Управление проектом «Радар Анапа»
                    </span>
                </div>

                <button onclick="location.reload()">
                    Обновить
                </button>
            </header>

            {content}
        </main>
    </body>
    </html>
    """)


@app.post("/monitor/run")
async def run_monitor_now(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)

    try:
        await asyncio.to_thread(check_sources)
        log_action("Запущена ручная проверка источников")
    except Exception:
        logger.exception("Ошибка ручной проверки")
        log_action("Ошибка проверки источников")

    return RedirectResponse("/?page=monitor", status_code=303)


@app.post("/drafts/create")
async def create_draft(
    request: Request,
    title: str = Form(...),
    content: str = Form(...)
):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)

    title = title.strip()
    content = content.strip()

    if not title or not content:
        return RedirectResponse("/?page=drafts", status_code=303)

    db_execute(
        """
        INSERT INTO drafts (title, content)
        VALUES (%s, %s)
        """,
        (title[:200], content[:10000])
    )

    log_action("Создан черновик", title[:200])

    return RedirectResponse("/?page=drafts", status_code=303)


@app.post("/drafts/{draft_id}/delete")
async def delete_draft(request: Request, draft_id: int):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)

    db_execute(
        "DELETE FROM drafts WHERE id = %s",
        (draft_id,)
    )

    log_action("Удалён черновик", f"ID: {draft_id}")

    return RedirectResponse("/?page=drafts", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
