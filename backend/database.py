import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'worker.db')}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # lightweight additive migrations for sqlite
    with engine.begin() as conn:
        duty_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(duties)").fetchall()}
        if "template_agent_id" not in duty_cols:
            conn.exec_driver_sql("ALTER TABLE duties ADD COLUMN template_agent_id VARCHAR DEFAULT ''")
        if "template_agent_name" not in duty_cols:
            conn.exec_driver_sql("ALTER TABLE duties ADD COLUMN template_agent_name VARCHAR(256) DEFAULT ''")
        worker_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(digital_workers)").fetchall()}
        if "entry_agent_id" not in worker_cols:
            conn.exec_driver_sql("ALTER TABLE digital_workers ADD COLUMN entry_agent_id VARCHAR DEFAULT ''")
        if "reception_agent_id" not in worker_cols:
            conn.exec_driver_sql("ALTER TABLE digital_workers ADD COLUMN reception_agent_id VARCHAR DEFAULT ''")
        user_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(human_users)").fetchall()}
        if "username" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE human_users ADD COLUMN username VARCHAR(64)")
        if "email" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE human_users ADD COLUMN email VARCHAR(256)")
        if "hashed_password" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE human_users ADD COLUMN hashed_password VARCHAR(256)")
        if "updated_at" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE human_users ADD COLUMN updated_at DATETIME")
        task_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(work_tasks)").fetchall()}
        if task_cols:
            if "project_id" not in task_cols:
                conn.exec_driver_sql("ALTER TABLE work_tasks ADD COLUMN project_id VARCHAR")
            if "item_id" not in task_cols:
                conn.exec_driver_sql("ALTER TABLE work_tasks ADD COLUMN item_id VARCHAR")
            if "progress_pct" not in task_cols:
                conn.exec_driver_sql("ALTER TABLE work_tasks ADD COLUMN progress_pct INTEGER DEFAULT 0")
            if "progress_steps" not in task_cols:
                conn.exec_driver_sql("ALTER TABLE work_tasks ADD COLUMN progress_steps JSON DEFAULT '[]'")
        project_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(projects)").fetchall()}
        if project_cols:
            if "start_date" not in project_cols:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN start_date DATE")
            if "end_date" not in project_cols:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN end_date DATE")
        item_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(project_items)").fetchall()}
        if item_cols:
            if "planned_start" not in item_cols:
                conn.exec_driver_sql("ALTER TABLE project_items ADD COLUMN planned_start DATETIME")
            if "planned_end" not in item_cols:
                conn.exec_driver_sql("ALTER TABLE project_items ADD COLUMN planned_end DATETIME")
            if "completed_at" not in item_cols:
                conn.exec_driver_sql("ALTER TABLE project_items ADD COLUMN completed_at DATETIME")
