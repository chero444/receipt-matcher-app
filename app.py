import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io, zipfile
from fuzzywuzzy import fuzz
import fitz  # PyMuPDF is actually imported as 'fitz' from 'pymupdf'
from fpdf import FPDF
import tempfile

st.title("Receipt Matcher")

# Upload statement
statement_file = st.file_uploader("Upload Credit Card CSV", type="csv")
# Upload receipts
receipt_files = st.file_uploader("Upload Receipt Files", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

if statement_file and receipt_files:
    # Skip to row 43 where headers start
    df = pd.read_csv(statement_file, skiprows=42)

    # Clean column headers and display them to help debug
    df.columns = df.columns.str.strip()
    st.write("Detected columns:", df.columns.tolist())

    # Let user select vendor and transaction number columns manually
    vendor_col = st.selectbox("Select the Vendor column", df.columns)
    tx_col = st.selectbox("Select the Transaction Number column", df.columns, index=df.columns.get_loc("Receipt Order") if "Receipt Order" in df.columns else 0)

    if st.button("Start Matching Receipts"):
        with st.spinner("Processing..."):
            df[vendor_col] = df[vendor_col].astype(str).str.lower().str.strip()

            output_pdfs = []

            for receipt in receipt_files:
                content = receipt.read()

                # Convert PDF or open image
                if receipt.name.endswith('.pdf'):
                    try:
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
                st.write(f"**{receipt.name}** text preview:", text[:500])

                # Match by vendor text only for now
                best_match = None
                best_score = 0
                for _, row in df.iterrows():
                    score = fuzz.partial_ratio(row[vendor_col], text)
                    if score > best_score:
                        best_match = row
                        best_score = score

                if best_match is not None:
                    tx_num = str(best_match[tx_col]).zfill(2)
                    vendor = best_match[vendor_col].title()
                    st.success(f"Matched '{receipt.name}' to transaction #{tx_num} - {vendor}")

                    filename = f"{tx_num} - {vendor}.pdf"

                    pdf = FPDF()
                    pdf.add_page()
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_img:
                        image.save(temp_img, format="JPEG")
                        temp_img_path = temp_img.name

                    pdf.image(temp_img_path, x=10, y=10, w=180, h=0)
                    pdf_bytes = pdf.output(dest='S').encode('latin1')

                    output_pdfs.append((filename, pdf_bytes))

            # Create zip for download
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for name, pdf_data in output_pdfs:
                    zipf.writestr(name, pdf_data)

            st.download_button("Download Receipts ZIP", data=zip_buffer.getvalue(), file_name="renamed_receipts.zip")
