import aiosmtplib
from email.message import EmailMessage
from email.utils import formataddr

from config import Config

web_config = Config()

async def format_email_object( recipient_email : str, email_subject : str, email_contents : str ) -> EmailMessage:
    """
        Formats an email object for sending

        :param recipient_email: The email address of the recipient
        :param email_subject: The subject of the email
        :param email_contents: The contents of the email

        :return: EmailMessage
    """

    email = EmailMessage()
    email["From"] = formataddr(( web_config.SMTP_NO_REPLY_SENDER_NAME, web_config.SMTP_NO_REPLY_SENDER ))
    email["To"] = recipient_email
    email["Subject"] = email_subject
    email.set_content( email_contents )

    return email

async def send_email( email_obj : EmailMessage ) -> None:
    """
        Sends an email using the configured SMTP server

        :param email_obj: The email to send

        :return: None
    """

    await aiosmtplib.send(
        email_obj,
        hostname = web_config.SMTP_SERVER_ADDRESS,
        username = web_config.SMTP_NO_REPLY_SENDER,
        password = web_config.SMTP_NO_REPLY_PASSWORD,
        use_tls = True
    )
