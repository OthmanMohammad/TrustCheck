"""
Change Detection Services Package

Production-grade change detection for sanctions data with:
- Content hashing and comparison
- Entity-level change detection
- Risk-based classification
- Notification dispatch
- audit trail
"""

from src.services.change_detection.download_manager import AsyncDownloadManager, DownloadResult
from src.services.change_detection.change_detector import AsyncChangeDetector, EntityChange

__all__ = [
    'AsyncDownloadManager',
    'DownloadResult', 
    'AsyncChangeDetector',
    'EntityChange'
]