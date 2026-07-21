import os
import tempfile

# Изолированная временная БД до импорта ecomed.config.
os.environ["ECOMED_DB_PATH"] = os.path.join(tempfile.gettempdir(), "ecomed_pytest.db")
# Тесты не должны ходить в сеть к LLM: переменная окружения перекрывает .env.
os.environ["OPENAI_API_KEY"] = ""

import pytest

from ecomed.db.database import _engine, get_session
from ecomed.db.models import Base, Household, HouseholdMember, User


@pytest.fixture
def db():
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def household(db) -> int:
    with get_session() as s:
        u = User(email="t@example.com", display_name="Test")
        s.add(u)
        s.flush()
        h = Household(name="Test", owner_id=u.id, city="Алматы")
        s.add(h)
        s.flush()
        s.add(HouseholdMember(household_id=h.id, user_id=u.id, role="owner"))
        hid = h.id
    return hid
