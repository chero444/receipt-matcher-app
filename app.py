import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io, zipfile
from fuzzywuzzy import fuzz
import fitz  # PyMuPDF is actually imported as 'fitz' from 'pymupdf'
from fpdf import FPDF

st.title("Receipt Matcher")

# Upload statement
statement_file = st.file_uploader("Upload Credit Card CSV", type="csv")
# Upload receipts
receipt_files = st.file_uploader("Upload Receipt Files", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

if statement_file and receipt_files:
    with st.spinner("Processing..."):
        # Skip to row 43 where headers start
        df = pd.read_csv(statement_file, skiprows=42)

        # Clean column headers and display them to help debug
        df.columns = df.columns.str.strip()
        st.write("Detected columns:", df.columns.tolist())

        # Try to auto-detect the vendor column
        vendor_col = None
        for col in df.columns:
            if 'item' in col.lower() or 'vendor' in col.lower() or 'merchant' in col.lower():
                vendor_col = col
                break

        if vendor_col is None:
            st.error("Could not find a vendor column (like 'ITEM', 'Vendor', or 'Merchant'). Please check the CSV.")
        else:
            df[vendor_col] = df[vendor_col].astype(str).str.lower().str.strip()

            output_pdfs = []

            for receipt in receipt_files:
                content = receipt.read()

                # Convert PDF or open image
                if receipt.name.endswith('.pdf'):
                    try:
                        import fitz  # Ensure import here in case of Streamlit Cloud module issues
                        doc = fitz.open(stream=content, filetype="pdf")
                        page = doc.load_page(0)
                        pix = page.get_pixmap()
                        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    except Exception as e:
                        st.warning(f"Failed to process PDF '{receipt.name}': {e}")
                        continue
                else:
                    image = Image.open(io.BytesIO(content))

                text = pytesseract.image_to_string(image).lower()

                # Match by vendor text only for now
                best_match = None
                best_score = 0
                for _, row in df.iterrows():
                    score = fuzz.partial_ratio(row[vendor_col], text)
                    if score > best_score:
                        best_match = row
                        best_score = score

                if best_match is not None:
                    tx_num = str(best_match['#']).zfill(2)  # Assuming '#' is transaction number column
                    vendor = best_match[vendor_col].title()
                    filename = f"{tx_num} - {vendor}.pdf"

                    pdf = FPDF()
                    pdf.add_page()
                    with io.BytesIO() as img_buffer:
                        image.save(img_buffer, format="JPEG")
                        pdf.image(img_buffer, x=10, y=10, w=180, h=0, type='JPEG')
                    pdf_bytes = pdf.output(dest='S').encode('latin1')

                    output_pdfs.append((filename, pdf_bytes))

            # Create zip for download
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for name, pdf_data in output_pdfs:
                    zipf.writestr(name, pdf_data)

            st.download_button("Download Receipts ZIP", data=zip_buffer.getvalue(), file_name="renamed_receipts.zip")
