"""
This script processes a list of Gallica documents referenced with their ARKs 
and export all images of these documents thanks to the Gallica IIIF Image API

Usage:
1. Provide the path to the ARKs file as a command-line argument.
2. Specify the image dimension ratio (between 0 and 1.0) to control the size of the downloaded images.
Example command:
>python extract.py arks.txt 0.7

Output:
- Thumbnails organized by ARK ("output/ARK" folder) 

Error Handling:
- Tracks and reports missing image files and IIIF API errors.
"""

import os
from PIL import Image, ImageDraw
import argparse
import requests

import utils

# Folders
output_dir = 'IIIF_images'

# IIIF
iiif_size = "max"
iiif_error = 0
iiif_ok = 0

# Other counters
arks = 0
image_not_found = 0

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Extract images thanks to the IIIF Image API.")
parser.add_argument("arks_file", type=str, help="Path to the ARKs file")
parser.add_argument('ratio',  type=float, default=0.7,
                    help='image dimension ratio')
args = parser.parse_args()

arks_file = args.arks_file
ratio = args.ratio

# Image size (max or pct:n)
if ratio <= 0 or ratio > 1.0:
    print ("# Error! ratio must be between 0 and 1.0 #")
    exit(1)
elif ratio == 1.0:
    iiif_size = "max"
else:
    pct = int(ratio * 100)
    iiif_size = f"pct:{pct}"
print(f"-----------------------------\n...using IIIF size: {iiif_size}")
answer = input("Continue? ")
if answer.lower() in ["n","no","non"]:
    print("...ending")
    exit(0)
   

###            MAIN           ###

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Read the arks list 
if not os.path.exists(arks_file):
    print(f"# ARKs file {arks_file} not found! #")
    exit(1)

# Load ARKs list 
with open(arks_file, 'r') as txtfile:
    for line in txtfile:
        ark = line.strip()  
        if ark:
            arks += 1
            n = utils.get_number_of_images(ark)
            if n == 0:
                image_not_found += 1
            else:
                print(f"--------------------\nProcessing ARK: {ark} with {n} images")
                ark_id = utils.get_ark_id(ark) # remove "ark:/12148/"
                for i in range(1, n+1):
                    url = utils.build_iiif_url(ark_id, i, iiif_size)                
                    output_filename = utils.format_filename(ark_id, i, "jpg")
                    iiif_error, iiif_ok = utils.export_thumbnail_iiif(url, output_dir, ark, output_filename)

print(f"--------------------------------\nARKs processed: {arks}")
print(f"ARKs not processed because of Pagination API errors: {image_not_found}")
print("----------------------------------------")
print(f"IIIF images downloaded: {iiif_ok}")
if iiif_error != 0:
    print(f"## Warning! IIIF errors: {iiif_error} ##")
