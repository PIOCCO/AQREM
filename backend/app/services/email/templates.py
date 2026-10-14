from __future__ import annotations

from html import escape


def _layout(*, title: str, body_html: str) -> tuple[str, str]:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{escape(title)}</title></head>
<body style="margin:0;background:#f4f4f5;font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#18181b;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:12px;border:1px solid #e4e4e7;">
        <tr><td style="padding:20px 24px;border-bottom:3px solid #0d9488;">
          <span style="font-weight:700;font-size:18px;letter-spacing:0.02em;">AQREM</span>
        </td></tr>
        <tr><td style="padding:24px;font-size:15px;line-height:1.55;">{body_html}</td></tr>
        <tr><td style="padding:16px 24px;font-size:12px;color:#71717a;border-top:1px solid #e4e4e7;">
          AQREM — evidence-backed questionnaire platform
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
    return html, title


def admin_invitation_email(
    *,
    invitee_name: str,
    organization_name: str,
    invitation_url: str,
    inviter_label: str,
    expires_at_label: str,
    personal_message: str | None,
) -> tuple[str, str, str]:
    subject = f"You're invited to administer {organization_name} on AQREM"
    msg_block = ""
    if personal_message:
        msg_block = f'<p style="background:#f4f4f5;padding:12px;border-radius:8px;">{escape(personal_message)}</p>'
    body = f"""
      <p>Hi {escape(invitee_name)},</p>
      <p><strong>{escape(inviter_label)}</strong> invited you to join <strong>{escape(organization_name)}</strong> as an organization administrator.</p>
      {msg_block}
      <p style="margin:24px 0;"><a href="{escape(invitation_url)}" style="display:inline-block;background:#0d9488;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600;">Accept invitation</a></p>
      <p style="font-size:13px;color:#52525b;">This link expires on {escape(expires_at_label)}. You will need a verification code sent to this email to finish setup.</p>
      <p style="font-size:12px;color:#71717a;word-break:break-all;">{escape(invitation_url)}</p>
    """
    html, _ = _layout(title=subject, body_html=body)
    text = (
        f"Hi {invitee_name},\n\n"
        f"{inviter_label} invited you to administer {organization_name} on AQREM.\n\n"
        f"Accept: {invitation_url}\n\n"
        f"Expires: {expires_at_label}\n"
    )
    return subject, html, text


def member_invitation_email(
    *,
    invitee_name: str,
    organization_name: str,
    invitation_url: str,
    expires_at_label: str,
) -> tuple[str, str, str]:
    subject = f"Join {organization_name} on AQREM"
    body = f"""
      <p>Hi {escape(invitee_name)},</p>
      <p>You have been invited to join <strong>{escape(organization_name)}</strong>.</p>
      <p style="margin:24px 0;"><a href="{escape(invitation_url)}" style="display:inline-block;background:#0d9488;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600;">Accept invitation</a></p>
      <p style="font-size:13px;color:#52525b;">Expires {escape(expires_at_label)}.</p>
      <p style="font-size:12px;color:#71717a;word-break:break-all;">{escape(invitation_url)}</p>
    """
    html, _ = _layout(title=subject, body_html=body)
    text = f"Join {organization_name}: {invitation_url}\nExpires: {expires_at_label}\n"
    return subject, html, text


def verification_code_email(*, organization_name: str, purpose: str, code: str) -> tuple[str, str, str]:
    subject = f"Your AQREM verification code — {organization_name}"
    body = f"""
      <p>Use this verification code to {escape(purpose)}:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:0.25em;font-family:ui-monospace,monospace;color:#0d9488;">{escape(code)}</p>
      <p style="font-size:13px;color:#52525b;">The code expires in 10 minutes and can only be used once. If you did not request this, you can ignore this email.</p>
    """
    html, _ = _layout(title=subject, body_html=body)
    text = (
        f"Your AQREM verification code for {organization_name} ({purpose}): {code}\n"
        "Expires in 10 minutes.\n"
    )
    return subject, html, text


def password_reset_email(*, reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your AQREM password"
    body = f"""
      <p>We received a request to reset your password.</p>
      <p style="margin:24px 0;"><a href="{escape(reset_url)}" style="display:inline-block;background:#0d9488;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600;">Reset password</a></p>
      <p style="font-size:12px;color:#71717a;">If you did not request this, ignore this email.</p>
    """
    html, _ = _layout(title=subject, body_html=body)
    text = f"Reset your AQREM password: {reset_url}\n"
    return subject, html, text
