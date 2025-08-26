"""
Notification Service

Simple notification system for sanctions changes.
Sends email alerts and webhook notifications for critical changes.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from enum import Enum

from src.services.change_detection.change_detector import EntityChange

# ======================== NOTIFICATION TYPES ========================

class NotificationPriority(Enum):
    IMMEDIATE = "immediate"      # CRITICAL risk - send now
    BATCH_HIGH = "batch_high"    # HIGH risk - batch within 30 minutes  
    BATCH_LOW = "batch_low"      # MEDIUM/LOW risk - daily digest

class NotificationChannel(Enum):
    EMAIL = "email"
    WEBHOOK = "webhook" 
    SLACK = "slack"
    LOG = "log"

# ======================== NOTIFICATION SERVICE ========================

class NotificationService:
    """
    Simple notification service for sanctions changes.
    
    Features:
    - Risk-based notification routing
    - Multiple notification channels
    - Batching for low-priority changes
    - Comprehensive logging
    
    Note: This is a basic implementation. In production, you'd use
    services like SendGrid, Slack API, etc.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configure notification channels
        self.channels = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.LOG: self._send_log_notification
        }
        
        # Default enabled channels (for basic setup)
        self.enabled_channels = [NotificationChannel.LOG]  # Start with just logging
    
    # ======================== MAIN DISPATCH METHODS ========================
    
    def dispatch_changes(self, changes: List[EntityChange], source: str) -> Dict[str, Any]:
        """
        Dispatch notifications based on change risk levels.
        
        Args:
            changes: List of detected changes
            source: Source name (e.g., 'us_ofac')
            
        Returns:
            Dispatch results with success/failure counts
        """
        if not changes:
            return {'status': 'no_changes', 'sent': 0, 'failed': 0}
        
        # Group changes by priority
        immediate_changes = [c for c in changes if c.risk_level == 'CRITICAL']
        high_priority_changes = [c for c in changes if c.risk_level == 'HIGH']
        low_priority_changes = [c for c in changes if c.risk_level in ['MEDIUM', 'LOW']]
        
        results = {
            'status': 'success',
            'immediate_sent': 0,
            'high_priority_sent': 0,
            'low_priority_queued': len(low_priority_changes),
            'failed': 0,
            'errors': []
        }
        
        # Send immediate alerts for critical changes
        if immediate_changes:
            self.logger.warning(f"🚨 CRITICAL: {len(immediate_changes)} critical sanctions changes detected!")
            
            for change in immediate_changes:
                try:
                    self._send_immediate_alert(change, source)
                    results['immediate_sent'] += 1
                except Exception as e:
                    self.logger.error(f"Failed to send immediate alert: {e}")
                    results['failed'] += 1
                    results['errors'].append(str(e))
        
        # Send high-priority notifications
        if high_priority_changes:
            self.logger.info(f"📋 HIGH PRIORITY: {len(high_priority_changes)} high-risk changes detected")
            
            try:
                self._send_batch_notification(high_priority_changes, source, 'HIGH')
                results['high_priority_sent'] = len(high_priority_changes)
            except Exception as e:
                self.logger.error(f"Failed to send high-priority batch: {e}")
                results['failed'] += len(high_priority_changes)
                results['errors'].append(str(e))
        
        # Queue low-priority for daily digest
        if low_priority_changes:
            self.logger.info(f"📊 LOW PRIORITY: {len(low_priority_changes)} changes queued for daily digest")
            # TODO: Implement actual queuing mechanism
        
        self.logger.info(
            f"Notification dispatch completed for {source}: "
            f"{results['immediate_sent']} immediate, {results['high_priority_sent']} high-priority, "
            f"{results['low_priority_queued']} queued"
        )
        
        return results
    
    # ======================== ALERT SENDING METHODS ========================
    
    def _send_immediate_alert(self, change: EntityChange, source: str) -> None:
        """Send immediate alert for critical change."""
        
        message = self._format_critical_message(change, source)
        
        # Send via all enabled channels
        for channel in self.enabled_channels:
            if channel in self.channels:
                try:
                    self.channels[channel](message, change, 'CRITICAL')
                    self.logger.info(f"Sent immediate alert via {channel.value}")
                except Exception as e:
                    self.logger.error(f"Failed to send via {channel.value}: {e}")
                    raise
    
    def _send_batch_notification(self, changes: List[EntityChange], source: str, priority: str) -> None:
        """Send batch notification for multiple changes."""
        
        message = self._format_batch_message(changes, source, priority)
        
        # Send via enabled channels
        for channel in self.enabled_channels:
            if channel in self.channels:
                try:
                    self.channels[channel](message, changes, priority)
                    self.logger.info(f"Sent batch notification via {channel.value}")
                except Exception as e:
                    self.logger.error(f"Failed to send batch via {channel.value}: {e}")
                    raise
    
    # ======================== MESSAGE FORMATTING ========================
    
    def _format_critical_message(self, change: EntityChange, source: str) -> str:
        """Format critical change alert message."""
        
        action = {
            'ADDED': 'added to',
            'REMOVED': 'removed from', 
            'MODIFIED': 'modified in'
        }.get(change.change_type, 'changed in')
        
        return f"""🚨 CRITICAL SANCTIONS ALERT

Entity: {change.entity_name}
Action: {action} {source.upper()}
Change: {change.change_summary}
Detected: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

⚠️  IMMEDIATE REVIEW REQUIRED FOR COMPLIANCE

This is an automated alert from TrustCheck Sanctions Monitoring System.
"""
    
    def _format_batch_message(self, changes: List[EntityChange], source: str, priority: str) -> str:
        """Format batch notification message."""
        
        change_summary = {}
        for change in changes:
            change_type = change.change_type
            change_summary[change_type] = change_summary.get(change_type, 0) + 1
        
        summary_text = ', '.join([f"{count} {type.lower()}" for type, count in change_summary.items()])
        
        message = f"""📋 {priority} PRIORITY SANCTIONS UPDATE

Source: {source.upper()}
Changes: {summary_text} ({len(changes)} total)
Detected: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

Details:
"""
        
        # Add individual change details
        for i, change in enumerate(changes[:10], 1):  # Limit to first 10
            message += f"{i}. {change.change_summary}\n"
        
        if len(changes) > 10:
            message += f"... and {len(changes) - 10} more changes\n"
        
        message += "\nReview changes in TrustCheck dashboard."
        
        return message
    
    # ======================== CHANNEL IMPLEMENTATIONS ========================
    
    def _send_log_notification(self, message: str, changes, priority: str) -> None:
        """Send notification via logging (always available)."""
        if priority == 'CRITICAL':
            self.logger.critical(message)
        elif priority == 'HIGH':
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def _send_email_notification(self, message: str, changes, priority: str) -> None:
        """Send email notification (placeholder implementation)."""
        # TODO: Implement actual email sending
        # Using SMTP, SendGrid, AWS SES, etc.
        
        self.logger.info(f"EMAIL NOTIFICATION ({priority}):")
        self.logger.info("-" * 50)
        self.logger.info(message)
        self.logger.info("-" * 50)
        
        # Example implementation structure:
        # import smtplib
        # from email.mime.text import MIMEText
        # 
        # msg = MIMEText(message)
        # msg['Subject'] = f'TrustCheck Alert: {priority} Priority Changes'
        # msg['From'] = 'alerts@trustcheck.com'
        # msg['To'] = 'compliance@yourcompany.com'
        # 
        # with smtplib.SMTP('smtp.gmail.com', 587) as server:
        #     server.starttls()
        #     server.login(username, password)
        #     server.send_message(msg)
    
    def _send_webhook_notification(self, message: str, changes, priority: str) -> None:
        """Send webhook notification (placeholder implementation)."""
        # TODO: Implement actual webhook HTTP POST
        
        self.logger.info(f"WEBHOOK NOTIFICATION ({priority}):")
        self.logger.info(f"Would POST to webhook endpoint with payload:")
        
        payload = {
            'source': 'trustcheck',
            'priority': priority,
            'timestamp': datetime.utcnow().isoformat(),
            'message': message,
            'change_count': len(changes) if isinstance(changes, list) else 1,
            'changes': [
                {
                    'entity_name': c.entity_name,
                    'change_type': c.change_type,
                    'risk_level': c.risk_level,
                    'summary': c.change_summary
                }
                for c in (changes if isinstance(changes, list) else [changes])
            ][:5]  # Limit for payload size
        }
        
        self.logger.info(f"Payload: {payload}")
        
        # Example implementation:
        # import requests
        # webhook_url = "https://your-company.com/webhooks/sanctions-alerts"
        # requests.post(webhook_url, json=payload, timeout=10)
    
    def _send_slack_notification(self, message: str, changes, priority: str) -> None:
        """Send Slack notification (placeholder implementation)."""
        # TODO: Implement Slack webhook integration
        
        slack_message = {
            'channel': '#compliance-alerts',
            'username': 'TrustCheck Bot',
            'icon_emoji': ':warning:' if priority == 'CRITICAL' else ':information_source:',
            'text': message
        }
        
        self.logger.info(f"SLACK NOTIFICATION ({priority}):")
        self.logger.info(f"Would send to Slack: {slack_message}")
        
        # Example implementation:
        # import requests
        # slack_webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
        # requests.post(slack_webhook_url, json=slack_message)