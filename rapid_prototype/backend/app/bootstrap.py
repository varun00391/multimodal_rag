from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.auth import hash_password
from app.seed import seed_demo_user


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "demo@nexus.ai").first():
            user = User(
                email="demo@nexus.ai",
                name="Ada Chen",
                hashed_password=hash_password("demo1234"),
                settings_json='{"default_model": "gpt-4o-mini"}',
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            seed_demo_user(db, user)
    finally:
        db.close()
