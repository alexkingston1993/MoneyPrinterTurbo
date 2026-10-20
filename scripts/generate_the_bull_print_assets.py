import os
from PIL import Image, ImageOps

LOGO_SRC = "/Users/apple/.gemini/antigravity-ide/brain/2ccf8b84-0b80-4489-9cbc-3c5709cc4937/the_bull_print_logo_1792515303362.jpg"
COVER_SRC = "/Users/apple/.gemini/antigravity-ide/brain/2ccf8b84-0b80-4489-9cbc-3c5709cc4937/the_bull_print_cover_1792515370628.jpg"
BRAND_DIR = "/Users/apple/Documents/Antigravity/untitled folder/brand_assets"

os.makedirs(BRAND_DIR, exist_ok=True)

logo_img = Image.open(LOGO_SRC).convert("RGBA")
cover_img = Image.open(COVER_SRC).convert("RGBA")

print(f"Loaded logo: {logo_img.size}")
print(f"Loaded cover: {cover_img.size}")

# Square Logo Sizes
logo_targets = {
    "logo_master_1024x1024.png": (1024, 1024),
    "youtube_profile_800x800.png": (800, 800),
    "twitter_avatar_400x400.png": (400, 400),
    "linkedin_company_logo_400x400.png": (400, 400),
    "instagram_profile_320x320.png": (320, 320),
    "website_favicon_192x192.png": (192, 192),
    "website_favicon_32x32.png": (32, 32),
}

for filename, size in logo_targets.items():
    resized = logo_img.resize(size, Image.Resampling.LANCZOS)
    out_path = os.path.join(BRAND_DIR, filename)
    resized.save(out_path, format="PNG", optimize=True)
    print(f"Saved {filename} ({size[0]}x{size[1]})")

# Create favicon.ico in root and brand_assets
ico_path_root = "/Users/apple/Documents/Antigravity/untitled folder/favicon.ico"
ico_path_brand = os.path.join(BRAND_DIR, "favicon.ico")
favicon_img = logo_img.resize((64, 64), Image.Resampling.LANCZOS)
favicon_img.save(ico_path_root, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
favicon_img.save(ico_path_brand, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print("Saved favicon.ico")

# Cover & Banner Targets with Smart Center Crop
cover_targets = {
    "cover_master_1920x1080.png": (1920, 1080),
    "youtube_banner_2560x1440.png": (2560, 1440),
    "twitter_header_1500x500.png": (1500, 500),
    "linkedin_banner_1584x396.png": (1584, 396),
    "facebook_cover_820x312.png": (820, 312),
    "opengraph_social_card_1200x630.png": (1200, 630),
}

for filename, (tw, th) in cover_targets.items():
    # Use ImageOps.fit for high quality centering crop without distortion
    cropped_banner = ImageOps.fit(cover_img, (tw, th), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    out_path = os.path.join(BRAND_DIR, filename)
    cropped_banner.save(out_path, format="PNG", optimize=True)
    print(f"Saved {filename} ({tw}x{th})")

print("All brand assets generated successfully!")
