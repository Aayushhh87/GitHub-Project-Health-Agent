# import os

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv

# from app.api.routes.analysis import router as analysis_router

# load_dotenv()

# app = FastAPI(
#     title="GitHub Project Health Agent",
#     version="0.1.0",
#     description="Evidence-driven GitHub repository health analysis foundation.",
# )

# frontend_origins = [
#     origin.strip()
#     for origin in os.getenv(
#         "FRONTEND_ORIGINS",
#         "http://localhost:3000,http://localhost:5173",
#     ).split(",")
#     if origin.strip()
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=frontend_origins,
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(analysis_router, prefix="/api", tags=["analysis"])


# @app.get("/", tags=["health"])
# def health() -> dict[str, str]:
#     """Return a lightweight service health response."""
#     return {"status": "ok"}


# @app.get("/api/healthz", tags=["health"])
# def healthz() -> dict[str, str]:
#     """Keep a namespaced health route for frontend and proxy checks."""
#     return {"status": "ok"}



import os

from dotenv import load_dotenv

# Load environment variables before importing modules
# that create the GitHub client.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router


app = FastAPI(
    title="GitHub Project Health Agent",
    version="0.1.0",
    description="Evidence-driven GitHub repository health analysis foundation.",
)

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api", tags=["analysis"])


@app.get("/", tags=["health"])
def health() -> dict[str, str]:
    """Return a lightweight service health response."""
    return {"status": "ok"}


@app.get("/api/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    """Keep a namespaced health route for frontend and proxy checks."""
    return {"status": "ok"}
