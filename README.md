# Roboflow
Roboflow integration with Gallica content

## General context
- Extraction of typographical material from the early prints of the Réserve collections (BnF)
- Roboflow [project](https://app.roboflow.com/snooptypo)
- [Methodology](https://docs.google.com/presentation/d/1TdVedZGo4_sOiXMk-Do7hSQA7STYTNOU_ZxO1fHRrXw/edit?slide=id.g12b1dcf850d_0_49#slide=id.g12b1dcf850d_0_49)


## 1. Extracting images from Gallica

Workflow:
1. Obtaining images of documents (Gallica IIIF API, extraction script).
2. Ingesting a subset of these documents into Roboflow for annotation.
3. Processing the rest of the corpus.

`extract_iiif.py` must be feed with a file of ARK IDs and a image ratio for extraction:

```
>python extract_iiif.py arks.txt 0.7
```

## 2. Training a model with Roboflow
See this [tutorial](https://docs.google.com/presentation/d/1-a0tdgQRa2K5ESwN5IhTn8VnGtDaxeseK37TgvtaiHY/edit?slide=id.g12b1dcf850d_0_49#slide=id.g12b1dcf850d_0_49)
and [methodology](https://docs.google.com/presentation/d/1TdVedZGo4_sOiXMk-Do7hSQA7STYTNOU_ZxO1fHRrXw/edit?slide=id.g12b1dcf850d_0_49#slide=id.g12b1dcf850d_0_49)

## 3. Training a model with Roboflow






