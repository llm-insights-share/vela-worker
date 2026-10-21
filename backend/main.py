import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import init_db, SessionLocal
from seed import seed_if_empty
from config import PUSH_LOOP_INTERVAL
from auth_config import AVATAR_DIR, PROJECT_DOCS_DIR

from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.roles import router as roles_router
from routes.workers import router as workers_router
from routes.duties import router as duties_router
from routes.org import router as org_router
from routes.catalog import router as catalog_router
from routes.conversations import router as conversations_router
from routes.messages import router as messages_router
from routes.tasks import router as tasks_router, ws_router
from routes.open_api import apps_router, open_router
from routes.push import router as push_router
from routes.inbox import router as inbox_router
from routes.projects import router as projects_router
from routes.ops_assistant import router as ops_assistant_router


async def _webhook_loop():
    from services.webhook_dispatcher import process_pending_webhooks
    while True:
        try:
            db = SessionLocal()
            try:
                process_pending_webhooks(db)
            finally:
                db.close()
        except Exception as e:
            print(f"[webhook_loop] {e}")
        await asyncio.sleep(30)


async def _push_loop():
    from services.push_service import process_due_cron_rules
    while True:
        try:
            db = SessionLocal()
            try:
                await process_due_cron_rules(db)
            finally:
                db.close()
        except Exception as e:
            print(f"[push_loop] {e}")
        await asyncio.sleep(PUSH_LOOP_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        # Bootstrap org/users only — demo/scenario seeds are disabled
        seed_if_empty(db)
    finally:
        db.close()
    webhook_task = asyncio.create_task(_webhook_loop())
    push_task = asyncio.create_task(_push_loop())
    yield
    for t in (webhook_task, push_task):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Vela Worker API",
    description="AI Agent 数字员工服务",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(workers_router)
app.include_router(duties_router)
app.include_router(org_router)
app.include_router(catalog_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(tasks_router)
app.include_router(ws_router)
app.include_router(apps_router)
app.include_router(open_router)
app.include_router(push_router)
app.include_router(inbox_router)
app.include_router(projects_router)
app.include_router(ops_assistant_router)

AVATAR_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=str(AVATAR_DIR)), name="avatars")
app.mount("/project-docs", StaticFiles(directory=str(PROJECT_DOCS_DIR)), name="project-docs")


@app.get("/api/v1/health")
def health():
    from services.vela_agent_client import vela_agent_client
    return {
        "status": "ok",
        "service": "Vela Worker",
        "vela_agent": vela_agent_client.check_health(),
    }
