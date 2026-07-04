import requests
from dotenv import load_dotenv

load_dotenv(".env")

def get_bot_username() -> str:
    bot_name = os.getenv("TELEGRAM_BOT_NAME")
    if bot_name and bot_name.strip():
        return bot_name.strip()
        
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or "your_test_bot_token" in token:
        return "Dmhaircarebot"
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return data["result"].get("username", "Dmhaircarebot")
    except Exception:
        pass
    return "Dmhaircarebot"

def generate_owner_activation_qr(business_id: str):
    """Generates the onboarding activation QR code and link for the salon owner."""
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "owner_qrs"))
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Construct Link
    bot_username = get_bot_username()
    activation_url = f"https://t.me/{bot_username}?start=a_{business_id}"
    
    # 2. Compile QR Code Image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(activation_url)
    qr.make(fit=True)
    
    # Charcoal QR code on white background for premium scanner contrast
    img = qr.make_image(fill_color="#1E2229", back_color="white")
    
    # 3. Save Image
    filename = f"owner_qr_{business_id}.png"
    output_path = os.path.join(output_dir, filename)
    img.save(output_path)
    
    print("\n👑 Salon Owner Onboarding QR Code Generated!")
    print(f"📍 Business ID: {business_id}")
    print(f"🔗 Activation Link: {activation_url}")
    print(f"📷 QR Code Saved To: {output_path}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Owner Onboarding QR Code & Link.")
    parser.add_argument("id", type=str, help="The business_id slug of the salon to generate the owner QR for.")
    args = parser.parse_args()
    
    generate_owner_activation_qr(args.id)
