all: BldgPly/buildings.shp BlockGroupPly/blockgroups.shp directories chunks merged osm

download: BldgPly/buildings.shp BlockGroupPly/blockgroups.geojson

clean:
	rm -f BldgPly.zip
	rm -f AddressPt.zip
	rm -f BlockGroupPly.zip

BldgPly.zip:
	curl -L "https://www.cob.org/data/gis/SHP_Files/COB_struc_shps.zip" -o BldgPly.zip

AddressPt.zip:
	curl -L "https://www.cob.org/data/gis/SHP_Files/COB_land_shps.zip" -o AddressPt.zip

BlockGroupPly.zip:
	curl -L "http://www2.census.gov/geo/tiger/TIGER2014/BG/tl_2014_53_bg.zip" -o BlockGroupPly.zip

BldgPly: BldgPly.zip
	rm -rf BldgPly
	unzip BldgPly.zip -d BldgPly

AddressPt: AddressPt.zip
	rm -rf AddressPt
	unzip AddressPt.zip -d AddressPt

# NOTE: this downloads block groups for all of Washington State. ogr2ogr selects & creates BlockGroupPolyshp with Whatcom county only.

BlockGroupPly: BlockGroupPly.zip
	rm -rf BlockGroupPly
	unzip BlockGroupPly.zip -d BlockGroupPly

BlockGroupPly/BlockGroupPly.shp: BlockGroupPly
	rm -f BlockGroupPly/BlockGroupPly.*
▸ ogr2ogr -where "COUNTYFP='073'" BlockGroupPly/BlockGroupPly.shp BlockGroupPly/tl_2014_53_bg.shp

-AddressPt/addresses.shp: AddressPt
	rm -f AddressPt/addresses.*
	ogr2ogr -t_srs EPSG:4326 -overwrite AddressPt/addresses.shp AddressPt/COB_Shps/COB_land_AddressPoints.shp

BldgPly/buildings.shp: BldgPly
	rm -f BldgPly/buildings.*
	ogr2ogr -simplify 0.2 -t_srs EPSG:4326 -overwrite BldgPly/buildings.shp BldgPly/COB_Shps/COB_struc_Buildings.shp

BlockGroupPly/blockgroups.shp: BlockGroupPly/BlockGroupPly.shp
	rm -f BlockGroupPly/blockgroups.*
	ogr2ogr -t_srs EPSG:4326 BlockGroupPly/blockgroups.shp BlockGroupPly/BlockGroupPly.shp

BlockGroupPly/blockgroups.geojson: BlockGroupPly
	rm -f BlockGroupPly/blockgroups.geojson
	rm -f BlockGroupPly/blockgroups-900913.geojson
	ogr2ogr -simplify 3 -t_srs EPSG:900913 -f "GeoJSON" BlockGroupPly/blockgroups-900913.geojson BlockGroupPly/BlockGroupPly.shp
#	python tasks.py BlockGroupPly/blockgroups-900913.geojson > BlockGroupPly/blockgroups.geojson

chunks: directories BldgPly/buildings.shp
	python chunk.py AddressPt/addresses.shp BlockGroupPly/blockgroups.shp chunks/addresses-%s.shp GEOID
	python chunk.py BldgPly/buildings.shp BlockGroupPly/blockgroups.shp chunks/buildings-%s.shp GEOID

merged: directories
	python merge.py

osm: merged
	python convert.py merged/*

directories:
	mkdir -p chunks
	mkdir -p merged
	mkdir -p osm
