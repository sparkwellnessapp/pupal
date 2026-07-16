"""
Email service for sending rubric share emails.

Provides an abstracted email interface with Gmail API implementation.
Supports retry logic, Hebrew templates, and proper error handling.
"""
import os
import base64
import json
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Result of an email send operation."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Attachment:
    """Email attachment."""
    filename: str
    content: bytes
    content_type: str = "application/pdf"


class EmailProvider(ABC):
    """Abstract base class for email providers."""
    
    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Attachment]] = None,
    ) -> EmailResult:
        """Send an email."""
        pass


class GmailEmailService(EmailProvider):
    """
    Gmail API email service.
    
    Uses a service account with domain-wide delegation to send emails.
    Includes retry logic with exponential backoff.
    """
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds
    
    def __init__(self):
        """Initialize Gmail service from environment variables."""
        self._service = None
        self._sender_email = os.getenv("GMAIL_SENDER_EMAIL", "noreply@vivi.app")
        self._sender_name = os.getenv("GMAIL_SENDER_NAME", "Vivi")
        
        # Load credentials from base64-encoded JSON
        creds_b64 = os.getenv("GMAIL_SERVICE_ACCOUNT_JSON")
        if creds_b64:
            try:
                self._credentials_info = json.loads(base64.b64decode(creds_b64))
                logger.info("Gmail credentials loaded from environment")
            except Exception as e:
                logger.warning(f"Failed to load Gmail credentials: {e}")
                self._credentials_info = None
        else:
            self._credentials_info = None
            logger.warning("GMAIL_SERVICE_ACCOUNT_JSON not set - email sending disabled")
    
    def _get_service(self):
        """Get or create the Gmail API service."""
        if self._service is not None:
            return self._service
        
        if not self._credentials_info:
            raise RuntimeError("Gmail credentials not configured")
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            credentials = service_account.Credentials.from_service_account_info(
                self._credentials_info,
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            
            # Delegate to sender email
            delegated_credentials = credentials.with_subject(self._sender_email)
            
            self._service = build('gmail', 'v1', credentials=delegated_credentials)
            logger.info(f"Gmail service initialized for {self._sender_email}")
            return self._service
            
        except ImportError:
            raise RuntimeError("google-auth and google-api-python-client required for Gmail")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            raise
    
    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Attachment]] = None,
    ) -> EmailResult:
        """
        Send an email via Gmail API.
        
        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML body content
            attachments: Optional list of attachments
            
        Returns:
            EmailResult with success status and message ID or error
        """
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self._send_email_once(to, subject, html_body, attachments)
                return result
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    await asyncio.sleep(delay)
        
        logger.error(f"Email send failed after {self.MAX_RETRIES} attempts: {last_error}")
        return EmailResult(success=False, error=f"שליחת המייל נכשלה: {last_error}")
    
    async def _send_email_once(
        self,
        to: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Attachment]] = None,
    ) -> EmailResult:
        """Single attempt to send email."""
        service = self._get_service()
        
        # Create message
        message = MIMEMultipart('mixed')
        message['to'] = to
        message['from'] = f"{self._sender_name} <{self._sender_email}>"
        message['subject'] = subject
        
        # Add HTML body
        html_part = MIMEText(html_body, 'html', 'utf-8')
        message.attach(html_part)
        
        # Add attachments if any
        if attachments:
            from email.mime.base import MIMEBase
            from email import encoders
            
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.content)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{attachment.filename}"'
                )
                message.attach(part)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send via API (run in thread pool to not block)
        def send():
            return service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
        
        result = await asyncio.get_event_loop().run_in_executor(None, send)
        
        message_id = result.get('id')
        logger.info(f"Email sent successfully to {to}, message_id={message_id}")
        
        return EmailResult(success=True, message_id=message_id)
    
    def is_configured(self) -> bool:
        """Check if Gmail is properly configured."""
        return self._credentials_info is not None


# =============================================================================
# Hebrew Email Templates
# =============================================================================

def create_rubric_share_email_html(
    sender_name: str,
    rubric_name: str,
    download_url: str,
    invite_url: str,
) -> str:
    """
    Create Hebrew HTML email for rubric sharing.
    
    Args:
        sender_name: Name of the teacher sharing
        rubric_name: Name of the rubric
        download_url: Direct PDF download link
        invite_url: Link to accept share and join Vivi
        
    Returns:
        HTML email body
    """
    return f'''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 24px; text-align: center; border-bottom: 1px solid #eee;">
                            <h1 style="margin: 0; color: #6366f1; font-size: 28px;">Vivi</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px;">
                            <h2 style="margin: 0 0 16px; color: #1f2937; font-size: 22px;">
                                היי! 👋
                            </h2>
                            
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                <strong style="color: #1f2937;">{sender_name}</strong> שיתף/ה אותך במחוון חדש שיצר/ה באמצעות Vivi.
                            </p>
                            
                            <div style="background-color: #f8fafc; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
                                <p style="margin: 0; color: #64748b; font-size: 14px;">שם המחוון:</p>
                                <p style="margin: 8px 0 0; color: #1f2937; font-size: 18px; font-weight: 600;">
                                    {rubric_name}
                                </p>
                            </div>
                            
                            <!-- Download Button -->
                            <div style="text-align: center; margin-bottom: 24px;">
                                <a href="{download_url}" style="display: inline-block; padding: 14px 32px; background-color: #10b981; color: #ffffff; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">
                                    📥 הורדת המחוון (PDF)
                                </a>
                            </div>
                            
                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                            
                            <p style="margin: 0 0 16px; color: #4b5563; font-size: 15px; line-height: 1.6;">
                                רוצה לערוך את המחוון ולבדוק איתו מבחנים?
                                <br>
                                הירשם/י ל-Vivi בחינם והמחוון יחכה לך בחשבון!
                            </p>
                            
                            <!-- Invite Button -->
                            <div style="text-align: center;">
                                <a href="{invite_url}" style="display: inline-block; padding: 14px 32px; background-color: #6366f1; color: #ffffff; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">
                                    🚀 הצטרפות ל-Vivi
                                </a>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; background-color: #f8fafc; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; color: #9ca3af; font-size: 13px;">
                                Vivi - בדיקת מבחנים חכמה למורים
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''


def create_rubric_share_subject(sender_name: str) -> str:
    """Create email subject for rubric sharing."""
    return f"{sender_name} שיתף/ה איתך מחוון חדש ב-Vivi"


# =============================================================================
# Service Factory
# =============================================================================

_email_service: Optional[EmailProvider] = None


def get_email_service() -> EmailProvider:
    """Get or create the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = GmailEmailService()
    return _email_service


async def send_rubric_share_email(
    recipient_email: str,
    sender_name: str,
    rubric_name: str,
    download_url: str,
    invite_url: str,
) -> EmailResult:
    """
    Convenience function to send a rubric share email.
    
    Args:
        recipient_email: Email address to send to
        sender_name: Name of the sharing teacher
        rubric_name: Name of the rubric
        download_url: Direct PDF download URL
        invite_url: URL to accept share and join Vivi
        
    Returns:
        EmailResult with success status
    """
    service = get_email_service()
    
    # Validate email format
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', recipient_email):
        return EmailResult(success=False, error="כתובת אימייל לא תקינה")
    
    subject = create_rubric_share_subject(sender_name)
    html_body = create_rubric_share_email_html(
        sender_name=sender_name,
        rubric_name=rubric_name,
        download_url=download_url,
        invite_url=invite_url,
    )
    
    return await service.send_email(
        to=recipient_email,
        subject=subject,
        html_body=html_body,
    )
