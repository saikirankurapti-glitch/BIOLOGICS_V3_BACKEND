import asyncio
from app.db.engine import init_db
from app.models.preformulation import PreformulationReport
from app.utils.report_generator import PDFReport

def test_pdf(data):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Arial', '', 11)
    
    risks = data.get('stability_risk', [])
    
    for risk in risks:
        print(f"X: {pdf.get_x()}, Y: {pdf.get_y()}")
        try:
            pdf.multi_cell(0, 8, f"- {risk}")
            print(f"Success rendering risk: {risk}")
        except Exception as e:
            print(f"FAILED rendering risk: {risk}")
            print(e)
            
async def main():
    await init_db()
    report = await PreformulationReport.find(PreformulationReport.compound_id == 'Erythromycin').sort('-_id').first_or_none()
    test_pdf(report.dict())

asyncio.run(main())
