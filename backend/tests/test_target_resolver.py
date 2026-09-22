from datetime import datetime

from sqlalchemy.orm import Session

from app.application.target_resolver import TargetResolver
from app.core.errors import AppError
from app.infrastructure.repositories import Repositories
import pytest


def _seed(repos: Repositories, session: Session):
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    repos.calendars.put({"id": "c1", "name": "Local", "timezone": "UTC", "createdAt": now, "updatedAt": now})
    repos.tasks.put(
        {
            "id": "t1",
            "calendarId": "c1",
            "title": "Buy milk",
            "completed": False,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    repos.tasks.put(
        {
            "id": "t2",
            "calendarId": "c1",
            "title": "Buy bread",
            "completed": False,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    session.commit()


def test_resolve_single_target(db_session: Session):
    repos = Repositories(db_session)
    _seed(repos, db_session)
    resolved = TargetResolver(db_session).resolve({"entityType": "task", "query": "milk"})
    assert resolved["id"] == "t1"


def test_resolve_full_sentence_query(db_session: Session):
    repos = Repositories(db_session)
    _seed(repos, db_session)
    resolved = TargetResolver(db_session).resolve(
        {"entityType": "task", "query": "удали задачу Buy milk пожалуйста"}
    )
    assert resolved["id"] == "t1"


def test_ambiguous_target(db_session: Session):
    repos = Repositories(db_session)
    _seed(repos, db_session)
    with pytest.raises(AppError) as raised:
        TargetResolver(db_session).resolve({"entityType": "task", "query": "buy"})
    assert raised.value.code == "ambiguous_target"
