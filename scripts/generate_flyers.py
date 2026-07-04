import sys
import argparse
from utility.generate_flyers import generate_all_flyers

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate PDF Marketing Flyers for registered businesses.")
    parser.add_argument("--id", type=str, help="Specific business_id to generate a flyer for.")
    args = parser.parse_args()
    
    generate_all_flyers(specific_id=args.id)
