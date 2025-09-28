"""
Perform inference on images folder with a Roboflow model
The Roboflow key must be published in ROBOFLOW_API_KEY in the Terminal

Input:
- images files organised in folders named with the ARK identifier
- ROBOFLOW_API_KEY environment variable must be set with your Roboflow API key
>export ROBOFLOW_API_KEY="..."

Parameters:
- folder with images or folder of folders
- Roboflow model name
- debug option (-d) for displaying the annotated images during inference
- save option (-s) for saving the annotated images

Usage:
>python roboflow_inference.py images model_name [-debug] [-save]
Example: python roboflow_inference.py bpt6k70557r "cheval-mandragore/3" -s

Output:
- JSON files in the JSON/ folder (one file per image)
- annotated images (if -save option is used) in the same folder as the input image(s)


"""

## Setup ##
# python -m venv roboflow
# source roboflow/bin/activate
# pip install inference
# export ROBOFLOW_API_KEY="p7LnHGfRLdA8xGQ5LF3r"
# python roboflow_inference.py ...


import inference
import supervision as sv # https://supervision.roboflow.com/
#import cv2
import argparse
import os.path
import sys
import pandas as pd
from PIL import Image, ImageDraw


import utils


# annotated files output folder
out = "JSON/"

# counters
infered = 0
objects = 0

# IIIF
iiif_error = 0
iiif_ok = 0
iiif_thumbs_dir = "IIIF_thumbs"

# name of the image files to process
data_files = []

# Create a DataFrame to store processed data
processed_data = pd.DataFrame(columns=utils.data_columns)
processed_data_file = os.path.join(out,"processed_data.csv")

# Create a dataframe for the Panoptic metadata import
processed_data_pano = pd.DataFrame(columns=utils.data_columns_pano)
processed_data_file_pano = os.path.join(out,"import_pano.csv")


# arguments
parser = argparse.ArgumentParser(description='Infer image(s) relatively to a Roboflow model')
parser.add_argument('image',  type=str,
                    help='one image file or folder of image files')
parser.add_argument('model',  type=str, help='Roboflow model name')
parser.add_argument('-d', '--debug', help='Display annotated images', action='store_true')
parser.add_argument('-s', '--save', help='Saved annotated images', action='store_true')
parser.add_argument('-i', '--iiif', help='Download IIIF images of the annotated objects', action='store_true')

args = parser.parse_args()


###      MAIN      ###
print("---------------------------------------")
utils.mkdir(out)
utils.mkdir(iiif_thumbs_dir) 

# images to be processed
image_files=args.image
if os.path.isfile(image_files):
    print("# You must provide a folder name! #")
    exit(0)
elif os.path.isdir(image_files):
    print("...processing folder: ",image_files)
    # reading files in the folder and subfolders
    dir_list = os.listdir(image_files)
    data_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(image_files) for f in filenames if f.endswith(('.jpg','.jpeg','.png'))]
else:
    sys.exit(f"# Error! Folder does not exist! {image_files}  #\n...ending")

#print(*data_files, sep="\n")
print(f"...{len(data_files)} file(s) found")
if len(data_files) == 0:
    exit(0)

# storing the annotated images in a subfolder 
output_path=out+image_files
utils.mkdir(output_path)

# Roboflow model_name 
model_name = args.model
print("...with Roboflow model: ",model_name)
# Loading 
model = inference.get_model(model_name)
print("-------  loaded  --------")
 
# Infering
for f in data_files:
    print("   Processing image: ",f)
    #image = cv2.imread(f)
    image = Image.open(f)
    (img_width, img_height) = utils.get_image_size(image)
    results = model.infer(image)[0]
    # charger les résultats dans l'API Supervision Detections
    detections = sv.Detections.from_inference(results)
    if len(detections) == 0:
        print("...no object found in the image, skipping...")
        continue
    else:
        print("...objects found: " + str(len(detections)))
        infered += 1
    # créer les annotateurs supervision
    bounding_box_annotator = sv.BoundingBoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    # annoter l'image avec les résultats de l'inférence
    annotated_image = bounding_box_annotator.annotate(
        scene=image, detections=detections)
    annotated_image = label_annotator.annotate(
        scene=annotated_image, detections=detections)
    # Display or save the annotated image
    if args.debug:
        sv.plot_image(annotated_image)
    if args.save:
        annotated_image_file = os.path.splitext(f)[0] + '_annotated.jpg'
        print("...writing annotated image in: ",annotated_image_file)
        #cv2.imwrite(annotated_image_file, annotated_image)
        #annotated_image_pil = Image.fromarray(annotated_image)
        annotated_image.save(annotated_image_file)
    
    # Export the annotations in Supervision format
    #     https://supervision.roboflow.com/latest/detection/tools/save_detections/#supervision.detection.tools.json_sink.JSONSink
    # We assume the folder name is the ARK identifier
    ark_id =  os.path.dirname(f).split("/")[-1]
    file_name = os.path.basename(f)
    file_name = os.path.splitext(file_name)[0]+'.json'
    json_file= os.path.join(output_path,ark_id,file_name)
    print("...writing JSON data in: ",json_file)
    json_sink = sv.JSONSink(json_file)
    json_sink.open()
    json_sink.append(detections, custom_data={'file':f, 'model':model_name})
    json_sink.write_and_close()

    # write the annotations data in a DataFrame
    bbox=detections.xyxy  #  [x1, y1, x2, y2] format
    category_ids=detections.class_id
    category_names=detections.data
    confidences=detections.confidence
    n_detections = len(detections)
    objects += n_detections
    print(f"...{n_detections} object(s) found in the image")
     # for each detection write a line in the DataFrame
    for i in range(0,n_detections):
        x1, y1, x2, y2 = bbox[i]
        category_id = category_ids[i]
        category=category_names["class_name"][i]
        confidence = confidences[i]
        if utils.debug:
            print(f"...object: {category} (id: {category_id}), confidence: {confidence}, x,y,w,h: {x1},{y1},{x2},{y2}")
        image_file = os.path.basename(f)
        vue = utils.get_vue(file_name)
        if vue == None:
            print("# Error: cannot extract the view number from the file name! #")
            continue
        # Build the IIIF url for the BB 
        ark = utils.get_ark(ark_id)
        gallica_iiif_url = utils.build_iiif_full_size(ark_id, vue, x1, y1, x2-x1, y2-y1, img_width, img_height, utils.iiif_size)
        out_file = utils.format_bb_filename(image_file.split('.')[0], category, i)
        # Extract full-resolution thumbnail using Gallica IIIF Image API        
        if args.iiif:    
            iiif_out_file = utils.format_bb_filename(utils.format_base_filename(ark_id,vue), category, i)
            print(iiif_out_file)
            iiif_error, iiif_ok = utils.export_thumbnail_iiif(gallica_iiif_url, iiif_thumbs_dir, ark_id, iiif_out_file)  
            if iiif_error != 0:
                # add a line in a log file
                utils.log_iiif_error(gallica_iiif_url)  

        # Add a line
        processed_data = utils.add_output_data(processed_data, ark, vue, image_file, out_file, category, gallica_iiif_url, confidence)
        # Add data to the DataFrame for Panoptic import
        processed_data_pano = utils.add_output_pano_data(processed_data_pano, ark, vue, out_file, category, gallica_iiif_url)


print("-------------------------")
# Save the processed data to CSV files
processed_data.to_csv(processed_data_file, index=False)
processed_data_pano.to_csv(processed_data_file_pano, index=False, sep=";") 

print(f"...{infered} image(s) contains an object (infered with model {model_name})")
print(f"...{objects} object(s) found in total")
print(f"...JSON data files saved in folder: {out}")
if args.iiif:
    print(f"...IIIF thumbnails downloaded: {iiif_ok} in {iiif_thumbs_dir}")
    if iiif_error != 0:
        print(f"# Warning! IIIF errors: {iiif_error} #")
print("-------------------------")
