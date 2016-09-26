# Convert Bellingham building footprints into importable OSM files.
from lxml import etree
from lxml.etree import tostring
from shapely.geometry import asShape, Point, LineString
from sys import argv, exit, stderr
from glob import glob
from merge import merge
import re
from decimal import Decimal, getcontext
from multiprocessing import Pool
import json
from rtree import index
import ntpath
from fiona import collection

# Adjust precision for buffer operations
getcontext().prec = 16

# Converts given buildings into corresponding OSM XML files.
def convert(buildingsFile, osmOut):
    with collection(buildingsFile, "r") as buildingFile:
        buildings = []
        buildingShapes = []
        buildingIdx = index.Index()
        for building in buildingFile:
            buildings.append(building)
            shape = asShape(building['geometry'])
            buildingShapes.append(shape)
            buildingIdx.add(len(buildingShapes) - 1, shape.bounds)

        # Generates a new osm id.
        osmIds = dict(node = -1, way = -1, rel = -1)
        def newOsmId(type):
            osmIds[type] = osmIds[type] - 1
            return osmIds[type]

        # Appends new node or returns existing if exists.
        nodes = {}
        def appendNewNode(coords, osmXml):
            rlon = int(float(coords[0]*10**7))
            rlat = int(float(coords[1]*10**7))
            if (rlon, rlat) in nodes:
                return nodes[(rlon, rlat)]
            node = etree.Element('node', visible = 'true', id = str(newOsmId('node')))
            node.set('lon', str(Decimal(coords[0])*Decimal(1)))
            node.set('lat', str(Decimal(coords[1])*Decimal(1)))
            nodes[(rlon, rlat)] = node
            osmXml.append(node)
            return node

        def appendNewWay(coords, intersects, osmXml):
            way = etree.Element('way', visible='true', id=str(newOsmId('way')))
            firstNid = 0
            for i, coord in enumerate(coords):
                if i == 0: continue # the first and last coordinate are the same
                node = appendNewNode(coord, osmXml)
                if i == 1: firstNid = node.get('id')
                way.append(etree.Element('nd', ref=node.get('id')))

                # Check each way segment for intersecting nodes
                int_nodes = {}
                try:
                    line = LineString([coord, coords[i+1]])
                except IndexError:
                    line = LineString([coord, coords[1]])
                for idx, c in enumerate(intersects):
                    if line.buffer(0.000001).contains(Point(c[0], c[1])) and c not in coords:
                        t_node = appendNewNode(c, osmXml)
                        for n in way.iter('nd'):
                            if n.get('ref') == t_node.get('id'):
                                break
                        else:
                            int_nodes[t_node.get('id')] = Point(c).distance(Point(coord))
                for n in sorted(int_nodes, key=lambda key: int_nodes[key]): # add intersecting nodes in order
                    way.append(etree.Element('nd', ref=n))

            way.append(etree.Element('nd', ref=firstNid)) # close way
            osmXml.append(way)
            return way

        # Appends a building to a given OSM xml document.
        def appendBuilding(building, shape, osmXml):
            # Check for intersecting buildings
            intersects = []
            for i in buildingIdx.intersection(shape.bounds):
                try:
                    for c in buildingShapes[i].exterior.coords:
                        if Point(c[0], c[1]).buffer(0.000001).intersects(shape):
                            intersects.append(c)
                except AttributeError:
                    for c in buildingShapes[i][0].exterior.coords:
                        if Point(c[0], c[1]).buffer(0.000001).intersects(shape):
                            intersects.append(c)

            # Export building, create multipolygon if there are interior shapes.
            interiors = []
            try:
                way = appendNewWay(list(shape.exterior.coords), intersects, osmXml)
                for interior in shape.interiors:
                    interiors.append(appendNewWay(list(interior.coords), [], osmXml))
            except AttributeError:
                way = appendNewWay(list(shape[0].exterior.coords), intersects, osmXml)
                for interior in shape[0].interiors:
                    interiors.append(appendNewWay(list(interior.coords), [], osmXml))
            if len(interiors) > 0:
                relation = etree.Element('relation', visible='true', id=str(newOsmId('way')))
                relation.append(etree.Element('member', type='way', role='outer', ref=way.get('id')))
                for interior in interiors:
                    relation.append(etree.Element('member', type='way', role='inner', ref=interior.get('id')))
                relation.append(etree.Element('tag', k='type', v='multipolygon'))
                osmXml.append(relation)
                way = relation

            if building['properties']['BLDGTYPE'] == 'HOUSE':
                way.append(etree.Element('tag', k='building', v='house'))
            elif building['properties']['BLDGTYPE'] == 'DUPLX':
                way.append(etree.Element('tag', k='building', v='residential'))
            elif building['properties']['TYPE'] == 'PUBLIC':
                way.append(etree.Element('tag', k='building', v='public'))
            elif building['properties']['TYPE'] == 'TRAILER':
                way.append(etree.Element('tag', k='building', v='static_caravan'))
            elif building['properties']['TYPE'] == 'RESERVOIR':
                way.append(etree.Element('tag', k='building', v='yes'))
                way.append(etree.Element('tag', k='man_made', v='storage_tank'))
            else:
                way.append(etree.Element('tag', k='building', v='yes'))

            if building['properties']['NAME'] != None:
                name = str(building['properties']['NAME'])
                way.append(etree.Element('tag', k='name', v=name))
            if building['properties']['YRBUILT'] > 1800:
                yrbuilt = str(int(building['properties']['YRBUILT']))
                way.append(etree.Element('tag', k='start_date', v=yrbuilt))
            if float(building['properties']['NUM_FLOORS']) > 0:
                if float(building['properties']['NUM_FLOORS']).is_integer():
                  num_floors = str(int(building['properties']['NUM_FLOORS']))
                  way.append(etree.Element('tag', k='building:levels', v=num_floors))
                else:
                  num_floors = str(float(building['properties']['NUM_FLOORS']))
                  way.append(etree.Element('tag', k='building:levels', v=num_floors))

        # Export buildings.
        allAddresses = []
        osmXml = etree.Element('osm', version='0.6', generator='alan@stamen.com')
        for i in range(0, len(buildings)):

            appendBuilding(buildings[i], buildingShapes[i], osmXml)

        with open(osmOut, 'w') as outFile:
            outFile.writelines(tostring(osmXml, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
            print 'Exported ' + osmOut

def prep(fil3):
    matches = re.match('^(.*)\..*?$', ntpath.basename(fil3)).groups(0)
    convert(fil3, 'osm/%s.osm' % matches[0])

if __name__ == '__main__':
    # this is better for debugging
    #for fil3 in argv[1:]:
    #    prep(fil3)

    pool = Pool()
    pool.map(prep, argv[1:])
    pool.close()
    pool.join()
