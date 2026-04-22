"""Email notification system.

SRP: Only responsible for composing and sending emails.
OCP: New notification channels can be added via the BaseNotifier abstraction.
DIP: Depends on EmailConfig, not hardcoded SMTP settings.
"""

import re
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from company_curator.config import EmailConfig


class BaseNotifier(ABC):
    """Abstract notifier — allows adding Slack, SMS, etc. without modifying existing code (OCP)."""

    @abstractmethod
    def send(self, subject: str, body: str) -> bool:
        ...


class EmailNotifier(BaseNotifier):
    """Sends daily email reports via SMTP."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, subject: str, body: str) -> bool:
        """Send an email with the given subject and body."""
        if not self._config.smtp_user or not self._config.smtp_password:
            print("[Email] SMTP credentials not configured, skipping email.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._config.smtp_user
        msg["To"] = self._config.email_to

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(self._markdown_to_html(body), "html"))

        try:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                server.starttls()
                server.login(self._config.smtp_user, self._config.smtp_password)
                server.send_message(msg)
            return True
        except smtplib.SMTPException as e:
            print(f"[Email] Failed to send: {e}")
            return False

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Convert markdown report to styled HTML email."""
        sections = re.split(r"\n---\n", md)
        html_sections: list[str] = []

        for section in sections:
            html_sections.append(_convert_section(section.strip()))

        body_content = "\n".join(
            f'<div class="section">{s}</div>' for s in html_sections if s
        )

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    margin: 0;
    padding: 0;
    background-color: #f4f4f7;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #2d3748;
    line-height: 1.6;
    font-size: 15px;
  }}
  .wrapper {{
    max-width: 680px;
    margin: 0 auto;
    padding: 24px 16px;
  }}
  .header {{
    background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
    color: #ffffff;
    padding: 32px 28px;
    border-radius: 8px 8px 0 0;
  }}
  .header h1 {{
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.3px;
  }}
  .header p {{
    margin: 6px 0 0 0;
    font-size: 13px;
    opacity: 0.85;
  }}
  .body {{
    background: #ffffff;
    padding: 28px;
    border-radius: 0 0 8px 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .section {{
    margin-bottom: 28px;
    padding-bottom: 24px;
    border-bottom: 1px solid #e2e8f0;
  }}
  .section:last-child {{
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
  }}
  h1 {{ font-size: 22px; color: #1a365d; margin: 0 0 16px 0; font-weight: 600; }}
  h2 {{ font-size: 18px; color: #2b6cb0; margin: 24px 0 12px 0; font-weight: 600; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }}
  h3 {{ font-size: 15px; color: #4a5568; margin: 20px 0 8px 0; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
  h4 {{ font-size: 14px; color: #4a5568; margin: 16px 0 6px 0; font-weight: 600; }}
  p {{ margin: 8px 0; }}
  strong {{ color: #1a202c; }}
  ul, ol {{
    margin: 8px 0;
    padding-left: 24px;
  }}
  li {{
    margin: 4px 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 13px;
  }}
  th {{
    background: #edf2f7;
    color: #2d3748;
    font-weight: 600;
    text-align: left;
    padding: 10px 12px;
    border: 1px solid #e2e8f0;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  td {{
    padding: 9px 12px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
  }}
  tr:nth-child(even) td {{
    background: #f7fafc;
  }}
  .score-badge {{
    display: inline-block;
    background: #2b6cb0;
    color: #fff;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
  }}
  .risk-high {{ color: #c53030; font-weight: 600; }}
  .risk-medium {{ color: #d69e2e; font-weight: 600; }}
  .risk-low {{ color: #38a169; font-weight: 600; }}
  .pick-card {{
    background: #f7fafc;
    border-left: 3px solid #2b6cb0;
    padding: 14px 18px;
    margin: 12px 0;
    border-radius: 0 6px 6px 0;
  }}
  .footer {{
    text-align: center;
    margin-top: 24px;
    padding: 16px;
    font-size: 12px;
    color: #a0aec0;
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Company Curator</h1>
    <p>Daily Investment Research Report</p>
  </div>
  <div class="body">
    {body_content}
  </div>
  <div class="footer">
    Generated by Company Curator &middot; Data via Yahoo Finance &middot; Analysis via Claude
  </div>
</div>
</body>
</html>"""


def _convert_section(text: str) -> str:
    """Convert a markdown section to HTML."""
    if not text:
        return ""

    lines = text.split("\n")
    html_lines: list[str] = []
    i = 0
    in_list = False
    in_ordered_list = False
    list_type = ""

    while i < len(lines):
        line = lines[i]

        # Markdown table
        if "|" in line and i + 1 < len(lines) and re.match(r"\s*\|[-\s|:]+\|\s*$", lines[i + 1]):
            table_html, i = _convert_table(lines, i)
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append(table_html)
            continue

        # Close open list if current line isn't a list item
        if in_list and not re.match(r"^\s*[-*]\s", line) and not re.match(r"^\s*\d+\.\s", line) and line.strip():
            html_lines.append(f"</{list_type}>")
            in_list = False

        # Headers
        if line.startswith("#### "):
            html_lines.append(f"<h4>{_inline(line[5:])}</h4>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            # Skip top-level headers — they're in the email header
            pass
        # Unordered list items
        elif re.match(r"^\s*[-*]\s", line):
            content = re.sub(r"^\s*[-*]\s", "", line)
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            html_lines.append(f"<li>{_inline(content)}</li>")
        # Ordered list items
        elif re.match(r"^\s*\d+\.\s", line):
            content = re.sub(r"^\s*\d+\.\s", "", line)
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            html_lines.append(f"<li>{_inline(content)}</li>")
        # Blank line
        elif not line.strip():
            pass
        # Regular paragraph
        else:
            html_lines.append(f"<p>{_inline(line)}</p>")

        i += 1

    if in_list:
        html_lines.append(f"</{list_type}>")

    return "\n".join(html_lines)


def _convert_table(lines: list[str], start: int) -> tuple[str, int]:
    """Convert a markdown table starting at `start` into an HTML table."""
    header_line = lines[start].strip().strip("|")
    headers = [h.strip() for h in header_line.split("|")]

    # Skip the separator line
    i = start + 2
    rows: list[list[str]] = []

    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        row_line = lines[i].strip().strip("|")
        cells = [c.strip() for c in row_line.split("|")]
        rows.append(cells)
        i += 1

    html = "<table>\n<thead><tr>"
    for h in headers:
        html += f"<th>{_inline(h)}</th>"
    html += "</tr></thead>\n<tbody>"
    for row in rows:
        html += "<tr>"
        for cell in row:
            styled = _style_risk(cell)
            html += f"<td>{_inline(styled)}</td>"
        html += "</tr>"
    html += "</tbody></table>"

    return html, i


def _inline(text: str) -> str:
    """Convert inline markdown: links, bold, italic, inline code."""
    # Links: [text](url)
    text = re.sub(
        r"\[(.+?)\]\((.+?)\)",
        r'<a href="\2" style="color:#2b6cb0;text-decoration:underline;font-weight:500;">\1</a>',
        text,
    )
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r'<code style="background:#edf2f7;padding:1px 5px;border-radius:3px;font-size:13px;">\1</code>', text)
    return text


def _style_risk(text: str) -> str:
    """Apply color styling to risk ratings."""
    text = re.sub(r"\bHIGH RISK\b", '<span class="risk-high">HIGH RISK</span>', text)
    text = re.sub(r"\bHIGH\b", '<span class="risk-high">HIGH</span>', text)
    text = re.sub(r"\bMEDIUM\b", '<span class="risk-medium">MEDIUM</span>', text)
    text = re.sub(r"\bLOW\b", '<span class="risk-low">LOW</span>', text)
    return text
