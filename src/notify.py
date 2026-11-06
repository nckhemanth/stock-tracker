"""Email notification via Resend."""

import os
from datetime import datetime


def send_refresh_email(stocks_count: int, top_10: list[dict]):
    """Send email notification that a refresh was completed."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        print("  [Email] No RESEND_API_KEY, skipping email")
        return False

    try:
        import resend
        resend.api_key = api_key

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Build top 10 summary
        top_rows = ""
        for s in top_10[:10]:
            hold = "HELD" if s.get("i_hold") else ""
            ip = f"${s['intuition_point']:.0f}" if s.get("intuition_point") else "—"
            top_rows += f"""<tr>
              <td style="padding:4px 8px;border-bottom:1px solid #333">{s['rank']}</td>
              <td style="padding:4px 8px;border-bottom:1px solid #333;font-weight:700">{s['ticker']}</td>
              <td style="padding:4px 8px;border-bottom:1px solid #333">${s['price']:.2f}</td>
              <td style="padding:4px 8px;border-bottom:1px solid #333">{ip}</td>
              <td style="padding:4px 8px;border-bottom:1px solid #333">{s.get('upside_pct', 0):.1f}%</td>
              <td style="padding:4px 8px;border-bottom:1px solid #333">{s['personal_score']:.1f}</td>
              <td style="padding:4px 8px;border-bottom:1px solid #333;color:{'#3fb950' if hold else '#8b949e'}">{hold or '—'}</td>
            </tr>"""

        html_body = f"""
        <div style="font-family:monospace;background:#0d1117;color:#e6edf3;padding:20px;max-width:600px">
          <h2 style="color:#58a6ff;margin:0 0 8px">Stock Tracker Refresh Complete</h2>
          <p style="color:#8b949e;font-size:12px">{now} | {stocks_count} stocks processed</p>
          <p style="margin:12px 0"><a href="https://{os.environ.get('GITHUB_REPO_OWNER', 'hemanth')}.github.io/{os.environ.get('GITHUB_REPO_NAME', 'stock-tracker')}/" style="color:#58a6ff">View Full Table →</a></p>
          <h3 style="color:#e6edf3;font-size:14px;margin:16px 0 8px">Top 10</h3>
          <table style="border-collapse:collapse;font-size:12px;color:#e6edf3;width:100%">
            <tr style="color:#8b949e">
              <th style="padding:4px 8px;text-align:left">#</th>
              <th style="padding:4px 8px;text-align:left">Ticker</th>
              <th style="padding:4px 8px;text-align:left">Price</th>
              <th style="padding:4px 8px;text-align:left">Intuition</th>
              <th style="padding:4px 8px;text-align:left">Upside</th>
              <th style="padding:4px 8px;text-align:left">Score</th>
              <th style="padding:4px 8px;text-align:left">Hold?</th>
            </tr>
            {top_rows}
          </table>
          <p style="color:#8b949e;font-size:10px;margin-top:16px">
            Intuition points are algorithmic estimates, not forecasts. Not investment advice.
          </p>
        </div>
        """

        resend.Emails.send({
            "from": "Stock Tracker <onboarding@resend.dev>",
            "to": ["nckhemanthreddy7@gmail.com"],
            "subject": f"Stock Tracker Refresh | {now}",
            "html": html_body,
        })
        print(f"  [Email] Sent refresh notification")
        return True

    except Exception as e:
        print(f"  [Email] Failed: {e}")
        return False
