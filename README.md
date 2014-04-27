Bellingham, Washington building and address import
==============================

This repository is based on the [DC buildings import](https://github.com/osmlab/dcbuildings/). There will be many references to DC that have not been switched over yet.

**[Work in progress, do not use for import yet](https://github.com/almccon/bellingham-wa-buildings/issues)**

Generates an OSM file of buildings with addresses per Bellingham census tract, ready
to be used in JOSM for a manual review and upload to OpenStreetMap.

No formal import proposal has been made yet. We will follow the [import guidelines](http://wiki.openstreetmap.org/wiki/Import/Guidelines) before any data is imported.

## Prerequisites 

    libxml2 
    libxslt
    spatialindex
    GDAL  
   

## Mac OSX specific install 
  
    # install brew http://brew.sh

    brew install libxml2 
    brew install libxslt 
    brew install spatialindex 
    brew install gdal 

## Ubuntu install
    sudo apt-get install libxml2
    sudo apt-get install libxml2-dev libxslt1-dev python-dev
    sudo apt-get install libspatialindex-dev
    sudo apt-get install gdal-bin

## Set up Python virtualenv and get dependencies
    # may need to easy_install pip and pip install virtualenv 
    virtualenv ~/venvs/bellingham-wa-buildings
    source ~/venvs/bellingham-wa-buildings/bin/activate 
    pip install -r requirements.txt


## Usage

Run all stages:

    # Download all files and process them into a building
    # and an address .osm file per census tract.
    make

You can run stages separately, like so:

    # Download and expand all files, reproject
    make download

    # Chunk address and building files by census tracts
    make chunks

    # Generate importable .osm files.
    # This will populate the osm/ directory with one .osm file per
    # census tract.
    make osm

    # Clean up all intermediary files:
    make clean

    # For testing it's useful to convert just a single census tract.
    # For instance, convert census tract 000100:
    python convert.py 000100

## Source data

- Address Points http://www.cob.org/data/gis/SHP_Files/COB_land_shps.zip
- Buildings http://www.cob.org/data/gis/FGDB_Files/COB_struc_shps.zip

## Features

- Conflates buildings and addresses
- Cleans address names
- Exports one OSM XML building file per census tract
- Exports OSM XML address files for addresses that pertain to buildings with
  more than one address
- Handles multipolygons
- Simplifies building shapes

## Attribute mapping

*Buildings*

Each building is a closed way tagged with:

    building="yes"
    addr:housenumber="ADDRNUM ADDRNUMSUF" # If available
    addr:streetname="STNAME STREET_TYP QUADRANT" # If available
    addr:postcode="ZIPCODE" # If available

(All entities in CAPS are from DCGIS address file.)

*Addresses*

Each address is a node tagged with:

    addr:housenumber="ADDRNUM ADDRNUMSUF"
    addr:streetname="STNAME STREET_TYP QUADRANT"
    addr:postcode=ZIPCODE

(All entities in CAPS from DCGIS address file.)

## Related

- [Bellingham import page](http://wiki.openstreetmap.org/wiki/Bellingham,_Washington/GIS_imports)
