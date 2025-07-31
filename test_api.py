"""
Test script for the Document Intelligence System
Creates sample images with text to test OCR and classification
"""

import requests
from PIL import Image, ImageDraw, ImageFont
import io
import os

def create_sample_invoice():
    """Create a sample invoice image for testing"""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a default font, fallback to basic if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        small_font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Invoice content
    text_lines = [
        "BFI TECH",
        "Software Development Company",
        "",
        "INVOICE",
        "",
        "Bill to: Client Company Ltd",
        "Date: 2025-07-31",
        "",
        "Services:",
        "Software Development    IDR 2,000,000",
        "Consulting              IDR 450,000",
        "",
        "Total Amount: IDR 2,450,000"
    ]
    
    y = 50
    for line in text_lines:
        if line == "BFI TECH" or line == "INVOICE":
            draw.text((50, y), line, fill='black', font=font)
        else:
            draw.text((50, y), line, fill='black', font=small_font)
        y += 35
    
    return img

def create_sample_receipt():
    """Create a sample receipt image for testing"""
    img = Image.new('RGB', (400, 500), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    text_lines = [
        "SUPERMARKET ABC",
        "123 Main Street",
        "",
        "RECEIPT",
        "",
        "Date: 2025-07-31",
        "Cashier: John",
        "",
        "Items:",
        "Bread         5,000",
        "Milk         12,000", 
        "Eggs          8,000",
        "",
        "Total Paid: IDR 25,000",
        "",
        "Thank you for shopping!"
    ]
    
    y = 30
    for line in text_lines:
        draw.text((20, y), line, fill='black', font=font)
        y += 25
    
    return img

def test_api_endpoint(image, filename):
    """Test the /analyze endpoint with an image"""
    
    # Save image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    try:
        # Make API request
        response = requests.post(
            "http://localhost:8000/analyze",
            files={"file": (filename, img_byte_arr, "image/png")}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ {filename} Analysis Results:")
            print(f"Document Type: {result['document_type']}")
            print("Extracted Fields:")
            for key, value in result['fields'].items():
                print(f"  {key}: {value}")
            print(f"Raw Text Preview: {result['raw_text'][:100]}...")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure the FastAPI server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run the test suite"""
    print("🧪 Testing Document Intelligence System")
    print("=" * 50)
    
    # Create sample images
    print("📄 Creating sample documents...")
    invoice_img = create_sample_invoice()
    receipt_img = create_sample_receipt()
    
    # Save sample images for reference
    os.makedirs("samples", exist_ok=True)
    invoice_img.save("samples/sample_invoice.png")
    receipt_img.save("samples/sample_receipt.png")
    print("✅ Sample images saved to 'samples/' directory")
    
    # Test API endpoints
    print("\n🔍 Testing API endpoints...")
    test_api_endpoint(invoice_img, "sample_invoice.png")
    test_api_endpoint(receipt_img, "sample_receipt.png")
    
    print("\n" + "=" * 50)
    print("🎯 Test completed!")
    print("💡 You can also test with your own images using:")
    print("   curl -X POST \"http://localhost:8000/analyze\" -F \"file=@your_image.jpg\"")

if __name__ == "__main__":
    main()
