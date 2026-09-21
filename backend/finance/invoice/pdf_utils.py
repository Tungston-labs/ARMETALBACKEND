from io import BytesIO

from django.core.files.base import ContentFile

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_invoice_pdf(invoice):

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )

    width, height = A4

    y = height - 50

    pdf.setFont("Helvetica-Bold", 16)

    pdf.drawString(
        50,
        y,
        f"INVOICE - {invoice.invoice_number}"
    )

    y -= 40

    pdf.setFont("Helvetica", 10)

    pdf.drawString(
        50,
        y,
        f"Company: {invoice.company_name}"
    )

    y -= 20

    pdf.drawString(
        50,
        y,
        f"Email: {invoice.company_email}"
    )

    y -= 20

    pdf.drawString(
        50,
        y,
        f"Phone: {invoice.company_phone}"
    )

    y -= 40

    pdf.drawString(
        50,
        y,
        f"Bill To: {invoice.customer_name}"
    )

    y -= 20

    pdf.drawString(
        50,
        y,
        f"Invoice Date: {invoice.invoice_date}"
    )

    y -= 20

    pdf.drawString(
        50,
        y,
        f"Due Date: {invoice.due_date}"
    )

    y -= 40

    pdf.setFont("Helvetica-Bold", 10)

    pdf.drawString(50, y, "Particular")
    pdf.drawString(250, y, "Qty")
    pdf.drawString(300, y, "Rate")
    pdf.drawString(370, y, "VAT")
    pdf.drawString(450, y, "Amount")

    y -= 20

    pdf.setFont("Helvetica", 9)

    for item in invoice.items.all():

        pdf.drawString(
            50,
            y,
            item.particular[:30]
        )

        pdf.drawString(
            250,
            y,
            str(item.quantity)
        )

        pdf.drawString(
            300,
            y,
            str(item.rate)
        )

        pdf.drawString(
            370,
            y,
            str(item.vat_sar)
        )

        pdf.drawString(
            450,
            y,
            str(item.amount)
        )

        y -= 20

        if y < 80:

            pdf.showPage()
            y = height - 50

    y -= 20

    pdf.drawString(
        350,
        y,
        f"Subtotal: {invoice.subtotal}"
    )

    y -= 20

    pdf.drawString(
        350,
        y,
        f"Total VAT: {invoice.total_vat}"
    )

    y -= 20

    pdf.drawString(
        350,
        y,
        f"Discount: {invoice.discount}"
    )

    y -= 20

    pdf.drawString(
        350,
        y,
        f"Round Off: {invoice.round_off}"
    )

    y -= 20

    pdf.setFont("Helvetica-Bold", 11)

    pdf.drawString(
        350,
        y,
        f"Total: {invoice.total_amount}"
    )

    pdf.save()

    buffer.seek(0)

    return ContentFile(
        buffer.getvalue(),
        name=f"{invoice.invoice_number}.pdf"
    )