import os
import sys
import argparse
import qrcode

def generate_owner_activation_qr(business_id: str):
    """Generates the onboarding activation QR code and link for the salon owner."""
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "owner_qrs"))
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Construct Link
    activation_url = f"https://t.me/Dmhaircarebot?start=a_{business_id}"
    
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
