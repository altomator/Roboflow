"""
This script processes COCO JSON annotations to extract bounding boxes, overlay them on images, 
and generate thumbnails. It also integrates with an ARK database to associate images with ARK 
identifiers and generates metadata for further processing.

Key Features:
- Parses COCO JSON files to extract bounding box annotations.
- Overlays bounding boxes and category labels on images.
- Generates thumbnails for bounding boxes and saves them in organized directories.
- Supports integration with the Gallica IIIF API to download high-resolution thumbnails.
- Associates images with ARK identifiers using a provided ARK database.
- Generates metadata in CSV format for processed images and bounding boxes (for further import in Panoptic tool).
- Generates Supervision format files for each ARK and view.
- Handles errors such as missing ARK identifiers or missing image files.

Inputs needeed:
- COCO JSON file (`_annotations.coco.json`) in the specified COCO folder + associated images.
- ARK database CSV file (`arks_database.csv`) with titles and ARK identifiers.

Parameters:
- The path to the COCO folder must be provided as a command-line argument
- The ratio between the image original scan size and the size of the image imported in Roboflow must be provided.
# If the image was downloaded using the IIIF Image API, this is the pct:n parameter; for example, 0.7 for pct:70.
# If the image was downloaded at its maximum size, the ratio is 1.0
- Set the -i option to enable downloading high-resolution thumbnails via the IIIF Gallica API.

Example command:
>python extract_box.py test 0.7 -i

Output:
- ARKs processed are logged in `arks_list.csv`
- Annotated images with bounding boxes saved in the "output" directory.
- Thumbnails organized by ARK ("output/iiif_thumbs" folder) and category ("output/thumbs" folder).
- Metadata CSV file ("output/processed_data.csv") for further processing. One line per bounding box.
- Metadata CSV file ("output/processed_data_pano.csv") for Panoptic import (one line per bounding box).
- Supervision JSON files in the "output/SV" folder (one file per ARK and view).

Error Handling:
- Logs missing ARK identifiers to `arks_errors.txt`.
- Tracks and reports missing image files and IIIF API errors.
"""

import json
import os
from PIL import Image, ImageDraw
import argparse
import requests
import csv
import unicodedata
import pandas as pd

import utils


# Roboflow model:
model = "snooptypo/2"

# IIIF
iiif_error = 0
iiif_ok = 0

# Folders
output_dir = 'output' # general output folder
thumbs_dir = "thumbs"
iiif_thumbs_dir = "IIIF_thumbs"
sv_dir = os.path.join(output_dir, "SV") # Supervision JSON files

# the database of ARK identifiers + their title 
arks_data_file = "arks_database.csv"
ark_dict = {}

# the list of titles with no ARK found in the database
arks_errors_file = os.path.join(output_dir,"arks_errors.txt")

# the list of ARK identifiers found in the annotations
processed_arks_file = os.path.join(output_dir,"processed_arks_list.csv")
processed_arks = set()

# Create a DataFrame to store processed data
processed_data = pd.DataFrame(columns=utils.data_columns)
processed_data_file = os.path.join(output_dir,"processed_data.csv")

# Create a dataframe for the Panoptic metadata import
processed_data_pano = pd.DataFrame(columns=utils.data_columns_pano)
processed_data_file_pano = os.path.join(output_dir,"import_pano.csv")


# Initialize the error counter
image_not_found = 0
image_with_annot = 0

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Extract bounding boxes from COCO JSON and overlay them on images. Also output thumbnails and metadata.")
parser.add_argument("data_dir", type=str, help="Path to the COCO folder")
parser.add_argument('ratio',  type=float, default=1.0,
                    help='Image dimension ratio compared to the original image')
parser.add_argument('-i', '--iiif', help='Download IIIF images of the annotated objects', action='store_true')

args = parser.parse_args()
ratio=args.ratio
images_dir = args.data_dir
coco_json_path = images_dir + "/_annotations.coco.json"

if args.iiif:
    download = True # download IIIF thumbnails?
else:
    download = False


# Clean the title string by removing spaces and special characters
def clean_title (title):
    
    # Remove everything after "_view" in the filename
    title = title.split('_view')[0]
    # Replace spaces with underscores
    cleaned_string = title.replace(" ", "_")
    # Remove special characters
    cleaned_string = ''.join(e for e in cleaned_string if e.isalnum() or e == '_')
    # Convert accented characters to their standard form
    cleaned_string = unicodedata.normalize('NFD', cleaned_string)
    cleaned_string = ''.join(c for c in cleaned_string if unicodedata.category(c) != 'Mn')
    # Replace double underscores with a single underscore
    cleaned_string = cleaned_string.replace("__", "_")
    cleaned_string = cleaned_string[:30]
    # Remove trailing underscore if present
    if cleaned_string.endswith("_"):
        cleaned_string = cleaned_string[:-1]
    return cleaned_string.lower()

# Function to find the ARK identifier in the data for a given image filename
def find_ark(image_filename):
    request = clean_title(image_filename)
    #print(request)
    gallica_ark = ark_dict.get(request, "Unknown")
    if gallica_ark == "Unknown":
        print(f"# ARK not found for title {image_filename} #")
        # Add the title to an error list
        with open(arks_errors_file, "a") as error_file:
            error_file.write(f"{image_filename}\n")
        return -1
    else:
        # Add the ARK to a set for tracking processed ARKs
        processed_arks.add(gallica_ark)
        return gallica_ark


# Extract bounding boxes from COCO JSON and overlay them on images
def extract_bounding_boxes(coco_json_path, images_dir, output_dir):
    global image_not_found
    global image_with_annot
    global processed_data
    global processed_data_pano
    global iiif_error 
    global iiif_ok

    # Load COCO dataset JSON file
    with open(coco_json_path, 'r') as f:
        coco_data = json.load(f) 

    # Map image IDs to file names
    image_id_to_file = {img['id']: img['file_name'] for img in coco_data['images']}
    
    # Process annotations
    for annotation in coco_data['annotations']:   
        image_id = annotation['image_id']
        bb_id = annotation['id']
        bbox = annotation['bbox']  # [x, y, width, height] / absolute coordinates
        # Get the label class
        category_id = annotation['category_id']
        category_name = next((cat['name'] for cat in coco_data['categories'] if cat['id'] == category_id), "Unknown")
           
        # Get image file name
        image_file = image_id_to_file.get(image_id)
        if not image_file:
            print("# Image ID {image_id} not found in COCO JSON, skipping... #")
            continue
        
        # Load image
        image_path = os.path.join(images_dir, image_file)
        if not os.path.exists(image_path):
            print(f"# Image file {image_path} not found, skipping... #")
            image_not_found += 1
            continue

        # Copy the image to the output folder at the first annotation
        out_image_filename = os.path.basename(image_path)
        # Remove everything after "_jpg" in the filename
        out_image_filename = out_image_filename.split('_jpg')[0] 
        print(f"... processing image: {out_image_filename} ...")
        copied_image_path = os.path.join(output_dir, out_image_filename + ".jpg")
        if not os.path.exists(copied_image_path):
            with open(image_path, 'rb') as src, open(copied_image_path, 'wb') as dst:
                dst.write(src.read())
                image_with_annot += 1

        if out_image_filename.startswith('bpt') or out_image_filename.startswith('btv'):
            gallica_ark = utils.get_ark_id(out_image_filename)
            if utils.debug:
                print(f"... found ARK in the database: {gallica_ark}")
            # Extract the vue number from the filename 
            vue = utils.get_vue(out_image_filename)     
        else:
            # find the related ark in the ARK database
            gallica_ark = find_ark(out_image_filename)
            if utils.debug:
                print(f"... ARK: {gallica_ark}")
            vue = utils.get_vue_trick(out_image_filename)

        ark_id = utils.get_ark_id(gallica_ark)

        if vue is None:
            print(f"# Warning! Cannot extract view number from filename {out_image_filename}, skipping... #")
            continue

        if utils.debug:
            print(f"... view number: {vue}")

        # The annotated image
        image = Image.open(copied_image_path)
        draw = ImageDraw.Draw(image)

        # The original image for thumbnail extraction
        origin_image = Image.open(image_path)

        # Draw bounding box
        x, y, width, height = bbox
        utils.draw_bbox(x, y, width, height, draw, category_name)

        # Save image with bounding box drawn
        image.save(copied_image_path)
        if utils.debug:
            print(f"... processed and saved in: {copied_image_path}")       

        # Get the image width and height
        image_dim = origin_image.size
        w = image_dim[0]
        h = image_dim[1]
        #print (f"... image dimensions: {image_dim[0]}x{image_dim[1]} pixels")
        # Generate the IIIF thumbnail URL
        gallica_iiif_url = utils.build_iiif_full_size(ark_id, vue, x, y, width, height, w,h, utils.iiif_size) 
        # Generate output filename for the bounding box thumbnail
        out_file = utils.format_bb_filename(out_image_filename, category_name, bb_id)
        # Add data to the DataFrame for processed data
        processed_data = utils.add_output_data(processed_data, gallica_ark, vue, image_file, out_file, category_name, gallica_iiif_url, 1.0)
        # Add data to the DataFrame for Panoptic import
        processed_data_pano = utils.add_output_pano_data(processed_data_pano, gallica_ark, vue, out_file, category_name, gallica_iiif_url)
        # export the data as a Supervision format
        utils.exportSV(sv_dir, image_file, category_id, category_name, x, y, w, h, vue, gallica_ark, model, ratio)

        # Extract thumbnail from the image file for the bounding box and save it    
        if gallica_ark:
            thumbnail = origin_image.crop((x, y, x + width, y + height))
            utils.export_thumbnail(thumbnail, thumbs_dir, gallica_ark, out_file, category_name)

        # Extract full-resolution thumbnail using Gallica IIIF Image API        
        if download and gallica_ark:
            iiif_out_file = utils.format_bb_filename(utils.format_base_filename(ark_id,vue), category_name, bb_id)
            iiif_error, iiif_ok = utils.export_thumbnail_iiif(gallica_iiif_url, iiif_thumbs_dir, gallica_ark, iiif_out_file)    
    # end of the loop

    print(f"\nNumber of annotations in the dataset: {len(coco_data['annotations'])}")
    print(f"Number of images in the dataset: {len(coco_data['images'])}")
    print(f"Number of images with annotations: {image_with_annot}")
    print(f"Number of files image not found: {image_not_found}")
    print(f"Number of processed ARKs: {len(processed_arks)}")

   

###            MAIN            ###

# Check if the COCO JSON file exists
if not os.path.exists(coco_json_path):
    print(f"# COCO JSON file {coco_json_path} not found! #")
    exit(1)

# Read the arks list as a CSV file and create a table with 2 columns: ark and title
if not os.path.exists(arks_data_file):
    print(f"# ARKS CSV file {arks_data_file} not found! #")
    exit(1)

# Load ARKs database (title/ark) 
with open(arks_data_file, 'r') as csvfile:
    reader = csv.reader(csvfile, delimiter="#")
    for row in reader:
        ark_dict[clean_title(row[0])] = row[1]  # Create a dictionary with ark as key and the first 20 characters of title as value

print(f"--------------------------------\nLength of ARKS dictionary: {len(ark_dict)}")
#print(ark_dict)

# Create output directories 
utils.mkdir(output_dir)
thumbs_dir = os.path.join(output_dir, thumbs_dir)
utils.mkdir(thumbs_dir)
iiif_thumbs_dir = os.path.join(output_dir, iiif_thumbs_dir)
utils.mkdir(iiif_thumbs_dir) 

extract_bounding_boxes(coco_json_path, images_dir, output_dir)

# Print the error list
if os.path.exists(arks_errors_file):
    print("\nTitles with no ARK identified:")
    with open(arks_errors_file, "r") as error_file:
        for line in error_file:
            print("  "+line.strip())

# Save the processed ARKs to a CSV file
with open(processed_arks_file, "a", newline="") as csvfile:
    writer = csv.writer(csvfile)
    for ark in processed_arks:
        writer.writerow([ark])
print(f"\nProcessed ARKs saved to: {processed_arks_file}")

# Save the processed data to a CSV files
processed_data.to_csv(processed_data_file, index=False)
processed_data_pano.to_csv(processed_data_file_pano, index=False, sep=";") 

# fix the Supervision JSON files
utils.fixSV(sv_dir)

print("----------------------------------------")
print(f"Processed data saved to: {processed_data_file}")
print(f"Import data for Panoptic saved to: {processed_data_file_pano}")
print(f"Supervision data saved to: {sv_dir}")
print("Thumbnails saved in: ", thumbs_dir)
if args.iiif:
    print(f"IIIF thumbnails downloaded: {iiif_ok} in {iiif_thumbs_dir}")
    if iiif_error != 0:
        print(f"## Warning! IIIF errors: {iiif_error} ##")
print("----------------------------------------")
