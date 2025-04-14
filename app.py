import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io, zipfile
from fuzzywuzzy import fuzz
from pdf2image import convert_from_bytes
from fpdf import FPDF

st.title("📎 Receipt Matcher")

statement_file = st.file_uploader("Upload Credit Card Statement CSV", type="csv")
receipt_files = st.file_uploader("Upload Receipt Files", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

if statement_file and receipt_files:
    with st.spinner("Processing..."):
        df = pd.read_csv(statement_file)
        df['Vendor'] = df['Vendor'].astype(str).str.lower().str.strip()

        output_pdfs = []

        for receipt in receipt_files:
            content = receipt.read()
            if receipt.name.endswith('.pdf'):
                pages = convert_from_bytes(content)
                image = pages[0]
            else:
                image = Image.open(io.BytesIO(content))

            text = pytesseract.image_to_string(image).lower()

            best_match = None
            best_score = 0
            for _, row in df.iterrows():
                score = fuzz.partial_ratio(row['Vendor'], text)
                if score > best_score and abs(float(row['Amount']) - sum(float(s.replace('$','')) for s in text.split() if s.replace('$','').replace('.','',1).isdigit())) < 1.00:
                    best_match = row
                    best_score = score

            if best_match is not None:
                tx_num = str(best_match['TransactionNumber']).zfill(2)
                vendor = best_match['Vendor'].title()
                filename = f"{tx_num} - {vendor}.pdf"

                pdf = FPDF()
                pdf.add_page()
                temp_path = f"/tmp/{receipt.name}.jpg"
                image.save(temp_path)
                pdf.image(temp_path, x=10, y=10, w=180)
                os.remove(temp_path)

                pdf_bytes = pdf.output(dest='S').encode('latin1')
                output_pdfs.append((filename, pdf_bytes))

        if output_pdfs:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for name, pdf_data in output_pdfs:
                    zipf.writestr(name, pdf_data)

            st.success("Receipts matched and renamed!")
            st.download_button("📦 Download ZIP", data=zip_buffer.getvalue(), file_name="renamed_receipts.zip", mime="application/zip")
        else:
            st.warning("No matching receipts found.")
