from fastapi import APIRouter, Depends

from oom.app.dependencies import get_memory_core
from oom.memory_core.core import MemoryCore
from oom.memory_core.types import ConversationSearchRequest, ConversationSearchResult, MemorySearchRequest, MemorySearchResult

router = APIRouter()


@router.post("/conversations/search", response_model=ConversationSearchResult)
async def search_conversations(
    request: ConversationSearchRequest, core: MemoryCore = Depends(get_memory_core)
) -> ConversationSearchResult:
    return await core.search_conversations(request)


@router.post("/memories/search", response_model=MemorySearchResult)
async def search_memories(request: MemorySearchRequest, core: MemoryCore = Depends(get_memory_core)) -> MemorySearchResult:
    return await core.search_memories(request)
