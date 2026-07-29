from fastapi import APIRouter

from app.api.v1 import (
    admin,
    attachments,
    auth,
    contacts,
    conversations,
    documents,
    folders,
    memories,
    messages,
    oauth,
    reminders,
    shared,
    tags,
    tools,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(attachments.router)
api_router.include_router(memories.router)
api_router.include_router(documents.router)
api_router.include_router(tools.router)
api_router.include_router(folders.router)
api_router.include_router(tags.router)
api_router.include_router(reminders.router)
api_router.include_router(contacts.router)
api_router.include_router(oauth.router)
api_router.include_router(shared.router)
api_router.include_router(admin.router)
