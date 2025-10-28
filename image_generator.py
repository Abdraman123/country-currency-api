from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os

def generate_summary_image(total_countries: int, top_countries: list, timestamp: datetime):
    os.makedirs("cache", exist_ok=True)
    
    width = 800
    height = 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    draw.rectangle([0, 0, width, 100], fill='#2c3e50')
    draw.text((width // 2, 50), "Country Summary Report", fill='white', font=title_font, anchor="mm")
    
    y_offset = 130
    draw.text((50, y_offset), f"Total Countries: {total_countries}", fill='black', font=header_font)
    
    y_offset += 50
    draw.text((50, y_offset), "Top 5 Countries by GDP:", fill='black', font=header_font)
    
    y_offset += 40
    for i, country in enumerate(top_countries, 1):
        gdp_formatted = f"{country.estimated_gdp:,.2f}" if country.estimated_gdp else "N/A"
        text = f"{i}. {country.name}: ${gdp_formatted}"
        draw.text((70, y_offset), text, fill='#34495e', font=body_font)
        y_offset += 35
    
    y_offset += 30
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if timestamp else "N/A"
    draw.text((50, y_offset), f"Last Refreshed: {timestamp_str}", fill='#7f8c8d', font=body_font)
    
    img.save("cache/summary.png")
    return "cache/summary.png"