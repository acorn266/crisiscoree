"""Re-export flood service for backward compatibility."""
from services.flood_service import FloodDetectionService, get_flood_service

__all__ = ["FloodDetectionService", "get_flood_service"]
