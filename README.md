Bellingham, Washington building and address import
==============================

This repository is based on the [DC buildings import](https://github.com/osmlab/dcbuildings/) and the later [LA buildings import](https://github.com/osmlab/labuildings/). There may be some references to DC or LA that have not been switched over yet.

**[Work in progress, do not use for import yet](https://github.com/almccon/bellingham-wa-buildings/issues)**

![Bellingham buildings screenshot](bellingham_buildings_screenshot.png?raw=true "Bellingham buildings screenshot from QGIS")

![Bellingham addresses screenshot](bellingham_addresses_screenshot.png?raw=true "Bellingham addresses screenshot from QGIS")

Generates an OSM file of buildings per Bellingham census block group, ready
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

    # Chunk building files by census tracts
    make chunks

    # Generate importable .osm files.
    # This will populate the osm/ directory with one .osm file per
    # census tract.
    make osm

    # Clean up all intermediary files:
    make clean

## Source data

- Buildings http://www.cob.org/data/gis/FGDB_Files/COB_struc_shps.zip

For future import (not in current phase):

- Address Points http://www.cob.org/data/gis/SHP_Files/COB_land_shps.zip
- LIDAR for building heights? See: http://pugetsoundlidar.ess.washington.edu/lidardata/restricted/nonpslc/bellingham2013/bellingham2013.html

## Features

- Transforms relevant attributes to OSM tags
- Exports one OSM XML building file per census block group
- Handles multipolygons
- Simplifies building shapes

## Attribute mapping

*Buildings*

Each building is a closed way tagged with:

    `building=yes`, or:
      - `building=house` if `BLDGTYPE=HOUSE`
      - `building=residential` if `BLDGTYPE=DUPLX`
      - `building=public` if `TYPE=PUBLIC`
      - `building=static_caravan` if `TYPE=TRAILER`
      - `man_made=storage_tank` if `TYPE=RESERVOIR`
    `name=NAME` # if available
    `building:levels=NUMFLOORS` # integer values, or 0.5, 1.5, 2.5, 3.5
    `start_date=YRBUILT` # if > 1800 (there is one erroneous value to filter out)

(All entities in CAPS are from `COB_struc_Buildings` shapefile.)


## Related

- [Bellingham import page](http://wiki.openstreetmap.org/wiki/Bellingham,_Washington/GIS_imports)
