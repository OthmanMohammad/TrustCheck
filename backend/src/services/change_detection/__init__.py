"""
Change Detection Services Package

Production-grade change detection for sanctions data with:
- Content hashing and comparison
- Entity-level change detection
- Risk-based classification
- Notification dispatch
- audit trail
"""

from src.services.change_detection.download_manager import DownloadManager, DownloadResult
from src.services.change_detection.change_detector import ChangeDetector, EntityChange

__all__ = [
    'DownloadManager',
    'DownloadResult', 
    'ChangeDetector',
    'EntityChange'
]