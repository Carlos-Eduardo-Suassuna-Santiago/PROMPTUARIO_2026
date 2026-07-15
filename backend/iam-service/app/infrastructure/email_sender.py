import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def send_reset_password_email(to_email: str, reset_link: str) -> None:
    """Send a password reset email using the configured SMTP server."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Redefinição de Senha - PROMPTUÁRIO"
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email

        text = f"""
        Olá,

        Você solicitou a redefinição da sua senha no sistema PROMPTUÁRIO.
        Acesse o link abaixo para criar uma nova senha:
        
        {reset_link}

        Se você não solicitou essa redefinição, ignore este e-mail.
        """

        html = f"""
        <html>
          <body>
            <h2>Redefinição de Senha</h2>
            <p>Olá,</p>
            <p>Você solicitou a redefinição da sua senha no sistema PROMPTUÁRIO.</p>
            <p>
               <a href="{reset_link}" style="display: inline-block; padding: 10px 20px; background-color: #2dd4bf; color: #fff; text-decoration: none; border-radius: 5px;">
                  Redefinir minha senha
               </a>
            </p>
            <p>Ou copie e cole o link no seu navegador:</p>
            <p><a href="{reset_link}">{reset_link}</a></p>
            <p>Se você não solicitou essa redefinição, ignore este e-mail.</p>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
            
        logger.info(f"Password reset email sent to {to_email}")

    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
