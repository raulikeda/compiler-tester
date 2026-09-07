# receives file name in sys.argv and fill the transparent pixels with white color
import sys
from PIL import Image

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fill_png.py <image_file>")
        sys.exit(1)
    file_name = sys.argv[1]
    img = Image.open(file_name)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        if item[3] == 0:  # transparent pixel
            new_data.append((255, 255, 255, 255))  # white color
        else:
            new_data.append(item)
    img.putdata(new_data)
    img.save(file_name)