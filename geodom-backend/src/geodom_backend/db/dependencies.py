from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.session import get_db_session

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session)
]
