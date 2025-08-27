"""
Notification Service - Complete Implementation

Handles notifications for sanctions changes with multiple channels and risk-based routing.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from src.core.domain.entities import ChangeEventDomain
from src.core.enums import RiskLevel, NotificationChannel, NotificationPriority
from src.core.logging_config import get_logger
from src.core.exceptions import BusinessLogicError, handle_exception

logger = get_logger(__name__)

# ======================== NOTIFICATION SERVICE ========================

class NotificationService:
    """
    Comprehensive notification service for sanctions changes.
    
    Features:
    - Risk-based notification routing
    - Multiple notification channels (email, webhook, Slack, log)
    - Batching for low-priority changes
    - Comprehensive logging and error handling
    - Extensible channel system
    
    Note: This implementation includes basic channel handlers.
    In production, integrate with actual services (SendGrid, Slack API, etc.)
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Configure notification channels
        self.channels = {
            NotificationChannel.EMAIL: self._send_email_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.LOG: self._send_log_notification
        }
        
        # Default enabled channels (for basic setup)
        self.enabled_channels = [
            NotificationChannel.LOG,
            NotificationChannel.EMAIL  # Add EMAIL for production
        ]
        
        # Channel configuration (would come from settings in production)
        self.config = {
            'email': {
                'smtp_server': 'smtp.company.com',
                'recipients': ['compliance@company.com', 'alerts@company.com'],
                'from_email': 'trustcheck-alerts@company.com'
            },
            'webhook': {
                'url': 'https://company.com/webhooks/sanctions-alerts',
                'timeout': 10,
                'retry_count': 3
            },
            'slack': {
                'webhook_url': 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK',
                'channel': '#compliance-alerts'
            }
        }
    
    # ======================== MAIN DISPATCH METHODS ========================
    
    async def dispatch_changes(self, changes: List[ChangeEventDomain], source: str) -> Dict[str, Any]:
        """
        Dispatch notifications based on change risk levels.
        
        Args:
            changes: List of detected changes
            source: Source name (e.g., 'OFAC', 'UN')
            
        Returns:
            Dispatch results with success/failure counts
        """
        if not changes:
            return {'status': 'no_changes', 'sent': 0, 'failed': 0}
        
        # Group changes by priority
        immediate_changes = [c for c in changes if c.risk_level == RiskLevel.CRITICAL]
        high_priority_changes = [c for c in changes if c.risk_level == RiskLevel.HIGH]
        low_priority_changes = [c for c in changes if c.risk_level in [RiskLevel.MEDIUM, RiskLevel.LOW]]
        
        results = {
            'status': 'success',
            'immediate_sent': 0,
            'high_priority_sent': 0,
            'low_priority_queued': len(low_priority_changes),
            'failed': 0,
            'errors': []
        }
        
        try:
            # Send immediate alerts for critical changes
            if immediate_changes:
                self.logger.warning(f"🚨 CRITICAL: {len(immediate_changes)} critical sanctions changes detected!")
                
                for change in immediate_changes:
                    try:
                        await self._send_immediate_alert(change, source)
                        results['immediate_sent'] += 1
                    except Exception as e:
                        self.logger.error(f"Failed to send immediate alert: {e}")
                        results['failed'] += 1
                        results['errors'].append(str(e))
            
            # Send high-priority notifications
            if high_priority_changes:
                self.logger.info(f"📋 HIGH PRIORITY: {len(high_priority_changes)} high-risk changes detected")
                
                try:
                    await self._send_batch_notification(high_priority_changes, source, 'HIGH')
                    results['high_priority_sent'] = len(high_priority_changes)
                except Exception as e:
                    self.logger.error(f"Failed to send high-priority batch: {e}")
                    results['failed'] += len(high_priority_changes)
                    results['errors'].append(str(e))
            
            # Queue low-priority for daily digest
            if low_priority_changes:
                self.logger.info(f"📊 LOW PRIORITY: {len(low_priority_changes)} changes queued for daily digest")
                await self._queue_daily_digest(low_priority_changes, source)
            
            self.logger.info(
                f"Notification dispatch completed for {source}: "
                f"{results['immediate_sent']} immediate, {results['high_priority_sent']} high-priority, "
                f"{results['low_priority_queued']} queued"
            )
            
            return results
            
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "dispatch_changes",
                "source": source,
                "changes_count": len(changes)
            })
            raise BusinessLogicError("Notification dispatch failed", cause=e) from error
    
    async def send_daily_digest(self, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Send daily digest of accumulated low-priority changes.
        
        Args:
            source: Optional source filter
            
        Returns:
            Dict with digest results
        """
        try:
            self.logger.info("Preparing daily sanctions digest...")
            
            # In production, this would query queued changes from database
            # For now, return placeholder implementation
            
            digest_data = {
                'date': datetime.utcnow().strftime('%Y-%m-%d'),
                'total_changes': 0,
                'by_source': {},
                'by_risk_level': {}
            }
            
            if digest_data['total_changes'] > 0:
                message = self._format_digest_message(digest_data)
                
                # Send via enabled channels
                for channel in self.enabled_channels:
                    if channel in self.channels:
                        await self.channels[channel](message, [], 'DIGEST')
                
                self.logger.info(f"Daily digest sent: {digest_data['total_changes']} changes")
            else:
                self.logger.info("No changes for daily digest")
            
            return {
                'status': 'success',
                'digest_sent': digest_data['total_changes'] > 0,
                'changes_count': digest_data['total_changes']
            }
            
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "send_daily_digest",
                "source": source
            })
            raise BusinessLogicError("Daily digest failed", cause=e) from error
    
    # ======================== ALERT SENDING METHODS ========================
    
    async def _send_immediate_alert(self, change: ChangeEventDomain, source: str) -> None:
        """Send immediate alert for critical change."""
        
        message = self._format_critical_message(change, source)
        
        # Send via all enabled channels
        for channel in self.enabled_channels:
            if channel in self.channels:
                try:
                    await self.channels[channel](message, change, 'CRITICAL')
                    self.logger.info(f"Sent immediate alert via {channel.value}")
                except Exception as e:
                    self.logger.error(f"Failed to send via {channel.value}: {e}")
                    raise
    
    async def _send_batch_notification(self, changes: List[ChangeEventDomain], source: str, priority: str) -> None:
        """Send batch notification for multiple changes."""
        
        message = self._format_batch_message(changes, source, priority)
        
        # Send via enabled channels
        for channel in self.enabled_channels:
            if channel in self.channels:
                try:
                    await self.channels[channel](message, changes, priority)
                    self.logger.info(f"Sent batch notification via {channel.value}")
                except Exception as e:
                    self.logger.error(f"Failed to send batch via {channel.value}: {e}")
                    raise
    
    async def _queue_daily_digest(self, changes: List[ChangeEventDomain], source: str) -> None:
        """Queue changes for daily digest."""
        # In production, this would store changes in database queue
        self.logger.info(f"Queued {len(changes)} changes for daily digest from {source}")
    
    # ======================== MESSAGE FORMATTING ========================
    
    def _format_critical_message(self, change: ChangeEventDomain, source: str) -> str:
        """Format critical change alert message."""
        
        action = {
            'ADDED': 'added to',
            'REMOVED': 'removed from', 
            'MODIFIED': 'modified in'
        }.get(change.change_type.value, 'changed in')
        
        return f"""🚨 CRITICAL SANCTIONS ALERT

Entity: {change.entity_name}
Action: {action} {source.upper()} sanctions list
Change: {change.change_summary}
Detected: {change.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
Risk Level: {change.risk_level.value}

⚠️  IMMEDIATE REVIEW REQUIRED FOR COMPLIANCE

Field Changes:
{self._format_field_changes(change.field_changes) if change.field_changes else 'No specific field changes recorded'}

This is an automated alert from TrustCheck Sanctions Monitoring System.
Review changes immediately to ensure compliance requirements are met.
"""
    
    def _format_batch_message(self, changes: List[ChangeEventDomain], source: str, priority: str) -> str:
        """Format batch notification message."""
        
        change_summary = {}
        for change in changes:
            change_type = change.change_type.value
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
            message += f"{i}. {change.change_summary} (Risk: {change.risk_level.value})\n"
        
        if len(changes) > 10:
            message += f"... and {len(changes) - 10} more changes\n"
        
        message += "\nReview all changes in TrustCheck dashboard for complete details."
        
        return message
    
    def _format_digest_message(self, digest_data: Dict[str, Any]) -> str:
        """Format daily digest message."""
        
        message = f"""📊 DAILY SANCTIONS DIGEST - {digest_data['date']}

Summary: {digest_data['total_changes']} total changes processed

By Source:
"""
        
        for source, count in digest_data.get('by_source', {}).items():
            message += f"  • {source}: {count} changes\n"
        
        message += "\nBy Risk Level:\n"
        for risk_level, count in digest_data.get('by_risk_level', {}).items():
            message += f"  • {risk_level}: {count} changes\n"
        
        message += "\nAccess the TrustCheck dashboard for detailed change analysis."
        
        return message
    
    def _format_field_changes(self, field_changes: List) -> str:
        """Format field changes for display."""
        if not field_changes:
            return "No field changes"
        
        formatted = []
        for change in field_changes:
            if hasattr(change, 'field_name'):
                formatted.append(f"  • {change.field_name}: {change.old_value} → {change.new_value}")
            else:
                # Handle dict format
                formatted.append(f"  • {change.get('field_name', 'Unknown')}: {change.get('old_value', 'N/A')} → {change.get('new_value', 'N/A')}")
        
        return "\n".join(formatted)
    
    # ======================== CHANNEL IMPLEMENTATIONS ========================
    
    async def _send_log_notification(self, message: str, changes, priority: str) -> None:
        """Send notification via logging (always available)."""
        if priority == 'CRITICAL':
            self.logger.critical(message)
        elif priority == 'HIGH':
            self.logger.warning(message)
        elif priority == 'DIGEST':
            self.logger.info(f"DAILY DIGEST:\n{message}")
        else:
            self.logger.info(message)
    
    async def _send_email_notification(self, message: str, changes, priority: str) -> None:
        """Send email notification."""
        try:
            # TODO: Implement actual email sending using SMTP/SendGrid/SES
            # This is a placeholder implementation
            
            subject = self._get_email_subject(priority, len(changes) if isinstance(changes, list) else 1)
            
            # Log the email that would be sent
            self.logger.info(f"EMAIL NOTIFICATION ({priority}):")
            self.logger.info(f"To: {', '.join(self.config['email']['recipients'])}")
            self.logger.info(f"Subject: {subject}")
            self.logger.info("-" * 50)
            self.logger.info(message)
            self.logger.info("-" * 50)
            
            # Example implementation structure:
            # import smtplib
            # from email.mime.text import MIMEText
            # from email.mime.multipart import MIMEMultipart
            # 
            # msg = MIMEMultipart()
            # msg['Subject'] = subject
            # msg['From'] = self.config['email']['from_email']
            # msg['To'] = ', '.join(self.config['email']['recipients'])
            # 
            # msg.attach(MIMEText(message, 'plain'))
            # 
            # with smtplib.SMTP(self.config['email']['smtp_server'], 587) as server:
            #     server.starttls()
            #     server.login(username, password)
            #     server.send_message(msg)
            
        except Exception as e:
            self.logger.error(f"Email notification failed: {e}")
            raise
    
    async def _send_webhook_notification(self, message: str, changes, priority: str) -> None:
        """Send webhook notification."""
        try:
            # TODO: Implement actual webhook HTTP POST
            
            payload = {
                'source': 'trustcheck',
                'priority': priority,
                'timestamp': datetime.utcnow().isoformat(),
                'message': message,
                'change_count': len(changes) if isinstance(changes, list) else 1,
                'changes': self._serialize_changes_for_webhook(changes)
            }
            
            self.logger.info(f"WEBHOOK NOTIFICATION ({priority}):")
            self.logger.info(f"URL: {self.config['webhook']['url']}")
            self.logger.info(f"Payload: {payload}")
            
            # Example implementation:
            # import requests
            # 
            # response = requests.post(
            #     self.config['webhook']['url'],
            #     json=payload,
            #     timeout=self.config['webhook']['timeout']
            # )
            # response.raise_for_status()
            
        except Exception as e:
            self.logger.error(f"Webhook notification failed: {e}")
            raise
    
    async def _send_slack_notification(self, message: str, changes, priority: str) -> None:
        """Send Slack notification."""
        try:
            # TODO: Implement Slack webhook integration
            
            slack_message = {
                'channel': self.config['slack']['channel'],
                'username': 'TrustCheck Bot',
                'icon_emoji': self._get_slack_emoji(priority),
                'text': message,
                'attachments': self._create_slack_attachments(changes, priority)
            }
            
            self.logger.info(f"SLACK NOTIFICATION ({priority}):")
            self.logger.info(f"Channel: {self.config['slack']['channel']}")
            self.logger.info(f"Message: {slack_message}")
            
            # Example implementation:
            # import requests
            # 
            # response = requests.post(
            #     self.config['slack']['webhook_url'],
            #     json=slack_message,
            #     timeout=10
            # )
            # response.raise_for_status()
            
        except Exception as e:
            self.logger.error(f"Slack notification failed: {e}")
            raise
    
    # ======================== HELPER METHODS ========================
    
    def _get_email_subject(self, priority: str, change_count: int) -> str:
        """Generate email subject based on priority."""
        if priority == 'CRITICAL':
            return f"🚨 CRITICAL: {change_count} Critical Sanctions Alert(s)"
        elif priority == 'HIGH':
            return f"📋 HIGH PRIORITY: {change_count} Sanctions Update(s)"
        elif priority == 'DIGEST':
            return f"📊 Daily Sanctions Digest - {datetime.utcnow().strftime('%Y-%m-%d')}"
        else:
            return f"📄 Sanctions Update: {change_count} Change(s)"
    
    def _get_slack_emoji(self, priority: str) -> str:
        """Get appropriate Slack emoji for priority."""
        return {
            'CRITICAL': ':rotating_light:',
            'HIGH': ':warning:',
            'DIGEST': ':bar_chart:',
            'DEFAULT': ':information_source:'
        }.get(priority, ':information_source:')
    
    def _create_slack_attachments(self, changes, priority: str) -> List[Dict[str, Any]]:
        """Create Slack message attachments."""
        if not isinstance(changes, list):
            changes = [changes] if changes else []
        
        color = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'DIGEST': 'good',
            'DEFAULT': '#439FE0'
        }.get(priority, '#439FE0')
        
        attachment = {
            'color': color,
            'fields': [
                {
                    'title': 'Change Count',
                    'value': str(len(changes)),
                    'short': True
                },
                {
                    'title': 'Priority',
                    'value': priority,
                    'short': True
                }
            ],
            'footer': 'TrustCheck Sanctions Monitor',
            'ts': int(datetime.utcnow().timestamp())
        }
        
        return [attachment]
    
    def _serialize_changes_for_webhook(self, changes) -> List[Dict[str, Any]]:
        """Serialize changes for webhook payload."""
        if not isinstance(changes, list):
            changes = [changes] if changes else []
        
        serialized = []
        for change in changes[:5]:  # Limit to 5 for payload size
            if hasattr(change, 'entity_name'):
                serialized.append({
                    'entity_name': change.entity_name,
                    'entity_uid': change.entity_uid,
                    'change_type': change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                    'risk_level': change.risk_level.value if hasattr(change.risk_level, 'value') else str(change.risk_level),
                    'summary': change.change_summary,
                    'detected_at': change.detected_at.isoformat() if hasattr(change, 'detected_at') else None
                })
        
        return serialized
    
    # ======================== CONFIGURATION METHODS ========================
    
    def configure_channel(self, channel: NotificationChannel, config: Dict[str, Any]) -> None:
        """Configure specific notification channel."""
        if channel == NotificationChannel.EMAIL:
            self.config['email'].update(config)
        elif channel == NotificationChannel.WEBHOOK:
            self.config['webhook'].update(config)
        elif channel == NotificationChannel.SLACK:
            self.config['slack'].update(config)
        
        self.logger.info(f"Configured {channel.value} notification channel")
    
    def enable_channels(self, channels: List[NotificationChannel]) -> None:
        """Enable specific notification channels."""
        self.enabled_channels = channels
        self.logger.info(f"Enabled notification channels: {[c.value for c in channels]}")
    
    def disable_channel(self, channel: NotificationChannel) -> None:
        """Disable specific notification channel."""
        if channel in self.enabled_channels:
            self.enabled_channels.remove(channel)
            self.logger.info(f"Disabled {channel.value} notification channel")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of notification service."""
        try:
            channel_health = {}
            
            for channel in self.enabled_channels:
                try:
                    # Test basic channel functionality
                    if channel == NotificationChannel.LOG:
                        channel_health[channel.value] = {'healthy': True, 'status': 'operational'}
                    else:
                        # For other channels, check configuration
                        config_key = channel.value
                        has_config = config_key in self.config and self.config[config_key]
                        channel_health[channel.value] = {
                            'healthy': has_config,
                            'status': 'configured' if has_config else 'not_configured'
                        }
                except Exception as e:
                    channel_health[channel.value] = {
                        'healthy': False,
                        'status': 'error',
                        'error': str(e)
                    }
            
            overall_healthy = all(ch.get('healthy', False) for ch in channel_health.values())
            
            return {
                'healthy': overall_healthy,
                'status': 'operational' if overall_healthy else 'degraded',
                'enabled_channels': [c.value for c in self.enabled_channels],
                'channel_health': channel_health
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'status': 'failed',
                'error': str(e)
            }

# ======================== EXPORTS ========================

__all__ = [
    'NotificationService'
]