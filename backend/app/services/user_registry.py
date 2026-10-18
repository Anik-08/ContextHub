import uuid

from sqlmodel import Session, select

from app.models.db_models import User
from app.services.document_registry import engine
from app.services.security import hash_password


def create_user(email: str, password: str, name: str | None = None) -> User:
    with Session(engine) as session:
        if session.exec(select(User).where(User.email == email)).first():
            raise ValueError("An account with this email already exists.")

        user = User(
            user_id=str(uuid.uuid4()),
            email=email.lower(),
            password_hash=hash_password(password),
            name=name or email.split("@")[0],
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def get_user_by_email(email: str) -> User | None:
    with Session(engine) as session:
        return session.exec(select(User).where(User.email == email.lower())).first()


def get_user_by_id(user_id: str) -> User | None:
    with Session(engine) as session:
        return session.get(User, user_id)
