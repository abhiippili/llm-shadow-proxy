from abc import ABC, abstractmethod
from app.models.domain.mismatch import Mismatch


class IMismatchRepository(ABC):
    @abstractmethod
    async def create(self, mismatch: Mismatch) -> Mismatch: ...

    @abstractmethod
    async def get_recent(self, limit: int = 20) -> list[Mismatch]: ...

    @abstractmethod
    async def count(self) -> int: ...
