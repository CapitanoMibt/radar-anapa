

import os
import secrets
import html

import psycopg

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from database import init_db, DATABASE_URL

app = FastAPI(title="Радар-Бот")

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    max_age=3600,
    https_only=True,
    same_site="lax"
)


@app.on_event("startup")
async def startup():
    init_db()


PAGES = {
    "dashboard": "Главная",
    "messages": "Сообщения",
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


def get_count(table):
    allowed = {"messages", "sources", "drafts", "audit_log"}
    if table not in allowed:
        return 0

    try:
        result = db_query(f"SELECT COUNT(*) FROM {table}")
        return result[0][0]
    except Exception:
        return 0


def panel_content(page):
    if page == "dashboard":
        messages = get_count("messages")
        sources = get_count("sources")
        drafts = get_count("drafts")

        return f"""
        <section class="welcome">
            <h2>Добро пожаловать в Радар-Бот!</h2>
            <p>Центр управления проектом «Радар Анапа».</p>
        </section>

        <div class="stats">
            <div class="stat">
                <span>Сообщения</span>
                <b>{messages}</b>
            </div>
            <div class="stat">
                <span>Источники</span>
                <b>{sources}</b>
            </div>
            <div class="stat">
                <span>Черновики</span>
                <b>{drafts}</b>
            </div>
        </div>

        <section class="panel">
            <h3>Состояние системы</h3>
            <p><span class="green-dot"></span> Панель работает</p>
            <p>База данных подключается через PostgreSQL.</p>
            <p>Автоматический мониторинг пока не подключён.</p>
        </section>
        """

    if page == "messages":
        try:
            rows = db_query("""
                SELECT title, content, status, created_at
                FROM messages
                ORDER BY created_at DESC
                LIMIT 50
            """)
        except Exception:
            rows = []

        items = ""
        for title, content, status, created in rows:
            items += f"""
            <article class="item">
                <h3>{html.escape(title)}</h3>
                <p>{html.escape(content or "")}</p>
                <small>{html.escape(status)} · {created}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Входящие сообщения</h2>
            {items or '<p class="muted">Сообщений пока нет.</p>'}
        </section>
        """

    if page == "sources":
        try:
            rows = db_query("""
                SELECT name, url, status
                FROM sources
                ORDER BY created_at DESC
            """)
        except Exception:
            rows = []

        items = ""
        for name, url, status in rows:
            items += f"""
            <article class="item">
                <h3>{html.escape(name)}</h3>
                <p>{html.escape(url)}</p>
                <small>Статус: {html.escape(status)}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Источники информации</h2>
            {items or '<p class="muted">Источники пока не добавлены.</p>'}
            <p class="muted">
                Подключение возможно через разрешённые API.
            </p>
        </section>
        """

    if page == "drafts":
        try:
            rows = db_query("""
                SELECT title, content, status, created_at
                FROM drafts
                ORDER BY created_at DESC
            """)
        except Exception:
            rows = []

        items = ""
        for title, content, status, created in rows:
            items += f"""
            <article class="item">
                <h3>{html.escape(title)}</h3>
                <p>{html.escape(content)}</p>
                <small>{html.escape(status)} · {created}</small>
            </article>
            """

        return f"""
        <section class="panel">
            <h2>Черновики</h2>
            {items or '<p class="muted">Черновиков пока нет.</p>'}
            <p>Публикации требуют ручного подтверждения.</p>
        </section>
        """

    if page == "history":
        try:
            rows = db_query("""
                SELECT action, details, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT 50
            """)
        except Exception:
            rows = []

        items = ""
        for action, details, created in rows:
            items += f"""
            <article class="item">
                <b>{html.escape(action)}</b>
                <p>{html.escape(details or "")}</p>
                <small>{created}</small>
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
            <p>Версия: 1.0</p>
            <p>Режим: закрытый</p>
            <p>Хостинг: Render</p>
            <p>База данных: PostgreSQL</p>
        </section>
        """

    return "<section class='panel'>Раздел не найден.</section>"


def render_login(error=""):
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Вход — Радар-Бот</title>
    <style>
    * {{box-sizing:border-box}}
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
    h1 {{color:#17477d}}
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
    .error {{color:#d33}}
    </style>
    </head>
    <body>
    <form action="/login" method="post">
        <h1>◈ РАДАР-БОТ</h1>
        <p>Закрытая панель управления</p>
        <input type="password" name="password"
        placeholder="Пароль" required>
        <button type="submit">Войти</button>
        <p class="error">{html.escape(error)}</p>
    </form>
    </body>
    </html>
    """


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(render_login())


@app.post("/login")
async def login(
    request: Request,
    password: str = Form(...)
):
    if secrets.compare_digest(password, ADMIN_PASSWORD):
        request.session.clear()
        request.session["logged_in"] = True

        return RedirectResponse(
            "/",
            status_code=303
        )

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
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{PAGES[page]} — Радар-Бот</title>

    <style>
    * {{box-sizing:border-box}}

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

    h1 {{font-size:27px;margin:0 0 7px}}

    .muted {{color:#8391a5}}

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

    button {{
        background:#2468a8;
        color:white;
        border:0;
        padding:10px 17px;
        border-radius:8px;
        cursor:pointer;
    }}

    @media(max-width:750px) {{
        .sidebar {{
            position:static;
            width:auto;
            padding:15px;
        }}

        .brand {{padding-bottom:12px}}

        .sidebar nav {{
            display:flex;
            overflow-x:auto;
            gap:5px;
        }}

        .sidebar a {{white-space:nowrap}}

        .logout {{
            position:static;
            display:block;
            margin:12px;
        }}

        main {{
            margin:0;
            padding:18px;
        }}

        .stats {{grid-template-columns:1fr}}
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


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

