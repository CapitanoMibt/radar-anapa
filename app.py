import os
import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "temporary-key-change-me"),
    max_age=3600
)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get("logged_in"):
        return """
        <h1>РАДАР-БОТ</h1>
        <p>Закрытая панель управления</p>
        <form action="/login" method="post">
            <input type="password" name="password"
                   placeholder="Пароль" required>
            <button type="submit">Войти</button>
        </form>
        """

    return """
    <h1>РАДАР-БОТ</h1>
    <p>Панель управления работает.</p>
    <p>Добро пожаловать!</p>
    <a href="/logout">Выйти</a>
    """


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if ADMIN_PASSWORD and secrets.compare_digest(
        password, ADMIN_PASSWORD
    ):
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)

    return HTMLResponse("Неверный пароль", status_code=401)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
