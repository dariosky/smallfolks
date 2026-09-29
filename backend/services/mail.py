import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import urlencode

import settings


def build_email_verification_url(email: str) -> str:
    from services.auth import build_email_verification_code

    query = urlencode({"email": email, "code": build_email_verification_code(email)})
    return f"{settings.BASE_URL.rstrip('/')}/verify-email?{query}"


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    if not settings.EMAIL_DELIVERY_ENABLED:
        return

    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise RuntimeError("SMTP settings are incomplete.")
    if settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
        raise RuntimeError("SMTP_USE_SSL and SMTP_USE_TLS cannot both be enabled.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    smtp_client_cls = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
    with smtp_client_cls(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=settings.SMTP_TIMEOUT_SECONDS,
    ) as smtp_client:
        if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
            smtp_client.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            smtp_client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp_client.send_message(message)


def _render_email_shell(*, title: str, body_html: str, cta_url: str, cta_label: str) -> str:
    escaped_title = escape(title)
    escaped_cta_url = escape(cta_url, quote=True)
    escaped_cta_label = escape(cta_label)
    escaped_site_name = escape(settings.SITE_NAME)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>{escaped_title}</title>
  </head>
  <body style="margin:0;padding:0;background:#f7f8fa;color:#20242a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <div style="max-width:560px;margin:0 auto;padding:24px;">
      <div style="background:#ffffff;border:1px solid #e3e7ee;border-radius:8px;overflow:hidden;">
        <div style="padding:22px 22px 0;">
          <div style="font-size:18px;font-weight:700;color:#20242a;">{escaped_site_name}</div>
        </div>
        <div style="padding:18px 22px 26px;font-size:15px;line-height:1.6;">
          <h1 style="margin:0 0 16px;font-size:22px;line-height:1.25;">{escaped_title}</h1>
          {body_html}
          <p style="margin:22px 0;"><a href="{escaped_cta_url}" style="display:inline-block;background:#2557d6;color:#ffffff;text-decoration:none;padding:10px 16px;border-radius:6px;font-weight:700;">{escaped_cta_label}</a></p>
          <p style="margin:18px 0 0;color:#687386;font-size:12px;">If you were not expecting this email, you can ignore it.</p>
        </div>
      </div>
    </div>
  </body>
</html>"""


def send_verification_email(*, recipient_email: str, full_name: str) -> None:
    verification_url = build_email_verification_url(recipient_email)
    display_name = full_name.strip() or "there"
    subject = f"Verify your {settings.SITE_NAME} email"
    text_body = (
        f"Hi {display_name},\n\n"
        f"Welcome to {settings.SITE_NAME}. Verify your email address here:\n\n"
        f"{verification_url}\n\n"
        "If you did not create this account, you can ignore this email."
    )
    html_body = _render_email_shell(
        title="Verify your email",
        body_html=(
            f"<p>Hi {escape(display_name)},</p>"
            f"<p>Welcome to {escape(settings.SITE_NAME)}. Confirm this email address so account recovery and notifications reach the right inbox.</p>"
        ),
        cta_url=verification_url,
        cta_label="Verify email address",
    )
    send_email(
        to_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_account_exists_email(*, recipient_email: str, full_name: str) -> None:
    login_url = f"{settings.BASE_URL.rstrip('/')}/"
    display_name = full_name.strip() or "there"
    subject = f"Sign-in attempt for your {settings.SITE_NAME} account"
    text_body = (
        f"Hi {display_name},\n\n"
        f"Someone tried to create a new {settings.SITE_NAME} account using this email. "
        f"If this was you, log in here: {login_url}\n\n"
        "If you did not attempt this, you can ignore this email."
    )
    html_body = _render_email_shell(
        title="You already have an account",
        body_html=(
            f"<p>Hi {escape(display_name)},</p>"
            f"<p>Someone tried to register a new {escape(settings.SITE_NAME)} account with this email address. If it was you, log in instead or reset your password.</p>"
        ),
        cta_url=login_url,
        cta_label=f"Log in to {settings.SITE_NAME}",
    )
    send_email(
        to_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_magic_login_email(
    *, recipient_email: str, full_name: str, magic_url: str
) -> None:
    display_name = full_name.strip() or "there"
    subject = f"Your {settings.SITE_NAME} sign-in link"
    text_body = (
        f"Hi {display_name},\n\n"
        f"Open this link to sign in to {settings.SITE_NAME}:\n\n{magic_url}\n\n"
        "This link expires soon. If you did not request it, you can ignore this email."
    )
    html_body = _render_email_shell(
        title="Your secure sign-in link",
        body_html=(
            f"<p>Hi {escape(display_name)},</p>"
            f"<p>Use this one-click link to sign in to {escape(settings.SITE_NAME)}. The link expires shortly.</p>"
        ),
        cta_url=magic_url,
        cta_label=f"Sign in to {settings.SITE_NAME}",
    )
    send_email(
        to_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_password_reset_email(
    *,
    recipient_email: str,
    full_name: str,
    reset_url: str,
) -> None:
    display_name = full_name.strip() or "there"
    subject = f"Reset your {settings.SITE_NAME} password"
    text_body = (
        f"Hi {display_name},\n\n"
        f"Open this link to set a new {settings.SITE_NAME} password:\n\n"
        f"{reset_url}\n\n"
        "This link expires soon. If you did not request it, you can ignore this email."
    )
    html_body = _render_email_shell(
        title="Reset your password",
        body_html=(
            f"<p>Hi {escape(display_name)},</p>"
            f"<p>Use this link to set a new password for your {escape(settings.SITE_NAME)} account. The link expires shortly.</p>"
        ),
        cta_url=reset_url,
        cta_label="Set new password",
    )

    send_email(
        to_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
