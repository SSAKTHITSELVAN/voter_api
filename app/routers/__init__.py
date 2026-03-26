from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.buildings import router as buildings_router
from app.routers.households import router as households_router
from app.routers.verification import router as verification_router

__all__ = [
    "auth_router",
    "users_router",
    "buildings_router",
    "households_router",
    "verification_router",
]
