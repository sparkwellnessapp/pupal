import asyncio
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def verify_email_config():
    """Verify email configuration by sending a test email."""
    print("=" * 60)
    print("EMAIL CONFIGURATION VERIFICATION")
    print("=" * 60)
    
    # 1. Check environment variables
    creds = os.getenv("GMAIL_SERVICE_ACCOUNT_JSON")
    sender = os.getenv("GMAIL_SENDER_EMAIL")
    
    print(f"Checking GMAIL_SENDER_EMAIL: {'OK' if sender else 'MISSING'} ({sender})")
    print(f"Checking GMAIL_SERVICE_ACCOUNT_JSON: {'OK' if creds else 'MISSING'}")
    
    if not creds or not sender:
        print("❌ Missing configuration! Please check your .env file.")
        return

    try:
        # Import manually to test imports too
        from app.services.email_service import get_email_service
        
        # 2. Initialize service
        print("\nInitializing Email Service...")
        service = get_email_service()
        
        if not service.is_configured():
            print("❌ Service reports 'not configured' despite env vars being present.")
            return
            
        print("✅ Service initialized successfully.")
        
        # 3. Send test email
        print(f"\nSending test email to {sender}...")
        
        result = await service.send_email(
            to=sender,  # Send to self
            subject="Vivi Email Configuration Test",
            html_body="""
            <h1>It Works! 🎉</h1>
            <p>This is a test email from your Vivi backend.</p>
            <p>If you're reading this, the Gmail API integration is correctly configured.</p>
            <br>
            <p>Time: <b>Just now</b></p>
            """
        )
        
        if result.success:
            print(f"✅ Email sent successfully! Message ID: {result.message_id}")
            print("\n🎉 VERIFICATION COMPLETE: Email system is working correctly.")
        else:
            print(f"❌ Email send failed: {result.error}")
            
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_email_config())
