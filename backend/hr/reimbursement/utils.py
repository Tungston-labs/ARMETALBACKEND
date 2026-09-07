from django.core.mail import EmailMessage
from django.template.loader import render_to_string

def send_reimbursement_email(reimbursement):
    subject = f"Reimbursement Request - {reimbursement.expense_category}"
    recipient = [reimbursement.to_mail]

    # Render HTML email from template
    message = render_to_string("reimbursement/email_template.html", {
        "reimbursement": reimbursement,
    })

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=None,   # will fallback to DEFAULT_FROM_EMAIL
        to=recipient,
    )
    email.content_subtype = "html"  # send as HTML

    # Attach images (if any)
    for img in reimbursement.images.all():
        email.attach_file(img.image.path)

    email.send()
