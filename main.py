from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler

from slowapi.errors import RateLimitExceeded
from routers import users, tickets, auth

app = FastAPI()

app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(users.router)
app.include_router(tickets.router)


@app.get("/")
async def root():
    return {"message": "Bienvenidos a SupportDesk Api"}
