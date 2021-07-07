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
        if config.SMTP_CERT is not None:
            sslcontext.load_verify_locations(cadata=config.SMTP_CERT)
        s.starttls(context=sslcontext)

    # if smtp credentials were provided, login
    if config.SMTP_USER is not None and config.SMTP_PASS is not None:
        s.login(config.SMTP_USER, config.SMTP_PASS)

    s.sendmail(config.SMTP_FROM, [email], msg.as_string())
    s.quit()
