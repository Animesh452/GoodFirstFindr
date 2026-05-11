from __future__ import annotations

import asyncio
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
import logging
import smtplib
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings
from app.models import IssueRecommendation
from app.recommender import find_recommendations


logger = logging.getLogger(__name__)


def start_digest_scheduler(settings: Settings) -> BackgroundScheduler | None:
    if not settings.digest_enabled:
        logger.info("Daily digest scheduler disabled")
        return None

    hour, minute = _parse_digest_time(settings.digest_time)
    timezone = ZoneInfo(settings.digest_timezone)
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(
        lambda: asyncio.run(send_daily_digest(settings)),
        CronTrigger(hour=hour, minute=minute, timezone=timezone),
        id="daily-email-digest",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Daily digest scheduled for %02d:%02d %s", hour, minute, settings.digest_timezone)
    return scheduler


async def send_daily_digest(settings: Settings) -> bool:
    if not settings.gmail_user or not settings.gmail_app_password or not settings.recipient_email:
        logger.info("Skipping daily digest because Gmail or recipient env vars are missing")
        return False

    issues, _ = await find_recommendations(
        keyword=settings.digest_keyword,
        limit=10,
        settings=settings,
        include_reasons=True,
    )
    if not issues:
        logger.info("Skipping daily digest because no issues were found")
        return False

    subject = f"GoodFirstFindr daily digest: {len(issues)} issues"
    text_body = _plain_text_digest(issues)
    html_body = _html_digest(issues)
    _send_email(settings, subject, text_body, html_body)
    logger.info("Daily digest sent to %s", settings.recipient_email)
    return True


def _parse_digest_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = max(0, min(23, int(hour_text)))
        minute = max(0, min(59, int(minute_text)))
        return hour, minute
    except (ValueError, AttributeError):
        return 8, 0


def _plain_text_digest(issues: list[IssueRecommendation]) -> str:
    lines = ["Top GoodFirstFindr issues for today", ""]
    for index, issue in enumerate(issues, start=1):
        lines.extend(
            [
                f"{index}. {issue.title}",
                f"   Repo: {issue.repository}",
                f"   Score: {issue.score:.1f}/100",
                f"   Reason: {issue.reason}",
                f"   URL: {issue.html_url}",
                "",
            ]
        )
    return "\n".join(lines)


def _html_digest(issues: list[IssueRecommendation]) -> str:
    rows = []
    for index, issue in enumerate(issues, start=1):
        labels = escape(", ".join(issue.labels[:5]))
        issue_url = escape(issue.html_url, quote=True)
        title = escape(issue.title)
        repository = escape(issue.repository)
        reason = escape(issue.reason)
        rows.append(
            f"""
            <tr>
                <td style="padding:12px;border-bottom:1px solid #e5e3dc;">{index}</td>
                <td style="padding:12px;border-bottom:1px solid #e5e3dc;">
                    <a href="{issue_url}" style="color:#136f63;font-weight:700;text-decoration:none;">{title}</a>
                    <div style="color:#66645d;font-size:13px;">{repository} | {labels}</div>
                    <div style="margin-top:6px;color:#33312d;">{reason}</div>
                </td>
                <td style="padding:12px;border-bottom:1px solid #e5e3dc;text-align:right;font-weight:700;">{issue.score:.1f}</td>
            </tr>
            """
        )
    today = datetime.now().strftime("%b %d, %Y")
    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f7f6f1;color:#262622;padding:24px;">
        <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e3dc;border-radius:8px;overflow:hidden;">
          <div style="padding:18px 20px;background:#136f63;color:#ffffff;">
            <h1 style="font-size:22px;margin:0;">GoodFirstFindr daily digest</h1>
            <p style="margin:4px 0 0;color:#d9f2ed;">{today}</p>
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr>
                <th style="padding:10px 12px;text-align:left;color:#66645d;">#</th>
                <th style="padding:10px 12px;text-align:left;color:#66645d;">Issue</th>
                <th style="padding:10px 12px;text-align:right;color:#66645d;">Score</th>
              </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
          </table>
        </div>
      </body>
    </html>
    """


def _send_email(settings: Settings, subject: str, text_body: str, html_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.gmail_user or ""
    message["To"] = settings.recipient_email or ""
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(settings.gmail_user, settings.gmail_app_password)
        smtp.sendmail(settings.gmail_user, [settings.recipient_email], message.as_string())
