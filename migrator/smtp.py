from email.mime.text import MIMEText
import smtplib
import ssl

from migrator.extensions import config


def send_email(email, subject, body):
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["To"] = email
    msg["From"] = config.SMTP_FROM

    s = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)

    # if we have a cert, then trust it
    if config.SMTP_TLS:
        sslcontext = ssl.create_default_context()
        if config.SMTP_CERT_CA is not None:
            sslcontext.load_verify_locations(cadata=config.SMTP_CERT_CA)
        s.starttls(context=sslcontext)

    # if smtp credentials were provided, login
    if config.SMTP_USER is not None and config.SMTP_PASS is not None:
        s.login(config.SMTP_USER, config.SMTP_PASS)

    s.sendmail(config.SMTP_FROM, [email], msg.as_string())
    s.quit()


def send_report_email(results):
    # results is a dict with keys "migrated", "failure", "skipped"
    subject = f"[{config.ENV}] - migrations completed!"
    nl = "\n"
    body = f"""
<h1>Migrator finished running for today!</h1>

<h2>Summary</h2>

Migrated: {len(results['migrated'])}
Failed: {len(results['failed'])}
Skipped: {len(results['skipped'])}

<h2>Failed instances</h2>

{nl.join(results['failed'])}

        """
    send_email(config.SMTP_TO, subject, body)
