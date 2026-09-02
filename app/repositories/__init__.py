"""Repository layer: data access without business rules."""

from app.repositories.base import BaseRepository
from app.repositories.candidate import CandidateRepository
from app.repositories.job import JobRepository
from app.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "CandidateRepository",
    "JobRepository",
    "UserRepository",
]
