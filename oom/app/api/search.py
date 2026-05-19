from fastapi import APIRouter, Depends

from only_one_memory.app.dependencies import get_memory_core
from only_one_memory.memory_core.core import MemoryCore
from only_one_memory.memory_core.types import ConversationSearchRequest, ConversationSearchResult

router = APIRouter()


@router.post("/conversations/search", response_model=ConversationSearchResult)
async def search_conversations(
    request: ConversationSearchRequest, core: MemoryCore = Depends(get_memory_core)
) -> ConversationSearchResult:
    return await core.search_conversations(request)
