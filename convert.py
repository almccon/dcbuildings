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
def convert(buildingsFile, extraAddressesFile, osmOut):
    with open(buildingsFile) as f:
        buildings = json.load(f)
    buildingShapes = []
    buildingIdx = index.Index()
    for building in buildings:
        shape = asShape(building['geometry'])
        buildingShapes.append(shape)
        buildingIdx.add(len(buildingShapes) - 1, shape.bounds)

    try:
        with open(extraAddressesFile) as f:
            extraAddresses = json.load(f)
    except:
        print "couldn't open", extraAddressesFile, "ignoring..."
        extraAddresses = []

    # Generates a new osm id.
    osmIds = dict(node = -1, way = -1, rel = -1)
    def newOsmId(type):
        osmIds[type] = osmIds[type] - 1
        return osmIds[type]

    # Converts an address
    def convertAddress(address):
        result = dict()
        if all (k in address for k in ('ADDR_NUM', 'STREET_NAM')):
            if address['ADDR_NUM']:
                result['addr:housenumber'] = str(address['ADDR_NUM'])
            if address['STREET_NAM']:
                streetname = address['STREET_NAM'].title()

                if streetname[0:2] == 'N ' and len(streetname) > 4: streetname = 'North ' + streetname[2:]
                if streetname[0:2] == 'S ' and len(streetname) > 4: streetname = 'South ' + streetname[2:]
                if streetname[0:2] == 'E ' and len(streetname) > 4: streetname = 'East ' + streetname[2:]
                if streetname[0:2] == 'W ' and len(streetname) > 4: streetname = 'West ' + streetname[2:]
                if streetname[0:3] == 'MT ': streetname = 'Mount ' + streetname[3:]

                if streetname[-3:] == ' Ct': streetname = streetname[:-3] + ' Court'
                if streetname[-3:] == ' Dr': streetname = streetname[:-3] + ' Drive'
                if streetname[-3:] == ' Ln': streetname = streetname[:-3] + ' Lane'
                if streetname[-3:] == ' Pl': streetname = streetname[:-3] + ' Place'
                if streetname[-3:] == ' Rd': streetname = streetname[:-3] + ' Road'
                if streetname[-3:] == ' St': streetname = streetname[:-3] + ' Street'
                if streetname[-4:] == ' Ave': streetname = streetname[:-4] + ' Avenue'
                if streetname[-4:] == ' Cir': streetname = streetname[:-4] + ' Circle'
                if streetname[-4:] == ' Hwy': streetname = streetname[:-4] + ' Highway'
                if streetname[-4:] == ' Ter': streetname = streetname[:-4] + ' Terrace'
                if streetname[-5:] == ' Blvd': streetname = streetname[:-5] + ' Boulevard'
                if streetname[-5:] == ' Pkwy': streetname = streetname[:-5] + ' Parkway'

                if streetname == 'Indian Street': streetname = 'Billy Frank Jr. Street'

                streetname = re.sub(r"(.*)(\d+)St\s+(.*)", r"\1\2st \3", streetname)
                streetname = re.sub(r"(.*)(\d+)Nd\s+(.*)", r"\1\2nd \3", streetname)
                streetname = re.sub(r"(.*)(\d+)Rd\s+(.*)", r"\1\2rd \3", streetname)
                streetname = re.sub(r"(.*)(\d+)Th\s+(.*)", r"\1\2th \3", streetname)

                result['addr:street'] = streetname
            if address['ZIP']:
                if address['PLUS4']:
                    result['addr:postcode'] = str(int(address['ZIP'])) + '-' + str(int(address['PLUS4']))
                else:
                    result['addr:postcode'] = str(int(address['ZIP']))
            if address['ADDR_SUITE']:
                result['addr:unit'] = str(address['ADDR_SUITE'])
        return result

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

    # Appends an address to a given node or way.
    def appendAddress(address, element):
        for k, v in convertAddress(address['properties']).iteritems():
            element.append(etree.Element('tag', k=k, v=v))

    # Appends a building to a given OSM xml document.
    def appendBuilding(building, shape, address, osmXml):
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
            name = str(building['properties']['NAME']).title()
            if name[-3:] == ' Es': name = name[:-3] + ' Elementary School'
            if name[-3:] == ' Ms': name = name[:-3] + ' Middle School'
            if name[-3:] == ' Hs': name = name[:-3] + ' High School'
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
        if address: appendAddress(address, way)

    # Export buildings & addresses. Only export address with building if there is exactly
    # one address per building. Export remaining addresses as individual nodes.
    allAddresses = []
    osmXml = etree.Element('osm', version='0.6', generator='alan@stamen.com')
    for i in range(0, len(buildings)):

        buildingAddresses = []
        for address in buildings[i]['properties']['addresses']:
            buildingAddresses.append(address)
        address = None
        if len(buildingAddresses) == 1:
            address = buildingAddresses[0]
        else:
            allAddresses.extend(buildingAddresses)

        appendBuilding(buildings[i], buildingShapes[i], address, osmXml)

    # Export any addresses that aren't the only address for a building.
    if (len(allAddresses) > 0):
        for address in allAddresses:
            node = appendNewNode(address['geometry']['coordinates'], osmXml)
            appendAddress(address, node)

    # Export any addresses that didn't originally intersect a building.
    if (len(extraAddresses) > 0):
        for address in extraAddresses:
            node = appendNewNode(address['geometry']['coordinates'], osmXml)
            appendAddress(address, node)

    with open(osmOut, 'w') as outFile:
        outFile.writelines(tostring(osmXml, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
        print 'Exported ' + osmOut

def prep(fil3):
    matches = re.match('^.*-(\d+)\.geojson$', fil3).groups(0)
    convert(fil3,
            'merged/extra-addresses-%s.geojson' % matches[0],
            'osm/buildings-addresses-%s.osm' % matches[0])

if __name__ == '__main__':
    # Run conversion.
    # Checks for an optional merged/extra-addresses-[block group geoid].geojson
    # for each merged/buildings-addresses-[block group geoid].geojson.
    # Optionally convert only one block group (passing the id as the argument).

    if (len(argv) == 2):
        convert('merged/buildings-addresses-%s.geojson' % argv[1],
                'merged/extra-addresses-%s.geojson' % argv[1],
                'osm/buildings-addresses-%s.osm' % argv[1])

    else:
        buildingFiles = glob("merged/buildings-addresses-*.geojson")

        pool = Pool()
        pool.map(prep, buildingFiles)
        pool.close()
        pool.join()
