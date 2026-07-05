import os
import sys
import argparse
import tempfile
import psycopg2
from dotenv import load_dotenv
import qrcode

# Install and import ReportLab components safely
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
except ImportError:
    print("❌ ReportLab not found. Run pip install reportlab")
    sys.exit(1)

# Add agent/ to search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent")))
load_dotenv(".env")

from src.db import get_pg_connection

def get_bot_username() -> str:
    bot_name = os.getenv("TELEGRAM_BOT_NAME")
    if bot_name and bot_name.strip():
        return bot_name.strip()
        
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or "your_test_bot_token" in token:
        return "Dmhaircarebot"
    try:
        import requests
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return data["result"].get("username", "Dmhaircarebot")
    except Exception:
        pass
    return "Dmhaircarebot"

def generate_qr_code(url: str) -> str:
    """Generates a high-quality QR code image and saves it to a temporary file."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1E2229", back_color="white")
    
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(temp_file.name)
    temp_file.close()
    return temp_file.name

def draw_flyer_pdf(output_path: str, biz_data: dict):
    """Draws a premium US Letter flyer using ReportLab vectors and canvas drawing."""
    business_name = biz_data.get("business_name", "Our Salon")
    agent_name = biz_data.get("agent_name", "Kim")
    website_url = biz_data.get("website_url", "")
    phone = biz_data.get("business_phone")
    address = biz_data.get("business_address")
    email = biz_data.get("business_email")
    business_id = biz_data.get("business_id")
    
    # 1. Setup Canvas (US Letter is 8.5 x 11 inches)
    width, height = letter
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setTitle(f"Flyer - {business_name}")
    
    # 2. Colors Definitions (Luxury Gold, Deep Charcoal, Soft Cream)
    charcoal = colors.HexColor("#1E2229")
    gold = colors.HexColor("#C5A880")
    cream = colors.HexColor("#FAF8F5")
    white = colors.HexColor("#FFFFFF")
    light_gray = colors.HexColor("#E2E8F0")
    mute_text = colors.HexColor("#64748B")
    
    # Draw Background Gradient/Base Fill
    c.setFillColor(cream)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Draw Luxury Border Frame
    c.setStrokeColor(gold)
    c.setLineWidth(1.5)
    c.rect(0.4 * inch, 0.4 * inch, width - 0.8 * inch, height - 0.8 * inch, fill=0, stroke=1)
    
    # Draw Header Top Band Accent
    c.setFillColor(charcoal)
    c.rect(0.4 * inch, height - 1.2 * inch, width - 0.8 * inch, 0.8 * inch, fill=1, stroke=0)
    
    # 3. Header Text
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2.0, height - 0.75 * inch, "Welcome to Our Digital Front Desk!")
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2.0, height - 1.0 * inch, "Instant customer assistance is now open 24/7.")
    
    # 4. Salon Presentation Name
    c.setFillColor(charcoal)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2.0, height - 2.0 * inch, business_name)
    
    c.setFont("Helvetica-Oblique", 14)
    c.setFillColor(gold)
    c.drawCentredString(width / 2.0, height - 2.35 * inch, f"Chat with {agent_name}, Our AI Receptionist")
    
    # 5. Introductory Paragraph
    c.setFillColor(charcoal)
    c.setFont("Helvetica", 11)
    intro_lines = [
        "Need to check our services, booking details, location, or general questions?",
        "Skip the wait! Simply scan the QR code below to launch our virtual assistant on Telegram.",
        f"Sarah is fully trained on all our latest salon details and is ready to assist you instantly!"
    ]
    y_offset = height - 2.8 * inch
    for line in intro_lines:
        c.drawCentredString(width / 2.0, y_offset, line)
        y_offset -= 18
        
    # 6. QR Code Card Block (Centered Card containing QR Code)
    card_w, card_h = 240, 240
    card_x = (width - card_w) / 2.0
    card_y = height - 6.8 * inch # Shifted down by 0.2 inch to prevent text overlap
    
    # Shadow rect
    c.setFillColor(colors.HexColor("#F1EDE6"))
    c.roundRect(card_x + 3, card_y - 3, card_w, card_h, 12, fill=1, stroke=0)
    
    # Main white card
    c.setFillColor(white)
    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.roundRect(card_x, card_y, card_w, card_h, 12, fill=1, stroke=1)
    
    # Generate and draw QR Code
    bot_username = get_bot_username()
    telegram_url = f"https://t.me/{bot_username}?start=v_{business_id}"
    qr_img_path = generate_qr_code(telegram_url)
    
    c.drawImage(qr_img_path, card_x + 30, card_y + 48, width=180, height=180) # Centered QR Code with balanced padding
    
    # Cleanup temp image
    try:
        os.unlink(qr_img_path)
    except Exception:
        pass
        
    # Card CTA Text
    c.setFillColor(charcoal)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2.0, card_y + 18, "👉 SCAN WITH YOUR PHONE CAMERA 💬")
    
    # 7. Instructions / Steps Block (Three columns at the bottom)
    inst_y = card_y - 1.2 * inch
    
    c.setStrokeColor(light_gray)
    c.setLineWidth(1)
    c.line(0.8 * inch, inst_y + 25, width - 0.8 * inch, inst_y + 25)
    
    step_width = (width - 1.6 * inch) / 3.0
    
    steps = [
        ("Step 1: Point & Scan", "Open your camera app", "Focus directly on the QR code"),
        ("Step 2: Tap Link", "Click the banner popup", "Open the Telegram app"),
        ("Step 3: Say Hello", 'Tap "Start" to begin', f"Ask {agent_name} anything!")
    ]
    
    for idx, (title, desc1, desc2) in enumerate(steps):
        col_x = 0.8 * inch + idx * step_width + (step_width / 2.0)
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(col_x, inst_y, title)
        
        c.setFillColor(charcoal)
        c.setFont("Helvetica", 9)
        c.drawCentredString(col_x, inst_y - 15, desc1)
        c.drawCentredString(col_x, inst_y - 27, desc2)
        
    # 8. Footer Section (Salon Details & Contact Info)
    footer_y = 1.0 * inch
    c.setStrokeColor(light_gray)
    c.setLineWidth(1)
    c.line(0.8 * inch, footer_y + 15, width - 0.8 * inch, footer_y + 15)
    
    contact_parts = []
    if phone: contact_parts.append(f"📞 {phone}")
    if email: contact_parts.append(f"📧 {email}")
    if website_url: contact_parts.append(f"🌐 {website_url.replace('https://','').replace('http://','')}")
    
    contact_str = "   |   ".join(contact_parts)
    c.setFillColor(mute_text)
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2.0, footer_y, contact_str)
    
    if address:
        c.drawCentredString(width / 2.0, footer_y - 18, f"📍 {address}")
        
    # Save Canvas Page
    c.showPage()
    c.save()

def generate_all_flyers(specific_id: str = None):
    """Queries Supabase, generates PDF files locally, and uploads them to Supabase Storage."""
    output_dir = os.path.join(tempfile.gettempdir(), "frontdesk_flyers")
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize Supabase Client for Storage Bucket uploads
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        # Automatically ensure storage bucket exists and is public
        try:
            sb.storage.create_bucket("flyers", options={"public": True})
        except Exception:
            pass  # Already exists or no permission
    except Exception as sb_err:
        print(f"⚠️ Warning: Could not initialize Supabase client for storage: {sb_err}")
        sb = None

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            if specific_id:
                cur.execute(
                    """
                    SELECT business_id, business_name, agent_name, website_url, 
                           business_phone, business_address, business_email 
                    FROM public.businesses 
                    WHERE business_id = %s
                    """, 
                    (specific_id,)
                )
            else:
                cur.execute(
                    """
                    SELECT business_id, business_name, agent_name, website_url, 
                           business_phone, business_address, business_email 
                    FROM public.businesses
                    """
                )
            rows = cur.fetchall()
            
            if not rows:
                print("⚠️ No business profiles found in the database matching selection.")
                return
                
            print(f"🎬 Compiling {len(rows)} PDF marketing flyers...")
            for row in rows:
                business_id = row[0]
                biz_data = {
                    "business_id": business_id,
                    "business_name": row[1],
                    "agent_name": row[2],
                    "website_url": row[3],
                    "business_phone": row[4],
                    "business_address": row[5],
                    "business_email": row[6]
                }
                
                filename = f"flyer_{business_id}.pdf"
                output_path = os.path.join(output_dir, filename)
                
                print(f"   ✍️ Drawing {filename}...")
                draw_flyer_pdf(output_path, biz_data)
                
                # Generate Owner Onboarding QR Code locally
                owner_qr_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "owner_qrs"))
                os.makedirs(owner_qr_dir, exist_ok=True)
                owner_filename = f"owner_qr_{business_id}.png"
                owner_qr_path = os.path.join(owner_qr_dir, owner_filename)
                
                bot_username = get_bot_username()
                activation_url = f"https://t.me/{bot_username}?start=a_{business_id}"
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(activation_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="#1E2229", back_color="white")
                qr_img.save(owner_qr_path)
                
                # Upload to Supabase Storage if connection is available
                if sb:
                    try:
                        # 1. Upload Customer PDF Flyer
                        print(f"   📤 Uploading {filename} to Supabase Storage...")
                        with open(output_path, "rb") as f:
                            sb.storage.from_("flyers").upload(
                                file=f,
                                path=filename,
                                file_options={"cache-control": "3600", "upsert": "true", "content-type": "application/pdf"}
                            )
                        public_flyer_url = sb.storage.from_("flyers").get_public_url(filename)
                        print(f"   🔗 Flyer Link: {public_flyer_url}")
                        
                        # 2. Upload Owner Onboarding QR Code Image
                        print(f"   📤 Uploading {owner_filename} to Supabase Storage...")
                        with open(owner_qr_path, "rb") as f:
                            sb.storage.from_("flyers").upload(
                                file=f,
                                path=owner_filename,
                                file_options={"cache-control": "3600", "upsert": "true", "content-type": "image/png"}
                            )
                        public_owner_qr_url = sb.storage.from_("flyers").get_public_url(owner_filename)
                        print(f"   🔗 Owner QR Link: {public_owner_qr_url}")
                        
                        # Save URLs in businesses table
                        cur.execute(
                            "UPDATE public.businesses SET flyer_url = %s, owner_qr_url = %s WHERE business_id = %s",
                            (public_flyer_url, public_owner_qr_url, business_id)
                        )
                        conn.commit()
                        print("   💾 Database updated with flyer and owner QR URLs.")
                    except Exception as upload_err:
                        print(f"   ⚠️ Upload/Database save failed: {upload_err}")
                
            print(f"\n🚀 Complete! All flyers compiled.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate PDF Marketing Flyers for registered businesses.")
    parser.add_argument("--id", type=str, help="Specific business_id to generate a flyer for.")
    args = parser.parse_args()
    
    generate_all_flyers(specific_id=args.id)
