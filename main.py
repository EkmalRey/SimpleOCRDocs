from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import io
from PIL import Image
import pytesseract
import re
from datetime import datetime
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Intelligence System", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

class DocumentProcessor:
    def __init__(self):
        # Configure tesseract path if needed (uncomment for Windows)
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pass
    
    def extract_text(self, image: Image.Image) -> str:
        """Extract text from image using OCR"""
        try:
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise HTTPException(status_code=500, detail="OCR processing failed")
    
    def classify_document(self, text: str) -> str:
        """Simple keyword-based document classification"""
        text_lower = text.lower()
        
        # Invoice keywords
        invoice_keywords = ['invoice', 'bill to', 'billing', 'amount due', 'subtotal', 'tax', 'total amount']
        # Receipt keywords  
        receipt_keywords = ['receipt', 'thank you', 'paid', 'change', 'cashier', 'transaction']
        # ID card keywords
        id_keywords = ['identity', 'id card', 'birth date', 'date of birth', 'nationality', 'id number', 'tempat/tgl lahir', 'provinsi', 'agama', 'pekerjaan']
        
        invoice_score = sum(1 for keyword in invoice_keywords if keyword in text_lower)
        receipt_score = sum(1 for keyword in receipt_keywords if keyword in text_lower)
        id_score = sum(1 for keyword in id_keywords if keyword in text_lower)
        
        if invoice_score >= receipt_score and invoice_score >= id_score:
            return "invoice"
        elif receipt_score >= id_score:
            return "receipt"
        elif id_score > 0:
            return "id_card"
        else:
            return "unknown"
    
    def extract_fields(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract key fields based on document type"""
        fields = {}
        
        if doc_type == "invoice":
            fields.update(self._extract_invoice_fields(text))
        elif doc_type == "receipt":
            fields.update(self._extract_receipt_fields(text))
        elif doc_type == "id_card":
            fields.update(self._extract_id_fields(text))
        
        return fields
    
    def _extract_invoice_fields(self, text: str) -> Dict[str, str]:
        """Extract invoice-specific fields"""
        fields = {}

        # Extract company/recipient after 'Kepada:' or 'KEPADA:'
        kepada_match = re.search(r'(?:Kepada|KEPADA)[:\s]*\n?([^\n]+)', text, re.IGNORECASE)
        if kepada_match:
            fields['company'] = kepada_match.group(1).strip()
        else:
            # Fallback to previous patterns
            company_patterns = [
                r'(?:Bill to|From|Company|Kepada):\s*([A-Za-z\s]+)',
                r'^([A-Z][A-Za-z\s&.]+)(?:\n|$)',  # First line capitalized
            ]
            for pattern in company_patterns:
                match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
                if match:
                    fields['company'] = match.group(1).strip()
                    break

        # Extract total amount (support 'TOTAL: RP 880,000' and similar)
        amount_patterns = [
            r'TOTAL[:\s]*RP[\s\.]*([\d,.]+)',  # Matches 'TOTAL: RP 880,000'
            r'(?:Total|Amount Due|Grand Total|Balance Due)[\s:]*([A-Z]{2,3}?\s*[\d,]+\.?\d*)',
            r'(?:IDR|USD|EUR|RP)\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(?:IDR|USD|EUR|RP)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                fields['total_amount'] = f"RP {value}".strip() if 'RP' in pattern.upper() else value.strip()
                break

        # Extract date (use existing logic)
        fields['date'] = self._extract_date(text)

        return fields
    
    def _extract_receipt_fields(self, text: str) -> Dict[str, str]:
        """Extract receipt-specific fields"""
        fields = {}
        
        # Extract vendor name (usually at the top)
        vendor_match = re.search(r'^([A-Z][A-Za-z\s&.]+)\n', text, re.MULTILINE)
        if vendor_match:
            fields['vendor'] = vendor_match.group(1).strip()
        
        # Extract total paid
        amount_patterns = [
            r'(?:Total|Sub\s*Total|Bayar)[\s:]*Rp[\s\.]*([\d,.]+)',  # Matches 'Total Rp 70.000' or 'Sub Total Rp 70.000'
            r'Rp[\s\.]*([\d,.]+)',                                   # Matches 'Rp 70.000'
            r'(?:Total|Paid|Amount)[\s:]*([A-Z]{2,3}?\s*[\d,.]+\.?\d*)',
            r'(?:IDR|USD|EUR)\s*([\d,.]+\.?\d*)',
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Use the captured group if available, else the whole match
                value = match.group(1) if match.lastindex else match.group(0)
                fields['total_paid'] = value.strip()
                break
        
        # Extract date
        fields['date'] = self._extract_date(text)
        
        return fields
    
    def _extract_id_fields(self, text: str) -> Dict[str, str]:
        """Extract ID card-specific fields"""
        fields = {}
        
        # Extract name
        name_patterns = [
            r'(?:Name|Full Name|Nama)[\s:]+([A-Za-z\s]+)(?:\n|Tempat|Tempat/Tgl|$)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Common name pattern
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields['name'] = match.group(1).strip()
                break
        
        # Extract ID number
        id_patterns = [
            r'(?:NIK|ID|ID Number)[\s\-:=]*([A-Za-z0-9]{12,})',
            r'(\d{10,})',  # Long number sequences
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields['id_number'] = match.group(1).strip()
                break
        
        # Extract birth date
        fields['birth_date'] = self._extract_date(text)
        
        return fields
    
    def _extract_date(self, text: str) -> str:
        """Extract date from text using various patterns"""
        date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',  # YYYY-MM-DD
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',  # DD Mon YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""

# Initialize processor
processor = DocumentProcessor()

@app.get("/", response_class=HTMLResponse)
async def frontend():
    """Serve the frontend HTML page"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api")
async def root():
    return {"message": "Document Intelligence System API", "version": "1.0.0"}

@app.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):
    """Analyze uploaded document image and extract structured information"""
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read and process image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Extract text using OCR
        raw_text = processor.extract_text(image)
        
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="No text found in image")
        
        # Classify document type
        doc_type = processor.classify_document(raw_text)
        
        # Extract key fields
        fields = processor.extract_fields(raw_text, doc_type)
        
        # Build response
        response = {
            "document_type": doc_type,
            "fields": fields,
            "raw_text": raw_text
        }
        
        logger.info(f"Successfully processed document: {doc_type}")
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
