# def generate_payslip_pdf(data):
#     from io import BytesIO
#     from reportlab.lib.pagesizes import A4
#     from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
#     from reportlab.lib.styles import getSampleStyleSheet
#     from reportlab.lib import colors


#     from reportlab.platypus import (
#     SimpleDocTemplate,
#     Paragraph,
#     Spacer,
#     Table,
#     TableStyle,
#     Image,
# )
#     from reportlab.lib.units import inch
#     from reportlab.lib.enums import TA_CENTER
#     from reportlab.lib.styles import ParagraphStyle
#     from io import BytesIO
#     import requests
        

#     buffer = BytesIO()
#     doc = SimpleDocTemplate(
#     buffer,
#     pagesize=A4,
#     leftMargin=20,
#     rightMargin=20,
#     topMargin=20,
#     bottomMargin=20,
# )
#     elements = []
#     styles = getSampleStyleSheet()

#     elements.append(Paragraph(f"<b>Payslip for {data['employee_name']}</b>", styles["Title"]))
#     elements.append(Paragraph(f"Month: {data['month']} / {data['year']}", styles["Normal"]))
#     elements.append(Spacer(1, 12))
#     company = data["company"]

#     logo = ""

#     if company.get("logo_url"):
#         try:
#             response = requests.get(company["logo_url"])

#             if response.status_code == 200:
#                 logo = Image(BytesIO(response.content))
#                 logo.drawWidth = 70
#                 logo.drawHeight = 70
#         except:
#             logo = ""

#         company_info = Paragraph(
#         f"""
#         <font size="18"><b>{company['name']}</b></font><br/>
#         {company['address']}<br/>
#         {company['email']}<br/>
#         {company['contact_number']}
#         """,
#         styles["Normal"],
#     )

#     header = Table(
#         [[company_info, logo]],
#         colWidths=[430,80]
#     )
#     header.setStyle(TableStyle([
#     ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#16213E")),
#     ("TEXTCOLOR",(0,0),(-1,-1),colors.white),
#     ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
#     ("BOTTOMPADDING",(0,0),(-1,-1),12),
#     ("TOPPADDING",(0,0),(-1,-1),12),
# ]))

#     # Employee details
#     emp_table = [
#         ["Employee ID", data["employee_id"]],
#         ["Department", data["department"]],
#         ["Designation", data["designation"]],
#         ["Email", data["email"]],
#     ]
#     elements.append(header)
#     elements.append(Spacer(1,20))
#     elements.append(Table(emp_table))
#     elements.append(Spacer(1, 12))

#     # Earnings
#     earnings_table = [["Earnings", "Amount ()"]]
#     for e in data["earnings"]:
#         earnings_table.append([e["label"], f"{e['amount']:.2f}"])
#     earnings_table.append(["Gross Earnings", f"{data['gross_earnings']:.2f}"])
#     elements.append(Table(earnings_table))
#     elements.append(Spacer(1, 12))

#     # Deductions
#     deductions_table = [["Deductions", "Amount ()"]]
#     for d in data["deductions"]:
#         deductions_table.append([d["label"], f"{d['value']:.2f}"])
#     deductions_table.append(["Total Deductions", f"{data['total_deductions']:.2f}"])
#     elements.append(Table(deductions_table))
#     elements.append(Spacer(1, 12))

#     # Summary
#     summary_table = [
#         ["Working Days", data["working_days"]],
#         ["Days Present", data["days_present"]],
#         ["LOP Days", data["lop_days"]],
#         ["LOP Amount", f"{data['lop_amount']:.2f}"],
#         ["Net Pay", f"{data['net_pay']:.2f}"],
#     ]
#     elements.append(Table(summary_table))

#     doc.build(elements)
#     pdf = buffer.getvalue()
#     buffer.close()
#     return pdf


import os
import tempfile
import urllib.request
from io import BytesIO
 
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
 
# ── palette (lifted directly from PayrollDetailsView.styles.js) ──
NAVY = colors.HexColor("#0f172a")
NAVY_TEXT = colors.HexColor("#f1f5f9")
NAVY_MUTED = colors.HexColor("#94a3b8")
BORDER = colors.HexColor("#e5e7eb")
THEAD_BG = colors.HexColor("#f9fafb")
MUTED = colors.HexColor("#6b7280")
VALUE = colors.HexColor("#111827")
ROW_LINE = colors.HexColor("#f3f4f6")
 
PAGE_WIDTH, _ = A4
MARGIN = 20 * mm if False else 20  # keep tight margins like the web padding
CONTENT_WIDTH = PAGE_WIDTH - 2 * 25  # matches leftMargin/rightMargin below
 
styles = getSampleStyleSheet()
 
label_style = ParagraphStyle(
    "Label", parent=styles["Normal"], fontSize=8.5, textColor=MUTED, leading=11
)
value_style = ParagraphStyle(
    "Value",
    parent=styles["Normal"],
    fontSize=9.5,
    textColor=VALUE,
    leading=12,
    alignment=2,  # right
)
value_style_bold = ParagraphStyle(
    "ValueBold", parent=value_style, fontName="Helvetica-Bold"
)
th_style = ParagraphStyle(
    "TH", parent=styles["Normal"], fontSize=8, textColor=MUTED, leading=10,
    fontName="Helvetica-Bold",
)
th_style_right = ParagraphStyle("THRight", parent=th_style, alignment=2)
td_style = ParagraphStyle("TD", parent=styles["Normal"], fontSize=9, textColor=VALUE, leading=12)
td_style_right = ParagraphStyle("TDRight", parent=td_style, alignment=2)
td_style_bold = ParagraphStyle("TDBold", parent=td_style, fontName="Helvetica-Bold")
td_style_bold_right = ParagraphStyle("TDBoldRight", parent=td_style_right, fontName="Helvetica-Bold")
company_name_style = ParagraphStyle(
    "CompanyName", parent=styles["Normal"], fontSize=14, textColor=NAVY_TEXT,
    fontName="Helvetica-Bold", leading=17,
)
company_text_style = ParagraphStyle(
    "CompanyText", parent=styles["Normal"], fontSize=8.5, textColor=NAVY_MUTED, leading=12,
)
title_style = ParagraphStyle(
    "PayslipTitle", parent=styles["Heading2"], alignment=TA_CENTER,
    textColor=VALUE, fontSize=15, spaceAfter=0,
)
footer_style = ParagraphStyle(
    "Footer", parent=styles["Normal"], fontSize=8, textColor=MUTED, alignment=TA_CENTER,
)
 
 
def _fmt(value):
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"
 
 
def _fmt_date(value):
    if not value:
        return "----"
    # value may already be a date string like "2024-05-01"
    try:
        from datetime import datetime
 
        d = datetime.fromisoformat(str(value)[:10])
        return d.strftime("%d/%b/%Y")
    except Exception:
        return str(value)
 
 
def _month_name(month):
    """Matches the web app's `new Date(year, month - 1).toLocaleString(..., { month: 'long' })`.
 
    `month` arrives from the Django serializer as an int (1-12) since the view does
    `month=int(month)` when querying EmployeePayrollRecord. Falls back gracefully if a
    month name string is passed instead (e.g. during local testing).
    """
    import calendar
 
    try:
        return calendar.month_name[int(month)]
    except (ValueError, TypeError, IndexError):
        return str(month)
 
 
def _company_header(company):
    """Dark navy banner: company text left, logo right — mirrors <CompanyHeader>."""
    logo_cell = ""
    tmp_path = None
    if company.get("logo_url"):
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            urllib.request.urlretrieve(company["logo_url"], tmp.name)
            tmp_path = tmp.name
            logo_cell = Image(tmp_path, width=44, height=44)
        except Exception:
            logo_cell = ""
 
    info = Paragraph(
        f"<para>{company.get('name', '')}</para>",
        company_name_style,
    )
    lines = [
        company.get("address", ""),
        company.get("email", ""),
        company.get("contact_number", ""),
    ]
    text_block = [info]
    for line in lines:
        if line:
            text_block.append(Paragraph(line, company_text_style))
 
    inner = Table(
        [[text_block, logo_cell]],
        colWidths=[CONTENT_WIDTH - 70, 70],
    )
    inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (0, 0), 16),
                ("RIGHTPADDING", (1, 0), (1, 0), 16),
                ("ROUNDEDCORNERS", [8, 8, 8, 8]),
            ]
        )
    )
    return inner, tmp_path
 
 
def _info_card(rows):
    """Two-column key/value card with light borders — mirrors <InfoTable>/<InfoRow>."""
    data = [
        [Paragraph(label, label_style), Paragraph(str(value if value not in (None, "") else "—"), value_style)]
        for label, value in rows
    ]
    t = Table(data, colWidths=[(CONTENT_WIDTH - 20) / 2 * 0.42, (CONTENT_WIDTH - 20) / 2 * 0.58])
    style = [
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(len(data) - 1):
        style.append(("LINEBELOW", (0, i), (-1, i), 0.5, ROW_LINE))
    t.setStyle(TableStyle(style))
    return t
 
 
def _data_table(header_left, header_right, rows, bold_last=False, dark_last=False):
    """Generic bordered table with uppercase muted header row — mirrors <TableWrapper><Table>."""
    data = [[Paragraph(header_left, th_style), Paragraph(header_right, th_style_right)]]
    for i, (left, right) in enumerate(rows):
        is_last = i == len(rows) - 1
        l_style = td_style_bold if (bold_last and is_last) else td_style
        r_style = td_style_bold_right if (bold_last and is_last) else td_style_right
        if dark_last and is_last:
            l_style = ParagraphStyle("l", parent=l_style, textColor=NAVY_TEXT)
            r_style = ParagraphStyle("r", parent=r_style, textColor=NAVY_TEXT)
        data.append([Paragraph(str(left), l_style), Paragraph(str(right), r_style)])
 
    col = (CONTENT_WIDTH - 20) / 2
    t = Table(data, colWidths=[col * 0.62, col * 0.38])
    style = [
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), THEAD_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(data) - 1):
        style.append(("LINEBELOW", (0, i), (-1, i), 0.5, ROW_LINE))
    if dark_last:
        style.append(("BACKGROUND", (0, -1), (-1, -1), NAVY))
    t.setStyle(TableStyle(style))
    return t
 
 
def _side_by_side(left_table, right_table):
    outer = Table([[left_table, right_table]], colWidths=[(CONTENT_WIDTH - 20) / 2] * 2)
    outer.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 20),
                ("LEFTPADDING", (1, 0), (1, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return outer
 
 
def generate_payslip_pdf(data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25,
    )
 
    elements = []
    tmp_logo_path = None
 
    company = data.get("company") or {}
    if company:
        header, tmp_logo_path = _company_header(company)
        elements.append(header)
        elements.append(Spacer(1, 18))
 
    month = _month_name(data.get("month"))
    year = data.get("year")
    elements.append(Paragraph(f"Payslip &ndash; {month} {year}", title_style))
    elements.append(Spacer(1, 16))
 
    # ── employee info: two cards side by side ──
    left_card = _info_card(
        [
            ("Employee Name", data.get("employee_name")),
            ("Department", data.get("department")),
            ("Account Number", data.get("account_number")),
        ]
    )
    right_card = _info_card(
        [
            ("Employee ID", data.get("employee_id")),
            ("Designation", data.get("designation")),
            ("Joining Date", _fmt_date(data.get("joining_date"))),
        ]
    )
    elements.append(_side_by_side(left_card, right_card))
    elements.append(Spacer(1, 16))
 
    # ── earnings & work summary ──
    # NOTE: data["earnings"] from EmployeePayrollRecordSerializer is already a full
    # breakdown (Basic Salary, Housing Allowance, Transportation, Special Allowance,
    # Incentive) whose amounts sum to gross_earnings. data["basic_salary"] (via
    # fields="__all__") is a *different* number — the raw bank_details base salary
    # before the percentage split — so it must NOT be added again here or the totals
    # would be double-counted.
    earnings_rows = [(e.get("label", ""), _fmt(e.get("amount"))) for e in (data.get("earnings") or [])]
    earnings_rows.append(("Gross Earnings", _fmt(data.get("gross_earnings"))))
    earnings_table = _data_table("Earnings", "Amount", earnings_rows, bold_last=True)
 
    lop_days = data.get("lop_days") or 0
    lop_text = _fmt(data.get("lop_amount"))
    if lop_days:
        lop_text += f" ({lop_days} day{'s' if lop_days > 1 else ''})"
    work_rows = [
        ("Total Working Days", f"{data.get('working_days', '-')} Days"),
        ("No. of Days Paid", f"{data.get('days_present', '-')} Days"),
        ("Loss of Pay", lop_text),
    ]
    work_table = _data_table("Work Summary", "Days / Amount", work_rows)
    elements.append(_side_by_side(earnings_table, work_table))
    elements.append(Spacer(1, 14))
 
    # ── deduction breakdown & pay summary ──
    deduction_rows = [(d.get("label", ""), _fmt(d.get("value"))) for d in (data.get("deductions") or [])]
    deduction_rows.append(("Total Deductions", _fmt(data.get("total_deductions"))))
    deduction_table = _data_table("Deduction Breakdown", "Amount", deduction_rows, bold_last=True)
 
    summary_rows = [
        ("Gross Pay", _fmt(data.get("gross_earnings"))),
        ("Deductions", _fmt(data.get("total_deductions"))),
        ("Net Pay", _fmt(data.get("net_pay"))),
    ]
    summary_table = _data_table(
        "Pay Summary", "Amount", summary_rows, bold_last=True, dark_last=True
    )
    elements.append(_side_by_side(deduction_table, summary_table))
    elements.append(Spacer(1, 20))
 
    elements.append(Paragraph("This is a computer generated payslip.", footer_style))
 
    doc.build(elements)
 
    if tmp_logo_path:
        try:
            os.unlink(tmp_logo_path)
        except Exception:
            pass
 
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
 
 
if __name__ == "__main__":
    # Shaped like what EmployeePayrollRecordSerializer(record, context={"request": request}).data
    # actually returns in PayslipDownloadView — month is an int (record.month), joining_date is
    # a DRF DateField (ISO "YYYY-MM-DD" string). This mirrors the actual output of
    # EmployeePayrollRecordSerializer.to_representation() in payroll/serializers.py —
    # not a guess. Note "basic_salary" here is the raw model field (bank_details base
    # salary), which is intentionally NOT rendered directly in the PDF; the "earnings"
    # list below (Basic Salary / Housing Allowance / Transportation / Special
    # Allowance / Incentive) is the real, already-split breakdown that sums to
    # gross_earnings.
    sample = {
        # from source="employee.*" fields
        "employee_name": "Anjali Menon",
        "department": "Engineering",
        "employee_id": "EMP-1042",
        "designation": "Senior Developer",
        "email": "anjali.menon@acmetech.com",
        "joining_date": "2022-03-15",
 
        # plain EmployeePayrollRecord model fields (fields = "__all__")
        "account_number": "XXXXXX4821",
        "status": "Paid",
        "month": 7,
        "year": 2026,
        "basic_salary": "38000.00",       # raw bank_details value — not used directly in PDF
        "salary_increment": "0.00",
        "housing_allowance": "0.00",      # model-level placeholder; real split value is in "earnings"
        "transportation": "0.00",
        "tds_deduction_amount": "1200.00",
        "deduction_amount": "500.00",
        "deduction_type": "Loan EMI",
        "deduction_reason": "Salary advance repayment",
        "incentive_amount": "3000.00",
        "incentive_type": "Performance Bonus",
        "incentive_reason": "Q2 target achieved",
 
        # computed fields added in to_representation()
        "working_days": 26.0,
        "days_present": 24.5,
        "approved_leave_days": 0.5,
        "lop_days": 1.0,
        "lop_amount": "1730.77",
        "total_increment_amount": 0.0,
        "increment_history": [],
        "gross_earnings": "41000.00",
        "total_deductions": "3430.77",
        "net_pay": "37569.23",
 
        "earnings": [
            {"label": "Basic Salary", "amount": "20500.00"},
            {"label": "Housing Allowance", "amount": "8200.00"},
            {"label": "Transportation", "amount": "4100.00"},
            {"label": "Special Allowance", "amount": "5200.00"},
            {"label": "Incentive", "amount": "3000.00"},
        ],
        "deductions": [
            {"label": "TDS Deduction", "value": "1200.00"},
            {"label": "Loss of Pay", "value": "1730.77"},
            {"label": "Loan EMI", "value": "500.00"},
        ],
 
        "company": {
            "name": "Acme Technologies Pvt Ltd",
            "address": "4th Floor, Infopark, Kochi, Kerala",
            "email": "hr@acmetech.com",
            "contact_number": "+91 98765 43210",
            "logo_url": "",
        },
    }
    with open("/mnt/user-data/outputs/sample_payslip.pdf", "wb") as f:
        f.write(generate_payslip_pdf(sample))
    print("done")
 