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
        """Convert markdown report to styled HTML email matching the Quill design."""
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
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400&family=JetBrains+Mono:wght@400;500;700&display=swap');
  body {{
    margin: 0;
    padding: 0;
    background-color: #f2ede3;
    font-family: 'Fraunces', Georgia, serif;
    color: #1a1714;
    line-height: 1.5;
    font-size: 15px;
  }}
  .wrapper {{
    max-width: 680px;
    margin: 0 auto;
    padding: 24px 16px;
  }}
  .header {{
    background: #1a1714;
    color: #fbf8f3;
    padding: 28px 24px;
    border: 1.5px solid #1a1714;
    border-radius: 6px 4px 0 0;
  }}
  .header-logo {{
    display: inline-block;
    width: 28px;
    height: 28px;
    border: 1.8px solid #fbf8f3;
    border-radius: 50%;
    text-align: center;
    line-height: 26px;
    font-size: 14px;
    background: #f2d35a;
    color: #1a1714;
    margin-right: 10px;
    vertical-align: middle;
  }}
  .header h1 {{
    display: inline;
    margin: 0;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 22px;
    font-weight: 700;
    vertical-align: middle;
  }}
  .header p {{
    margin: 8px 0 0 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #fbf8f3;
    opacity: 0.85;
  }}
  .body {{
    background: #fbf8f3;
    padding: 24px;
    border: 1.5px solid #1a1714;
    border-top: none;
    border-radius: 0 0 6px 4px;
  }}
  .section {{
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px dashed #9a9089;
  }}
  .section:last-child {{
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
  }}
  h1 {{
    font-family: 'Fraunces', Georgia, serif;
    font-size: 20px;
    color: #1a1714;
    margin: 0 0 14px 0;
    font-weight: 700;
  }}
  h2 {{
    font-family: 'Fraunces', Georgia, serif;
    font-size: 18px;
    color: #1a1714;
    margin: 20px 0 10px 0;
    font-weight: 600;
    padding-bottom: 6px;
    border-bottom: 1.5px solid #1a1714;
  }}
  h3 {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #6b625a;
    margin: 18px 0 6px 0;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  h4 {{
    font-family: 'Fraunces', Georgia, serif;
    font-size: 15px;
    color: #3a342e;
    margin: 14px 0 6px 0;
    font-weight: 600;
  }}
  p {{
    margin: 6px 0;
    color: #3a342e;
  }}
  strong {{ color: #1a1714; }}
  em {{ font-style: italic; }}
  ul, ol {{
    margin: 6px 0;
    padding-left: 22px;
    color: #3a342e;
  }}
  li {{ margin: 3px 0; font-size: 14px; }}

  /* Cards for picks */
  .pick-card {{
    background: #f2ede3;
    border: 1.2px solid #1a1714;
    border-left: 4px solid #f2d35a;
    border-radius: 3px 5px 2px 6px;
    padding: 12px 16px;
    margin: 10px 0;
  }}

  /* Pills */
  .pill {{
    display: inline-block;
    border: 1.5px solid #1a1714;
    border-radius: 999px;
    padding: 1px 10px;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 12px;
    background: #fbf8f3;
  }}
  .pill-green {{ background: rgba(74, 124, 58, 0.28); }}
  .pill-red {{ background: rgba(197, 70, 58, 0.22); }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0;
    font-size: 13px;
  }}
  th {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #6b625a;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1.5px solid #1a1714;
    background: #f2ede3;
  }}
  td {{
    padding: 8px 10px;
    border-bottom: 1px dashed #9a9089;
    vertical-align: top;
    font-size: 13px;
  }}
  tr:last-child td {{ border-bottom: none; }}

  /* Data styling */
  .data-val {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
  }}
  .data-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #6b625a;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .positive {{ color: #4a7c3a; }}
  .negative {{ color: #c5463a; }}

  /* Risk ratings */
  .risk-high {{ color: #c5463a; font-weight: 600; }}
  .risk-medium {{ color: #d69e2e; font-weight: 600; }}
  .risk-low {{ color: #4a7c3a; font-weight: 600; }}

  /* Score badge */
  .score-badge {{
    display: inline-block;
    background: #1a1714;
    color: #fbf8f3;
    padding: 2px 10px;
    border-radius: 999px;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 12px;
    font-weight: 600;
  }}

  /* CTA button */
  .btn {{
    display: inline-block;
    border: 1.5px solid #1a1714;
    border-radius: 4px 7px 3px 6px;
    padding: 6px 14px;
    background: #1a1714;
    font-family: 'Fraunces', Georgia, serif;
    font-size: 13px;
    color: #fbf8f3;
    text-decoration: none;
    font-weight: 600;
  }}

  .footer {{
    text-align: center;
    margin-top: 20px;
    padding: 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #9a9089;
    letter-spacing: 0.5px;
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <span class="header-logo">&#10022;</span>
    <h1>Curator</h1>
    <p>Daily Investment Research Report</p>
  </div>
  <div class="body">
    {body_content}
  </div>
  <div class="footer">
    Company Curator &middot; Data via Yahoo Finance &middot; Analysis via Claude
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
        r'<a href="\2" style="color:#3a5a8c;text-decoration:underline;font-weight:600;">\1</a>',
        text,
    )
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(
        r"`(.+?)`",
        r'<code style="font-family:\'JetBrains Mono\',monospace;background:#f2ede3;padding:1px 5px;border-radius:3px;font-size:12px;">\1</code>',
        text,
    )
    return text


def _style_risk(text: str) -> str:
    """Apply color styling to risk ratings."""
    text = re.sub(r"\bHIGH RISK\b", '<span class="risk-high">HIGH RISK</span>', text)
    text = re.sub(r"\bHIGH\b", '<span class="risk-high">HIGH</span>', text)
    text = re.sub(r"\bMEDIUM\b", '<span class="risk-medium">MEDIUM</span>', text)
    text = re.sub(r"\bLOW\b", '<span class="risk-low">LOW</span>', text)
    return text
