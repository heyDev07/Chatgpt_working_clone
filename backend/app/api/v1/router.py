from fastapi import APIRouter

from app.api.v1 import auth, conversations, documents, folders, memories, messages, tags, tools

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(memories.router)
api_router.include_router(documents.router)
api_router.include_router(tools.router)
api_router.include_router(folders.router)
api_router.include_router(tags.router)
