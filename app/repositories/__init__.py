"""Repository layer: data access without business rules."""

from app.repositories.base import BaseRepository
from app.repositories.candidate import CandidateRepository
from app.repositories.job import JobRepository
from app.repositories.match import MatchRepository
from app.repositories.note import NoteRepository
from app.repositories.pipeline import PipelineRepository
from app.repositories.user import UserRepository
from app.repositories.webhook import WebhookDeliveryRepository, WebhookRepository

__all__ = [
    "BaseRepository",
    "CandidateRepository",
    "JobRepository",
    "MatchRepository",
    "NoteRepository",
    "PipelineRepository",
    "UserRepository",
    "WebhookDeliveryRepository",
    "WebhookRepository",
]
