"""
Demo chat is handled by app/public/router.py at POST /demo/chat
(registered without a prefix, so it wins the route-match order).
This module is kept so main.py's include_router call doesn't break,
but it registers no additional routes.
"""
from fastapi import APIRouter

router = APIRouter()
