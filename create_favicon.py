#!/usr/bin/env python3
"""
Generate a minimal favicon.ico file
Run this once: python create_favicon.py
"""

import struct
import os

def create_minimal_favicon(filename="static/favicon.ico"):
    """Create a minimal 1x1 pixel favicon.ico file"""
    
    # Ensure static directory exists
    os.makedirs("static", exist_ok=True)
    
    # Minimal ICO file with a 1x1 white pixel
    # ICO header
    ico_data = bytearray()
    ico_data.extend(b'\x00\x00')  # Reserved
    ico_data.extend(b'\x01\x00')  # Type (1 = ICO)
    ico_data.extend(b'\x01\x00')  # Number of images (1)
    
    # Image directory entry
    ico_data.extend(b'\x01')      # Width (1 pixel)
    ico_data.extend(b'\x01')      # Height (1 pixel)
    ico_data.extend(b'\x00')      # Color count
    ico_data.extend(b'\x00')      # Reserved
    ico_data.extend(b'\x01\x00')  # Color planes
    ico_data.extend(b'\x20\x00')  # Bits per pixel (32)
    ico_data.extend(b'\x30\x00\x00\x00')  # Image data size (48 bytes)
    ico_data.extend(b'\x16\x00\x00\x00')  # Offset to image data (22 bytes)
    
    # Minimal BMP data (1x1 32-bit image - white pixel)
    # BMP info header
    ico_data.extend(b'\x28\x00\x00\x00')  # BMP header size (40 bytes)
    ico_data.extend(b'\x01\x00\x00\x00')  # Width (1 pixel)
    ico_data.extend(b'\x02\x00\x00\x00')  # Height (2 pixels for ICO)
    ico_data.extend(b'\x01\x00')          # Planes
    ico_data.extend(b'\x20\x00')          # Bits per pixel (32)
    ico_data.extend(b'\x00' * 24)         # Rest of header (zeros)
    
    # Pixel data: white pixel (BGRA format)
    ico_data.extend(b'\xFF\xFF\xFF\xFF')  # White pixel
    ico_data.extend(b'\x00\x00\x00\x00')  # Transparent pixel
    
    # Write file
    with open(filename, 'wb') as f:
        f.write(ico_data)
    
    print(f"✓ Created {filename} ({len(ico_data)} bytes)")
    return filename

if __name__ == "__main__":
    create_minimal_favicon()
    print("Favicon created successfully!")
