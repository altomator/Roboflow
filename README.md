# Roboflow
Roboflow integration with Gallica content (and [Panoptic](https://panopticorg.github.io/))

## General context
- Extraction of typographical material from the early prints of the Réserve collections (BnF)
- Roboflow [project](https://app.roboflow.com/snooptypo)
- [Methodology](https://docs.google.com/presentation/d/1TdVedZGo4_sOiXMk-Do7hSQA7STYTNOU_ZxO1fHRrXw/edit?slide=id.g12b1dcf850d_0_49#slide=id.g12b1dcf850d_0_49)


## 1. Extracting images from Gallica

<b>Workflow</b>:
1. Obtaining images of documents (Gallica IIIF API, extraction script).
2. Ingesting a subset of these documents into Roboflow for annotation.
3. Processing the rest of the corpus.

`extract_iiif.py` must be feed with a file of ARK IDs and a image ratio for extraction (> 0.0 and <= 1.0):

```
>python extract_iiif.py arks.txt 0.5
```
Notes:
- Remember to restart the script to cover the case where the API failed the first time.
- Images are stored in a `IIIF_images folder`, in subfolders named by ARK IDs.

## 2. Training a model with Roboflow
See this [tutorial](https://docs.google.com/presentation/d/1-a0tdgQRa2K5ESwN5IhTn8VnGtDaxeseK37TgvtaiHY/edit?slide=id.g12b1dcf850d_0_49#slide=id.g12b1dcf850d_0_49)
and [methodology](https://docs.google.com/presentation/d/1TdVedZGo4_sOiXMk-Do7hSQA7STYTNOU_ZxO1fHRrXw/edit?slide=id.g12b1dcf850d_0_49#slide=id.g12b1dcf850d_0_49)


## 3. Obtain annotations made in Roboflow

This step allows to get access to the annotated data but also to reuse it under the same conditions as the data produced later by inference.

<b>Workflow</b>:
1. Export the annotated dataset from Roboflow in COCO format.
In [Roboflow](https://app.roboflow.com/snooptypo/snooptypo/models): 
- Go to the Versions tab. Click on the Download Dataset button
- Format: COCO, option: Download zip to computer
  
Notes:
- The dataset must have been generated <i>without</i> augmentation in Roboflow, otherwise the same images will appear multiple times. 
- The dataset includes JSON COCO annotations and the annotated images once uploaded to Roboflow.

2. Prepare the processing
- Unzip the .zip file into the processing folder. The annotated images are divided into three subfolders: test, train, and valid.
- In this particular project, we have to restore the link to Gallica ARKs based on document titles. This data is contained in the `arks_database.csv` file. Not necessary if the images are named after the ARK document.

3. Process the dataset
- The `export_boxes.py` script processes JSON COCO annotations in order to extract frames from annotated content (ornate letters, decorations, etc.), superimpose them on images, and generate thumbnails of the content. It also generates CSV data for further processing, as well as CSV data that will be needed to import useful metadata into [Panoptic](https://panopticorg.github.io/) (including the URL links to Gallica).

There are two types of thumbnails produced:
- extracted from Roboflow images,
- generated via the Gallica IIIF API (at the best available resolution): optional, must be requested when calling with -i

The script must be run on each test, train, and valid subfolder. Example with the test folder:
```
> python extract_boxes.py test 0.7 -i
```

After processing, the data produced is stored in the `output` folder:
- images of pages with annotated content boxes superimposed
- IIIF thumbnails of content (`IIIF_thumbs` folder), organised by ARK
- extracted thumbnails (thumbs folder), organised by ARK and content type (classes from the classification scheme)
- CSV data:
  - `processed_data.csv`: one line per annotation ARK,View,Image_filename,Category_name,Gallica,IIIF,Annotation_filename
 - `import_pano.csv`: one line per annotated image, for later import into Panoptic
path;Gallica[url];IIIF[url];Class[tag];ARK[text]
 - one JSON file per annotated image in Roboflow Supervision format, in the SV folder

![image](images/boxes.jpeg)
