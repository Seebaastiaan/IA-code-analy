"""
Mapa del proyecto (app.analyses.mapa, docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.2): con los repos demo y con
proyectos pequeños de FastAPI, Flask y Django escritos aquí (mismas formas que los repos públicos de §11.2).
"""

import textwrap
from pathlib import Path

from app.analyses import mapa
from tests import demos

SEED = Path(__file__).resolve().parent.parent / "seed_data"


def write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(textwrap.dedent(text), encoding="utf-8")
    return root


def endpoints(mp: mapa.ProjectMap) -> dict[str, mapa.Endpoint]:
    return {f"{e.method} {e.path}": e for e in mp.endpoints}


# ───────────────────────── Repos demo ─────────────────────────


def test_inventario_demo_fastapi():
    mp = mapa.build(demos.combined("inventario_demo"))
    assert (mp.framework, mp.packages, mp.warnings) == ("fastapi", ["inventario"], [])
    eps = endpoints(mp)
    # Prefijo del APIRouter (prefix="/productos") + ruta vacía del decorador
    assert {"POST /productos", "GET /productos", "PATCH /productos/{producto_id}", "DELETE /productos/{producto_id}", "POST /ventas"} <= set(eps)
    # requiere(*CATALOGO) dentro de Depends(...) en un Annotated; la constante vive en el mismo módulo
    assert eps["POST /productos"].roles == ["gerente", "almacenista"] and eps["POST /productos"].auth
    # Alias Annotated importado de otro módulo (Actual = Annotated[Usuario, Depends(usuario_actual)])
    assert eps["GET /productos"].auth and "usuario_actual" in eps["GET /productos"].guards
    # Roles que se revisan dentro del cuerpo (usuario.rol not in PRECIOS)
    assert set(eps["PATCH /productos/{producto_id}"].roles) == {"gerente", "cajero", "almacenista"}
    assert not eps["GET /salud"].auth
    assert mp.roles == ["cajero", "barista", "gerente", "almacenista"]
    assert [m.name for m in mp.models][:3] == ["Usuario", "Producto", "Lote"]
    producto = next(m for m in mp.models if m.name == "Producto")
    assert {c.name for c in producto.fields if c.unique} >= {"sku", "codigo_barras"}
    assert "ProductoNuevo" in {s.name for s in mp.schemas}
    assert [(p.kind, p.name) for p in mp.entry] == [("app", "inventario.main:app")]
    assert ("sesion", "inventario.db:get_db") in {(p.kind, p.name) for p in mp.database}
    assert {p.name for p in mp.auth} == {"inventario.auth:requiere", "inventario.auth:usuario_actual"}
    assert mp.fixtures["tests/reglas/conftest.py"][:3] == ["sesiones", "api", "como"]


def test_reservas_demo_flask():
    mp = mapa.build(demos.combined("reservas_demo"))
    assert mp.framework == "flask"
    eps = endpoints(mp)
    # Rutas de Flask con parámetros (<int:cita_id> → {cita_id}) dentro de la fábrica crear_app()
    assert eps["GET /citas/{cita_id}"].roles == ["cliente", "recepcion", "admin"]
    assert eps["POST /servicios"].roles == ["admin"] and eps["POST /servicios"].auth
    assert not eps["POST /login"].auth
    assert mp.roles == ["cliente", "recepcion", "admin"]
    assert [(p.kind, p.name) for p in mp.entry] == [("factory", "reservas.app:crear_app")]
    # Lo que el arnés sustituye: el correo (smtplib en _entregar) y la hora (reloj.ahora)
    assert [(i.kind, i.functions) for i in mp.integrations] == [("correo", ["reservas.correo:_entregar"])]
    assert [t.function for t in mp.time] == ["reservas.reloj:ahora"]


# ───────────────────────── FastAPI ─────────────────────────


def test_fastapi_routers_anidados_sqlmodel_y_dependencias(tmp_path):
    root = write(tmp_path, {
        "requirements.txt": "fastapi\nsqlmodel\n",
        "app/__init__.py": "",
        "app/main.py": """
            from fastapi import FastAPI
            from app.api.main import api_router
            app = FastAPI()
            app.include_router(api_router, prefix="/api/v1")
        """,
        "app/api/__init__.py": "",
        "app/api/main.py": """
            from fastapi import APIRouter
            from app.api.routes import items, users
            api_router = APIRouter()
            api_router.include_router(items.router)
            api_router.include_router(users.router, prefix="/users")
        """,
        "app/api/deps.py": """
            from typing import Annotated
            from fastapi import Depends
            def get_db():
                yield None
            def get_current_user(): ...
            def get_current_active_superuser(): ...
            SessionDep = Annotated[object, Depends(get_db)]
            CurrentUser = Annotated[object, Depends(get_current_user)]
        """,
        "app/api/routes/__init__.py": "",
        "app/api/routes/items.py": """
            from fastapi import APIRouter, Depends
            from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
            router = APIRouter(prefix="/items", tags=["items"])
            @router.get("/")
            def read_items(session: SessionDep, current_user: CurrentUser): ...
            @router.delete("/{id}", dependencies=[Depends(get_current_active_superuser)])
            def delete_item(id: int, session: SessionDep): ...
        """,
        "app/api/routes/users.py": """
            from fastapi import APIRouter
            router = APIRouter()
            @router.post("/signup")
            def register_user(): ...
        """,
        "app/models.py": """
            import uuid
            from sqlmodel import Field, SQLModel
            class ItemBase(SQLModel):
                title: str = Field(min_length=1, max_length=255)
                description: str | None = None
            class ItemCreate(ItemBase):
                pass
            class Item(ItemBase, table=True):
                id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
                owner_id: uuid.UUID = Field(foreign_key="user.id")
        """,
    })
    mp = mapa.build(root)
    eps = endpoints(mp)
    assert set(eps) == {"GET /api/v1/items/", "DELETE /api/v1/items/{id}", "POST /api/v1/users/signup"}
    assert eps["GET /api/v1/items/"].auth and eps["DELETE /api/v1/items/{id}"].auth
    assert not eps["POST /api/v1/users/signup"].auth
    # SQLModel con table=True es modelo (con los campos de su base); sin table=True es esquema
    item = next(m for m in mp.models if m.name == "Item")
    assert (item.kind, [c.name for c in item.fields]) == ("sqlmodel", ["title", "description", "id", "owner_id"])
    assert next(c for c in item.fields if c.name == "owner_id").foreign_key == "user.id"
    assert {"ItemBase", "ItemCreate"} <= {s.name for s in mp.schemas}
    assert ("sesion", "app.api.deps:get_db") in {(p.kind, p.name) for p in mp.database}


def test_sintaxis_de_python_314_se_lee(tmp_path):
    # PEP 758: `except A, B:` sin paréntesis (el backend corre en 3.12)
    root = write(tmp_path, {
        "requirements.txt": "fastapi\n",
        "api.py": """
            from fastapi import FastAPI
            app = FastAPI()
            @app.get("/salud")
            def salud():
                try:
                    return {"ok": True}
                except ValueError, KeyError:
                    return {"ok": False}
        """,
        "roto.py": "def (:\n",
    })
    mp = mapa.build(root)
    assert list(endpoints(mp)) == ["GET /salud"]
    assert mp.warnings == ["1 archivo(s) de Python no se pudieron leer (error de sintaxis)."]


# ───────────────────────── Flask ─────────────────────────


def test_flask_blueprints_importados_y_login_required(tmp_path):
    root = write(tmp_path, {
        "requirements.txt": "flask\nflask-sqlalchemy\nflask-login\n",
        "app/__init__.py": """
            from flask import Flask
            from flask_sqlalchemy import SQLAlchemy
            db = SQLAlchemy()
            def create_app():
                app = Flask(__name__)
                from app.main import bp as main_bp
                app.register_blueprint(main_bp)
                from app.api import bp as api_bp
                app.register_blueprint(api_bp, url_prefix="/api")
                return app
        """,
        "app/main/__init__.py": """
            from flask import Blueprint
            bp = Blueprint("main", __name__)
        """,
        "app/main/routes.py": """
            from flask_login import login_required, current_user
            from app.main import bp
            @bp.route("/", methods=["GET", "POST"])
            @login_required
            def index(): ...
            @bp.route("/admin")
            @login_required
            def admin():
                if current_user.role != "admin":
                    return "no", 403
        """,
        "app/api/__init__.py": """
            from flask import Blueprint
            bp = Blueprint("api", __name__)
        """,
        "app/api/users.py": """
            from app.api import bp
            @bp.route("/users/<int:id>", methods=["GET"])
            def get_user(id): ...
        """,
        "app/models.py": """
            from app import db
            class User(db.Model):
                id = db.Column(db.Integer, primary_key=True)
                email = db.Column(db.String(120), unique=True, nullable=False)
        """,
        "tests.py": "import unittest\n",
    })
    mp = mapa.build(root)
    eps = endpoints(mp)
    assert set(eps) == {"GET /", "POST /", "GET /admin", "GET /api/users/{id}"}
    assert eps["GET /"].auth and eps["GET /"].guards == ["login_required"]
    assert eps["GET /admin"].roles == ["admin"]
    assert not eps["GET /api/users/{id}"].auth
    assert [(p.kind, p.name) for p in mp.entry] == [("factory", "app:create_app")]
    user = next(m for m in mp.models if m.name == "User")
    assert user.kind == "sqlalchemy" and next(c for c in user.fields if c.name == "email").unique
    # tests.py no es un paquete del proyecto
    assert mp.packages == ["app"]


# ───────────────────────── Django / DRF ─────────────────────────


def test_django_drf_router_include_y_modelos_abstractos(tmp_path):
    root = write(tmp_path, {
        "requirements.txt": "Django\ndjangorestframework\n",
        "manage.py": """
            import os
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
        """,
        "main/__init__.py": "",
        "main/settings.py": 'ROOT_URLCONF = "main.urls"\nDATABASES = {}\n',
        "main/urls.py": """
            from django.urls import include, path
            urlpatterns = [path("stock/", include("stock.urls")), path("account/", include("account.urls"))]
        """,
        "stock/__init__.py": "",
        "stock/urls.py": """
            from rest_framework import routers
            from .views import ProductView
            router = routers.DefaultRouter()
            router.register("product", ProductView)
            urlpatterns = [] + router.urls
        """,
        "stock/views.py": """
            from rest_framework import viewsets
            from rest_framework.decorators import action
            from .models import Product
            from .permissions import SoloAlmacen
            class ProductView(viewsets.ModelViewSet):
                queryset = Product.objects.all()
                permission_classes = [SoloAlmacen]
                @action(detail=True, methods=["post"])
                def ajustar(self, request, pk=None): ...
        """,
        "stock/permissions.py": """
            from rest_framework.permissions import BasePermission
            class SoloAlmacen(BasePermission):
                def has_permission(self, request, view):
                    return request.user.groups.filter(name="almacen").exists() or request.user.role == "gerente"
        """,
        "stock/models.py": """
            from django.db import models
            class Auditado(models.Model):
                creado = models.DateTimeField(auto_now_add=True)
                class Meta:
                    abstract = True
            class Product(Auditado):
                sku = models.CharField(max_length=20, unique=True)
                stock = models.PositiveIntegerField(default=0)
        """,
        "account/__init__.py": "",
        "account/urls.py": """
            from django.urls import path
            from .views import RegisterView
            urlpatterns = [path("register/", RegisterView.as_view())]
        """,
        "account/views.py": """
            from rest_framework.generics import CreateAPIView
            class RegisterView(CreateAPIView): ...
        """,
    })
    mp = mapa.build(root)
    assert mp.framework == "django"
    eps = endpoints(mp)
    assert {"GET /stock/product/", "POST /stock/product/", "DELETE /stock/product/{pk}/", "POST /stock/product/{pk}/ajustar/", "POST /account/register/"} <= set(eps)
    assert eps["GET /stock/product/"].auth and eps["GET /stock/product/"].guards == ["SoloAlmacen"]
    # Grupo de Django y comparación con el rol, dentro de la clase de permiso
    assert set(eps["GET /stock/product/"].roles) == set(mp.roles) == {"almacen", "gerente"}
    assert not eps["POST /account/register/"].auth
    # La abstracta no es tabla; Product hereda su campo
    assert [(m.name, [c.name for c in m.fields]) for m in mp.models] == [("Product", ["creado", "sku", "stock"])]
    assert [(p.kind, p.name) for p in mp.entry] == [("settings", "main.settings")]


def test_sin_framework(tmp_path):
    mp = mapa.build(write(tmp_path, {"calc.py": "def suma(a, b):\n    return a + b\n"}))
    assert mp.empty and mp.framework is None
    assert "No se reconoció FastAPI, Flask ni Django" in mp.warnings[0]


# ───────────────────────── Código en una subcarpeta ─────────────────────────

BACKEND = {
    "README.md": "# app",
    "frontend/package.json": "{}",
    "backend/requirements.txt": "fastapi\n",
    "backend/main.py": """
        from fastapi import FastAPI
        from agents.rutas import router

        app = FastAPI()
        app.include_router(router)
    """,
    "backend/agents/__init__.py": "",
    "backend/agents/rutas.py": """
        from fastapi import APIRouter

        router = APIRouter(prefix="/productos")


        @router.get("")
        def listar():
            return []
    """,
}


def test_codigo_en_una_subcarpeta_se_importa_sin_el_prefijo(tmp_path):
    # Pasó con eugen-goebel/inventory-management: `from agents.x import y` parecía un módulo inexistente
    write(tmp_path, BACKEND)
    mp = mapa.build(tmp_path)
    assert mp.source_root == "backend" and mp.framework == "fastapi"
    assert mp.packages == ["agents", "main"]
    assert "GET /productos" in endpoints(mp)
    # Las rutas del mapa siguen siendo las del repo (el editor y las evidencias las leen desde la raíz)
    assert {e.file for e in mp.endpoints} == {"backend/agents/rutas.py"}
    assert mapa.find_source_root(tmp_path) == "backend"


def test_raiz_del_codigo_solo_si_es_inequivoca(tmp_path):
    assert mapa.source_root(["requirements.txt", "backend/requirements.txt"]) == ""
    assert mapa.source_root(["backend/requirements.txt", "api/pyproject.toml"]) == ""
    # Con la carpeta a la vista, la que declara un framework web gana; si las dos lo declaran, ninguna
    write(tmp_path, {"api/requirements.txt": "fastapi\n", "worker/requirements.txt": "celery\n", "api/main.py": "x = 1"})
    assert mapa.find_source_root(tmp_path) == "api" and mapa.build(tmp_path).source_root == "api"
    write(tmp_path, {"worker/requirements.txt": "flask\n"})
    assert mapa.find_source_root(tmp_path) == ""
    assert mapa.source_root(["backend/main.py"]) == ""
    assert mapa.source_root([".github/pyproject.toml", "app/manage.py"]) == "app"
    write(tmp_path, {"main.py": "x = 1", "requirements.txt": ""})
    assert mapa.find_source_root(tmp_path) == "" and mapa.build(tmp_path).source_root == ""
