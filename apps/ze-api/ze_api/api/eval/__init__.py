from fastapi import APIRouter

from ze_api.api.eval.collisions import router as collisions_router
from ze_api.api.eval.router import router as eval_router
from ze_api.api.eval.routing import router as routing_router
from ze_api.api.v0 import API_V0_PREFIX

dev_router = APIRouter()
dev_router.include_router(eval_router)
dev_router.include_router(collisions_router, prefix=API_V0_PREFIX)
dev_router.include_router(routing_router, prefix=API_V0_PREFIX)
