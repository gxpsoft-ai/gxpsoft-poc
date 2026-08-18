"""Ingestion package re-exports."""

from gxpsoft.ingestion.service import DuplicateEventError, IngestionService

__all__ = ["IngestionService", "DuplicateEventError"]
