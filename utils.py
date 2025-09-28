#

import os
import requests
from PIL import Image, ImageFont
import json
import pandas as pd

# global variables
debug = True
iiif_size = "max" #  we want the thumbnails at the maximum size
iiif_error = 0
iiif_ok = 0
image_not_found = 0

# IIIF
#gallica_base_url = "https://gallica.bnf.fr/iiif/ark:/12148/"
gallica_base_url = "https://openapi.bnf.fr/iiif/image/v3/ark:/12148/" # v3 version
iiif_log_file = "iiif_errors.log"

### Helper functions ###
def mkdir(name):
    if not os.path.isdir(name):
        print("...creating folder: ", name)
        os.mkdir(name)

# Remove "ark:/12148/" from ARK identifier
def get_ark_id(id):
    if id.startswith("ark:"):
        return id.replace("ark:/12148/", "")
    else:
        return id

def get_ark(ark):
    return ("ark:/12148/"+ark)

# Format the filename based on ARK, view number, and type."""
def format_filename(ark, vue, type):  
    if type(vue) is str:
        try:
            vue = int(vue)
        except ValueError:
            return None
    # Pad view number with leading zeros to 4 digits
    return f"{ark}-{vue:04d}.{type}"

# Format the filename based on ARK, view number, and type."""
def format_base_filename(ark, vue):  
    if type(vue) is str:
        try:
            vue = int(vue) 
        except ValueError:
            return None
    # Pad view number with leading zeros to 4 digits
    return f"{ark}-{vue:04d}"

# return the vue number as string
def get_vue(file_name):
    """Extract the view number from the file name."""
    # file name: bpt6k858005x-0001.jpg
    base_name = os.path.basename(file_name)
    vue_str = base_name.split('-')[-1].split('.')[0]
    try:
        return str(vue_str)
    except ValueError:
        return None

def get_vue_trick(file_name):
    """Extract the view number from the file name."""
    # file name: Ces_presentes_Heures_a_lusaige_de_view_216_num_NP.jpg
    base_name = os.path.basename(file_name)
    vue_str = base_name.split("view_")[1].split("_")[0]
    try:
        return int(vue_str)
    except ValueError:
        return None
    
# Generate output filename for the bounding box thumbnail
def format_bb_filename(out_image_filename, category_name, bb_id):

    return f"{out_image_filename}-{category_name}_{bb_id}.jpg"

### Image processing ###
def get_image_size(image):
    """Return the width and height of a PIL image"""
    return image.size  # (width, height)

def get_color_by_class(class_name):
    """Return a color based on the class name."""

    return   {
            "Vignette": "#0492C2",
            "Lettrine": "#ff69B4",
            "Ornement": "#8601AF"
        }.get(class_name, "red")  # Default

# Draw bounding box and label on a PIL image
def draw_bbox(x,y,width,height, draw, category_name):

    color=get_color_by_class(category_name)
    # Draw bounding box
    draw.rectangle([x, y, x + width, y + height], outline=color, width=4)
    # Draw label class
    text_position = (x + 2, y - 5)  # Position above the bounding box
    font = ImageFont.truetype("Arial Unicode.ttf", 30)
    draw.text(text_position, category_name, fill=color, font=font)
    return draw

# Export the thumbnail to the specified directory, considering its ark and category
# thumbnail is a PIL image
def export_thumbnail(thumbnail, thumbs_dir, ark, filename, category_name):

    ark = get_ark_id(ark)
    # Create a directory for the category if it doesn't exist
    category_dir = os.path.join(thumbs_dir, ark, category_name)
    os.makedirs(category_dir, exist_ok=True)
    # Save the thumbnail
    thumbnail_path = os.path.join(category_dir, filename)
    thumbnail.save(thumbnail_path)
    if debug:
        print(f"... thumbnail saved in: {thumbnail_path}")


### IIIF ###

def build_iiif_url(ark, vue, iiif_size):
    return f"{gallica_base_url}{ark}/f{vue}/full/{iiif_size}/0/default.jpg"                  

# Extract and save a IIIF image to the specified directory
# url is the IIIF image URL
def export_thumbnail_iiif(url, thumbs_dir, ark, filename):
    global iiif_error 
    global iiif_ok

    ark = get_ark_id(ark)
    # Create a directory for the category if it doesn't exist
    # category_dir = os.path.join(thumbs_dir, ark, category_name)
    # we don't use category
    category_dir = os.path.join(thumbs_dir, ark)
    os.makedirs(category_dir, exist_ok=True)
    thumbnail_path = os.path.join(category_dir, filename)
    if os.path.exists(thumbnail_path):
        print(f"... IIIF image already exists: {thumbnail_path}")
        return iiif_error, iiif_ok
    try:
        print(f"... downloading image with the IIIF API: {url} ...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        if response.status_code == 200:
            iiif_thumbnail = Image.open(response.raw)
            iiif_thumbnail.save(thumbnail_path)
            if debug:
                print(f"... IIIF image saved in: {thumbnail_path}")   
            iiif_ok += 1   
        else:
            print(f"# Failed to download IIIF image: {response.status_code} #")
            iiif_error += 1
    except Exception as e:
        print(f"# Failed to download IIIF image: {e} #")
        iiif_error += 1

    return iiif_error, iiif_ok

# Build the IIIF URL for a given bounding box
# iiif_size is the output size we want for the thumbnail
def build_iiif_full_size(gallica_ark, vue, x, y, width, height, w, h, iiif_size):
        
        # we express IIIF bbox as % compared to the full image size
        x_per = str(round(x/w*100, 2))
        y_per = str(round(y/h*100, 2))
        w_per = str(round(width/w*100, 2))
        h_per = str(round(height/h*100, 2))
        pct = f"pct:{x_per},{y_per},{w_per},{h_per}"
        return f"{gallica_base_url}{gallica_ark}/f{vue}/{pct}/{iiif_size}/0/default.jpg" 


def log_iiif_error(gallica_iiif_url):  
    with open(iiif_log_file, "a") as log_file:
        log_file.write(gallica_iiif_url + "\n")
        if debug:
            print(f"... logged IIIF error for URL: {gallica_iiif_url}")

### Supervision data ###

# Export the bounding box in supervision format in a path named after this scheme: sv_dir/ark/ark-vue.json  
def  exportSV(sv_dir, image_file, category_id, category_name, x, y, w, h, vue, ark, model, ratio):

    # Extract the last part of the ARK identifier
    ark = get_ark_id(ark)
    # fill the view number with leading zeros to 4 digits
    vue = str(vue).zfill(4)
    os.makedirs(os.path.join(sv_dir, ark), exist_ok=True)
    sv_file = os.path.join(sv_dir, ark, ark + "-" + vue + ".json")
    print(f"... exporting supervision data in: {sv_file}")
    # If the file does not exist, create it and write the header
    if not os.path.exists(sv_file): 
        with open(sv_file, "w") as f:
            f.write(f"[\n")
        with open(sv_file, "a") as f:
            json_record = {
                "x_min": x,
                "y_min": y,
                "x_max": x + w,
                "y_max": y + h,
                "class_id": category_id,
                "confidence": "1.0", 
                "tracker_id": "",
                "class_name": category_name,
                "file": image_file,
                "model": model,
                "_comment": f"Supervision format for ARK: {ark}, vue: {vue}; x,y,w,h in pixels, relatively to the listed file ({ratio} ratio with the original image)"
            }
            f.write(json.dumps(json_record) + ",")
    if debug:
        print(f"... supervision format saved in: {sv_file}")

# replace the last comma in the JSON supervision files with a closing bracket
def fixSV(sv_dir): 

    json_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(sv_dir) for f in filenames if os.path.splitext(f)[1] == '.json']
    for sv_path in json_files:
        os.system(f"sed 's/,$/]/' {sv_path} > tmp.json")
        os.system(f"mv tmp.json  {sv_path}")



### CSV data generation ###

data_columns = ["ARK", "Vue", "Image_filename", "Annotation_filename", "Category_name", "Gallica", "IIIF", "Confidence"]
data_columns_pano = ["path", "Gallica[url]", "IIIF[url]", "Classe[tag]", "ARK[text]"]

# Add data to the DataFrame
def add_output_data(processed_data, ark, vue, image_file, out_file, category_name, gallica_iiif_url, confidence):
    
    return pd.concat([processed_data, pd.DataFrame([{
            "ARK": ark,
            "Vue": vue,
            "Image_filename": image_file,
            "Annotation_filename": f"{get_ark_id(ark)}/{out_file}",
            "Category_name": category_name,
            "Gallica": f"https://gallica.bnf.fr/{ark}/f{vue}.item",
            "IIIF": gallica_iiif_url,
            "Confidence": confidence
        }])], ignore_index=True)


def add_output_pano_data(processed_data_pano, ark, vue, out_file, category_name, gallica_iiif_url):

    return pd.concat([processed_data_pano, pd.DataFrame([{
            "path": out_file,
            "Gallica[url]": f"https://gallica.bnf.fr/{ark}/f{vue}.item",
            "IIIF[url]": gallica_iiif_url,
            "Classe[tag]": category_name,
            "ARK[text]": ark
        }])], ignore_index=True)


### Gallica  APIs ###

# Get the number of images of a Gallica document thanks to its ARK and the Gallica Pagination API: https://gallica.bnf.fr/services/Pagination
# This API returns an XML flow with the <nbVueImages> element indicating the number of images
def get_number_of_images(ark):
    global image_not_found

    # Remove "ark:/12148/" from ARK identifier
    ark = get_ark_id(ark)
    pagination_url = f"https://gallica.bnf.fr/services/Pagination?ark={ark}&format=xml"
    try:
        response = requests.get(pagination_url)
        response.raise_for_status()
        if response.status_code == 200:
            # Parse the XML to find the <nbVueImages> element
            from xml.etree import ElementTree as ET
            root = ET.fromstring(response.content)
            nb_images_elem = root.find('.//nbVueImages')
            if nb_images_elem is not None and nb_images_elem.text.isdigit():
                return int(nb_images_elem.text)
            else:
                print(f"# Warning: <nbVueImages> element not found or invalid in the pagination response for ARK {ark} #")
                image_not_found += 1
                return 0
        else:
            print(f"# Failed to retrieve pagination info for ARK {ark}:\n{response.status_code}")
            image_not_found += 1
            return 0
    except Exception as e:
        print(f"# Failed to retrieve pagination info for ARK {ark}:\n{e}")
        image_not_found += 1
        return 0