"""API e servidor local da vitrine Droga Center + Rede Amparo."""

import os
import re
import secrets
import unicodedata
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Literal

import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parent
PRODUCT_IMAGES_DIR = ROOT / "assets" / "products"
load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
SESSION_COOKIE = "farmacia_admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 8
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
MAX_PRODUCT_IMAGE_SIZE = 5 * 1024 * 1024


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ProductPayload(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=500)
    category_slug: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    package_label: str = Field(default="", max_length=80)
    visual_theme: Literal["lotion", "sun", "soap", "vitamin"] = "lotion"
    is_demo: bool = True
    active: bool = True


class CategoryPayload(BaseModel):
    name: str = Field(min_length=2, max_length=100)

CATEGORIES = [
    ("dermocosmeticos", "Dermocosméticos"),
    ("higiene-pessoal", "Higiene pessoal"),
    ("vitaminas", "Vitaminas"),
]

DEMO_PRODUCTS = [
    {
        "slug": "hidratante-corporal-demo",
        "category_slug": "dermocosmeticos",
        "name": "Hidratante corporal",
        "description": "Exemplo de produto para o catálogo",
        "price": 29.90,
        "package_label": "200 ml",
        "visual_theme": "lotion",
    },
    {
        "slug": "protetor-solar-demo",
        "category_slug": "dermocosmeticos",
        "name": "Protetor solar",
        "description": "Exemplo de produto para o catálogo",
        "price": 49.90,
        "package_label": "FPS 50",
        "visual_theme": "sun",
    },
    {
        "slug": "sabonete-liquido-demo",
        "category_slug": "higiene-pessoal",
        "name": "Sabonete líquido",
        "description": "Exemplo de produto para o catálogo",
        "price": 16.90,
        "package_label": "250 ml",
        "visual_theme": "soap",
    },
    {
        "slug": "vitamina-c-demo",
        "category_slug": "vitaminas",
        "name": "Vitamina C",
        "description": "Exemplo de produto para o catálogo",
        "price": 24.90,
        "package_label": "30 un.",
        "visual_theme": "vitamin",
    },
]


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def connect_db():
    if not DATABASE_URL:
        raise RuntimeError(
            "Configure a variável DATABASE_URL com a conexão do PostgreSQL."
        )
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def session_serializer() -> URLSafeTimedSerializer:
    if not SESSION_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Configure SESSION_SECRET no arquivo .env para habilitar o painel.",
        )
    return URLSafeTimedSerializer(SESSION_SECRET, salt="farmacia-admin-session")


def require_admin(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    try:
        session = session_serializer().loads(token, max_age=SESSION_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.")
    return str(session.get("sub", ""))


def create_product_slug(name: str) -> str:
    slug = slugify(name)
    if not slug:
        raise HTTPException(status_code=422, detail="Informe um nome válido para o produto.")
    return f"{slug}-{secrets.token_hex(3)}"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def ensure_category_exists(category_slug: str) -> None:
    with connect_db() as connection:
        category = connection.execute(
            "SELECT slug FROM categories WHERE slug = %s", (category_slug,)
        ).fetchone()
    if not category:
        raise HTTPException(status_code=422, detail="Selecione uma categoria válida.")


def image_extension(contents: bytes) -> str | None:
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp"
    return None


def remove_product_image(image_url: str) -> None:
    prefix = "/assets/products/"
    if not image_url.startswith(prefix):
        return
    filename = Path(image_url).name
    image_path = (PRODUCT_IMAGES_DIR / filename).resolve()
    if image_path.parent == PRODUCT_IMAGES_DIR.resolve() and image_path.is_file():
        image_path.unlink()


def initialize_database() -> None:
    with connect_db() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE,
                    category_slug TEXT NOT NULL REFERENCES categories(slug),
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
                    package_label TEXT NOT NULL DEFAULT '',
                    visual_theme TEXT NOT NULL DEFAULT 'lotion',
                    image_url TEXT NOT NULL DEFAULT '',
                    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT NOT NULL DEFAULT ''"
            )
            cursor.executemany(
                "INSERT INTO categories (slug, name) VALUES (%s, %s) ON CONFLICT (slug) DO NOTHING",
                CATEGORIES,
            )
            cursor.execute("SELECT COUNT(*) AS total FROM products")
            if cursor.fetchone()["total"] == 0:
                cursor.executemany(
                    """
                    INSERT INTO products
                        (slug, category_slug, name, description, price,
                         package_label, visual_theme, is_demo)
                    VALUES
                        (%(slug)s, %(category_slug)s, %(name)s, %(description)s,
                         %(price)s, %(package_label)s, %(visual_theme)s, TRUE)
                    """,
                    DEMO_PRODUCTS,
                )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    PRODUCT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    initialize_database()
    yield


app = FastAPI(
    title="Droga Center + Rede Amparo API",
    description="API local para consultar o catálogo demonstrativo da farmácia.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/health")
def health():
    try:
        with connect_db() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except (psycopg.Error, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/categories")
def list_categories():
    with connect_db() as connection:
        rows = connection.execute(
            """
            SELECT c.slug, c.name, COUNT(p.id)::INTEGER AS product_count
            FROM categories AS c
            LEFT JOIN products AS p ON p.category_slug = c.slug AND p.active = TRUE
            GROUP BY c.slug, c.name
            ORDER BY c.name
            """
        ).fetchall()
    return {"items": rows}


@app.post("/api/admin/categories", status_code=201)
def admin_create_category(
    payload: CategoryPayload, _username: str = Depends(require_admin)
):
    name = payload.name.strip()
    slug = slugify(name)
    if not slug:
        raise HTTPException(status_code=422, detail="Informe um nome válido para a categoria.")
    try:
        with connect_db() as connection:
            item = connection.execute(
                "INSERT INTO categories (slug, name) VALUES (%s, %s) RETURNING slug, name",
                (slug, name),
            ).fetchone()
    except UniqueViolation as error:
        raise HTTPException(
            status_code=409, detail="Já existe uma categoria com esse nome."
        ) from error
    return item


@app.put("/api/admin/categories/{slug}")
def admin_update_category(
    slug: str, payload: CategoryPayload, _username: str = Depends(require_admin)
):
    name = payload.name.strip()
    try:
        with connect_db() as connection:
            item = connection.execute(
                "UPDATE categories SET name = %s WHERE slug = %s RETURNING slug, name",
                (name, slug),
            ).fetchone()
    except UniqueViolation as error:
        raise HTTPException(
            status_code=409, detail="Já existe uma categoria com esse nome."
        ) from error
    if not item:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return item


@app.get("/api/products")
def list_products(
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=80),
):
    with connect_db() as connection:
        rows = connection.execute(
            """
            SELECT p.slug, p.name, p.description, p.price::FLOAT AS price,
                   p.package_label, p.visual_theme, p.image_url, p.is_demo,
                   c.slug AS category_slug, c.name AS category
            FROM products AS p
            JOIN categories AS c ON c.slug = p.category_slug
            WHERE p.active = TRUE
            ORDER BY p.name
            """
        ).fetchall()

    normalized_query = normalize_text(q.strip())
    normalized_category = normalize_text(category.strip())
    items = []
    for row in rows:
        searchable = normalize_text(
            " ".join(
                str(row[field])
                for field in ("name", "description", "category", "category_slug")
            )
        )
        if normalized_query and normalized_query not in searchable:
            continue
        if normalized_category and normalize_text(row["category_slug"]) != normalized_category:
            continue
        items.append(row)

    return {
        "items": items,
        "count": len(items),
        "all_demo": all(item["is_demo"] for item in items) if items else False,
    }


@app.post("/api/admin/login")
def admin_login(payload: LoginPayload, response: Response):
    if not ADMIN_USERNAME or not ADMIN_PASSWORD or not SESSION_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Configure ADMIN_USERNAME, ADMIN_PASSWORD e SESSION_SECRET no arquivo .env.",
        )
    username_matches = secrets.compare_digest(
        payload.username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8")
    )
    password_matches = secrets.compare_digest(
        payload.password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")
    )
    if not (username_matches and password_matches):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")

    token = session_serializer().dumps({"sub": ADMIN_USERNAME})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"username": ADMIN_USERNAME}


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"ok": True}


@app.get("/api/admin/session")
def admin_session(username: str = Depends(require_admin)):
    return {"username": username}


@app.get("/api/admin/products")
def admin_list_products(_username: str = Depends(require_admin)):
    with connect_db() as connection:
        items = connection.execute(
            """
            SELECT p.slug, p.name, p.description, p.price::FLOAT AS price,
                   p.package_label, p.visual_theme, p.image_url, p.is_demo, p.active,
                   c.slug AS category_slug, c.name AS category
            FROM products AS p
            JOIN categories AS c ON c.slug = p.category_slug
            ORDER BY p.created_at DESC, p.id DESC
            """
        ).fetchall()
    return {"items": items}


@app.post("/api/admin/products", status_code=201)
def admin_create_product(
    payload: ProductPayload, _username: str = Depends(require_admin)
):
    ensure_category_exists(payload.category_slug)
    slug = create_product_slug(payload.name)
    with connect_db() as connection:
        item = connection.execute(
            """
            INSERT INTO products
                (slug, category_slug, name, description, price,
                 package_label, visual_theme, is_demo, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING slug, name, description, price::FLOAT AS price,
                      package_label, visual_theme, image_url, is_demo, active,
                      category_slug
            """,
            (
                slug,
                payload.category_slug,
                payload.name.strip(),
                payload.description.strip(),
                payload.price,
                payload.package_label.strip(),
                payload.visual_theme,
                payload.is_demo,
                payload.active,
            ),
        ).fetchone()
    return item


@app.put("/api/admin/products/{slug}")
def admin_update_product(
    slug: str, payload: ProductPayload, _username: str = Depends(require_admin)
):
    ensure_category_exists(payload.category_slug)
    with connect_db() as connection:
        item = connection.execute(
            """
            UPDATE products
            SET category_slug = %s, name = %s, description = %s, price = %s,
                package_label = %s, visual_theme = %s, is_demo = %s, active = %s
            WHERE slug = %s
            RETURNING slug, name, description, price::FLOAT AS price,
                      package_label, visual_theme, image_url, is_demo, active,
                      category_slug
            """,
            (
                payload.category_slug,
                payload.name.strip(),
                payload.description.strip(),
                payload.price,
                payload.package_label.strip(),
                payload.visual_theme,
                payload.is_demo,
                payload.active,
                slug,
            ),
        ).fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return item


@app.post("/api/admin/products/{slug}/image")
async def admin_upload_product_image(
    slug: str,
    file: UploadFile = File(...),
    _username: str = Depends(require_admin),
):
    contents = await file.read(MAX_PRODUCT_IMAGE_SIZE + 1)
    if len(contents) > MAX_PRODUCT_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="A imagem deve ter até 5 MB.")
    extension = image_extension(contents)
    if not extension:
        raise HTTPException(
            status_code=415, detail="Use uma imagem PNG, JPG ou WebP válida."
        )

    with connect_db() as connection:
        product = connection.execute(
            "SELECT image_url FROM products WHERE slug = %s", (slug,)
        ).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    filename = f"{uuid.uuid4().hex}{extension}"
    image_path = PRODUCT_IMAGES_DIR / filename
    image_url = f"/assets/products/{filename}"
    image_path.write_bytes(contents)
    try:
        with connect_db() as connection:
            updated = connection.execute(
                "UPDATE products SET image_url = %s WHERE slug = %s RETURNING image_url",
                (image_url, slug),
            ).fetchone()
    except Exception:
        image_path.unlink(missing_ok=True)
        raise

    if not updated:
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    remove_product_image(product["image_url"])
    return {"image_url": updated["image_url"]}


@app.delete("/api/admin/products/{slug}/image")
def admin_remove_product_image(slug: str, _username: str = Depends(require_admin)):
    with connect_db() as connection:
        product = connection.execute(
            "SELECT image_url FROM products WHERE slug = %s", (slug,)
        ).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    with connect_db() as connection:
        connection.execute("UPDATE products SET image_url = '' WHERE slug = %s", (slug,))
    remove_product_image(product["image_url"])
    return {"ok": True}


@app.delete("/api/admin/products/{slug}")
def admin_deactivate_product(slug: str, _username: str = Depends(require_admin)):
    with connect_db() as connection:
        item = connection.execute(
            "UPDATE products SET active = FALSE WHERE slug = %s RETURNING slug",
            (slug,),
        ).fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return {"ok": True, "slug": item["slug"]}


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/style.css")
def stylesheet():
    return FileResponse(ROOT / "style.css", media_type="text/css")


@app.get("/script.js")
def javascript():
    return FileResponse(ROOT / "script.js", media_type="text/javascript")


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return FileResponse(ROOT / "admin.html")


@app.get("/admin.css")
def admin_stylesheet():
    return FileResponse(ROOT / "admin.css", media_type="text/css")


@app.get("/admin.js")
def admin_javascript():
    return FileResponse(ROOT / "admin.js", media_type="text/javascript")


app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")
