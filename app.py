
import os
import secrets
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    max_age=3600,
    https_only=True,
    same_site="lax"
)

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

PAGES = {
    "dashboard": ("Главная", "Обзор системы"),
    "messages": ("Сообщения", "Лента поступивших сообщений"),
    "sources": ("Источники", "Подключённые источники информации"),
    "drafts": ("Черновики", "Материалы, ожидающие проверки"),
    "history": ("История", "История действий"),
    "settings": ("Настройки", "Настройки панели")
}

def layout(page):
    title, subtitle = PAGES.get(page, PAGES["dashboard"])

    nav = ""
    for key, (name, _) in PAGES.items():
        active = "active" if key == page else ""
        nav += f'<a class="{active}" href="/?page={key}">{name}</a>'

    content = {
        "dashboard": """
        <div class="welcome">
          <h2>Добро пожаловать!</h2>
          <p>Центр управления проектом «Радар Анапа».</p>
        </div>
        <div class="stats">
          <div class="stat"><span>Сообщения</span><b>0</b><small>Поступило</small></div>
          <div class="stat"><span>Черновики</span><b>0</b><small>Ожидают проверки</small></div>
          <div class="stat"><span>Источники</span><b>0</b><small>Подключено</small></div>
        </div>
        <div class="panel">
          <h3>Состояние системы</h3>
          <p><i class="dot"></i> Панель управления запущена</p>
          <p><i class="dot gray"></i> Мониторинг пока не подключён</p>
        </div>
        <div class="panel">
          <h3>Последние события</h3>
          <p class="muted">Пока событий нет.</p>
        </div>
        """,
        "messages": """
        <div class="panel"><h3>Входящая лента</h3>
        <p class="muted">Здесь будут отображаться полученные сообщения.</p>
        <p>Автоматический сбор ещё не настроен.</p></div>
        """,
        "sources": """
        <div class="panel"><h3>Источники информации</h3>
        <p class="muted">Источники пока не подключены.</p>
        <p>Подключение будет доступно через разрешённые API и официальные каналы.</p></div>
        """,
        "drafts": """
        <div class="panel"><h3>Черновики публикаций</h3>
        <p class="muted">Новых черновиков пока нет.</p>
        <p>Материалы будут попадать сюда на проверку перед публикацией.</p></div>
        """,
        "history": """
        <div class="panel"><h3>История действий</h3>
        <p class="muted">История пока пуста.</p></div>
        """,
        "settings": """
        <div class="panel"><h3>Настройки</h3>
        <p>Название проекта: Радар Анапа</p>
        <p>Версия панели: 1.0</p>
        <p>Режим: закрытая административная панель</p></div>
        """
    }.get(page, "")

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} — Радар-Бот</title>
    <style>
    * {{box-sizing:border-box}}
    body {{margin:0;background:#f3f6fb;color:#17243a;
      font-family:Arial,sans-serif}}
    .sidebar {{position:fixed;inset:0 auto 0 0;width:245px;
      background:#102c52;color:white;padding:25px 16px}}
    .brand {{font-size:23px;font-weight:bold;padding:8px 12px 30px}}
    .brand small {{display:block;font-size:12px;color:#a9c6e9;
      margin-top:7px;font-weight:normal}}
    .sidebar a {{display:block;color:#c9d8eb;text-decoration:none;
      padding:13px 15px;border-radius:9px;margin:5px 0}}
    .sidebar a.active,.sidebar a:hover {{background:#24548a;color:white}}
    .logout {{position:absolute;bottom:22px;left:25px;color:#c9d8eb;
      text-decoration:none}}
    main {{margin-left:245px;padding:30px;max-width:1300px}}
    header {{display:flex;justify-content:space-between;
      align-items:center;margin-bottom:28px;gap:15px}}
    h1 {{font-size:27px;margin:0 0 7px}}
    .muted {{color:#8391a5}}
    .welcome {{background:linear-gradient(110deg,#17477d,#2877bd);
      color:white;border-radius:16px;padding:25px;margin-bottom:22px}}
    .welcome h2 {{margin:0 0 10px}}
    .welcome p {{margin:0;color:#d9eaff}}
    .stats {{display:grid;grid-template-columns:repeat(3,1fr);
      gap:16px;margin-bottom:22px}}
    .stat,.panel {{background:white;border:1px solid #e5ebf3;
      border-radius:14px;padding:22px}}
    .stat span,.stat small {{display:block;color:#7d8ba0}}
    .stat b {{display:block;font-size:32px;margin:14px 0}}
    .panel {{margin-bottom:18px}}
    .panel h3 {{margin-top:0}}
    .dot {{display:inline-block;width:9px;height:9px;
      background:#19b879;border-radius:50%;margin-right:8px}}
    .dot.gray {{background:#a6b1c0}}
    button {{background:#2468a8;color:white;border:0;
      padding:10px 17px;border-radius:8px;cursor:pointer}}
    @media(max-width:750px) {{
      .sidebar {{position:static;width:auto;padding:15px}}
      .brand {{padding-bottom:12px}}
      .sidebar nav {{display:flex;overflow-x:auto;gap:5px}}
      .sidebar a {{white-space:nowrap}}
      .logout {{position:static;display:block;margin:12px}}
      main {{margin:0;padding:18px}}
      .stats {{grid-template-columns:1fr}}
    }}
    </style>
    </head>
    <body>
    <aside class="sidebar">
      <div class="brand">◈ РАДАР-БОТ
        <small>Центр управления</small>
      </div>
      <nav>{nav}</nav>
      <a class="logout" href="/logout">↪ Выйти</a>
    </aside>
    <main>
      <header>
        <div><h1>{title}</h1><span class="muted">{subtitle}</span></div>
        <button onclick="location.reload()">Обновить</button>
      </header>
      {content}
    </main>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, page: str = "dashboard"):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse(layout(page if page in PAGES else "dashboard"))

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html><html lang="ru"><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Вход — Радар-Бот</title>
    <style>
    body{background:#102c52;font-family:Arial;display:grid;
    place-items:center;min-height:100vh;margin:0}
    form{background:white;padding:35px;border-radius:18px;
    width:min(90%,360px)}
    h1{color:#17477d}
    input{width:100%;padding:13px;border:1px solid #ccd6e3;
    border-radius:8px;margin:12px 0;box-sizing:border-box}
    button{width:100%;padding:13px;background:#2468a8;
    color:white;border:0;border-radius:8px}
    </style>
    <form action="/login" method="post">
    <h1>◈ РАДАР-БОТ</h1>
    <p>Закрытая панель управления</p>
    <input type="password" name="password" placeholder="Пароль" required>
    <button>Войти</button>
    </form></html>
    """

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if secrets.compare_digest(password, ADMIN_PASSWORD):
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)
    return HTMLResponse("Неверный пароль", status_code=401)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
