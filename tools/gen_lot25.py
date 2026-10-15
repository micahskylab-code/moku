"""Generates plans/lot25.json from measurements taken off the Na Hiku Lot 25 floor plan.

All numbers below are pixel coordinates on the plan page rendered at 300 dpi
(`pdftoppm -r 300 -f 6 -l 6`). Scale: 23 px = 1 ft. That scale reproduces the
brochure's own areas: covered lanai + entry 506 vs 494 sq ft stated, ohana 347 vs
352 sq ft, main AC footprint 2,300 sq ft.
Origin (0,0) is the outside corner of the primary bedroom (px 175, 551).
Plan x runs toward the street (east on the drawing), plan y runs down the page.
"""
import json, sys
from pathlib import Path

S = 23.0
OX, OY = 175.0, 551.0
def X(px): return round((px - OX) / S, 2)
def Y(py): return round((py - OY) / S, 2)
def ft(px): return round(px / S, 2)

EXT, INT = 0.5, 0.375
walls = []

def hwall(ypx, x0, x1, t=INT, openings=(), **kw):
    """Horizontal wall on the drawing; openings are (type, from_px, to_px, extra)."""
    ops = [dict(type=o[0], at=round((o[1] - x0) / S, 2), width=round((o[2] - o[1]) / S, 2), **(o[3] if len(o) > 3 else {})) for o in openings]
    walls.append(dict(a=[X(x0), Y(ypx)], b=[X(x1), Y(ypx)], t=t, openings=ops, **kw))

def vwall(xpx, y0, y1, t=INT, openings=(), **kw):
    ops = [dict(type=o[0], at=round((o[1] - y0) / S, 2), width=round((o[2] - y0) / S - (o[1] - y0) / S, 2), **(o[3] if len(o) > 3 else {})) for o in openings]
    walls.append(dict(a=[X(xpx), Y(y0)], b=[X(xpx), Y(y1)], t=t, openings=ops, **kw))

# Window presets (heights in ft above finished floor)
BED = dict(sill=1.5, head=8.0, shutters=True)      # tall bedroom windows with wood shutters (back rendering)
LIV = dict(sill=1.5, head=8.0, shutters=True)
BATH = dict(sill=4.5, head=8.0)                     # privacy height over vanities / WCs
KIT = dict(sill=4.0, head=8.0)
SLIDE = dict(head=9.0)
DOOR = dict(head=8.0)

# ---------------- main house, north side (bedroom 3 wing + great room) ----------------
hwall(555, 588, 1986, EXT, [
    ('window', 635, 698, LIV), ('window', 966, 1029, LIV), ('window', 1330, 1377, KIT),
    ('window', 1457, 1505, BED), ('window', 1668, 1716, BED),
    ('window', 1817, 1864, BATH), ('window', 1908, 1954, BATH)])
# Lanai back wall (outdoor kitchen side) with two unglazed openings
hwall(627, 217, 596, EXT, [('opening', 241, 286, dict(sill=3.5, head=7.5)), ('opening', 496, 540, dict(sill=3.5, head=7.5))])
# Great room west wall: thick pocket wall, 18 ft of stacking glass that disappears into the pocket
vwall(604, 551, 1211, 1.39, [('pocket', 672, 1090, dict(head=9.5))])
# Great room east wall: kitchen side openings, hall, glass pivot front door with sidelights
vwall(1284, 551, 1211, EXT, [('cased', 614, 737, DOOR), ('cased', 847, 913, DOOR), ('pivot', 959, 1168, dict(head=9.0))])
hwall(683, 1284, 1427, INT, [('cased', 1325, 1382, DOOR)])          # pantry north
hwall(786, 1280, 1427, INT)                                         # pantry south / hall north
vwall(1421, 551, 919, INT, [('door', 852, 919, DOOR)])              # bedroom 3 west + door from hall
hwall(921, 1280, 1753, EXT, [('cased', 1330, 1377, DOOR), ('slider', 1497, 1682, SLIDE)])  # hall + bedroom 3 to courtyard
vwall(1749, 551, 919, INT, [('door', 700, 760, DOOR), ('window', 857, 919, BED)])
vwall(1802.5, 551, 688, INT)                                       # bath 3 closet / WC
vwall(1879, 551, 694, INT)                                         # bath 3 WC / shower
hwall(825.5, 1746, 1986, EXT, [('window', 1802, 1843, BATH), ('window', 1895, 1936, BATH)])
vwall(1980, 551, 831, EXT, [('slider', 622, 761, SLIDE)])           # glass to garden shower 3

# ---------------- south side: primary suite, gallery, bedroom 2 wing ----------------
hwall(1207, 169, 1000, EXT, [('window', 202, 250, BED), ('window', 471, 518, BED), ('door', 620, 701, DOOR)])
hwall(1207, 1280, 1753, EXT, [('cased', 1330, 1377, DOOR), ('slider', 1497, 1683, SLIDE)])
vwall(175, 1203, 1576, EXT, [('slider', 1250, 1530, SLIDE)])        # primary bedroom west, gable end
hwall(1572, 170, 914, EXT, [('window', 216, 264, BED), ('window', 456, 504, BED), ('window', 754, 802, BATH)])
vwall(543, 1288, 1576, INT, [('door', 1390, 1470, dict(head=8.0, double=True))])
hwall(1288, 539, 748, INT)
hwall(1386.5, 539, 694, INT, [('cased', 592, 641, DOOR)])
hwall(1474, 539, 694, INT, [('cased', 592, 642, DOOR)])
vwall(690, 1288, 1390, INT)
vwall(690, 1474, 1576, INT)
vwall(744, 1203, 1292, INT)
vwall(909, 1203, 1575, EXT, [('slider', 1305, 1493, SLIDE)])        # primary bath to garden shower 1
hwall(1291, 903, 1298, EXT, [('slider', 1064, 1250, SLIDE)])         # WH closet + gallery glass to side yard
vwall(996, 1207, 1291, INT, [('door', 1207, 1276, DOOR)])           # WH closet door

vwall(1290.5, 1291, 1576, EXT, [('window', 1359, 1405, BATH), ('door', 1436, 1483, DOOR)])
hwall(1572, 1287, 1986, EXT, [('window', 1333, 1381, BATH), ('window', 1459, 1507, BED), ('window', 1668, 1716, BED),
                              ('window', 1816, 1865, BATH), ('window', 1907, 1954, BATH)])
vwall(1423, 1207, 1576, INT, [('door', 1207, 1275, DOOR)])          # bedroom 2 west + door
hwall(1291, 1290, 1423, INT, [('cased', 1325, 1418, DOOR)])          # powder (pocket door)
hwall(1420, 1290, 1423, INT, [('cased', 1325, 1418, DOOR)])          # laundry (pocket door)
vwall(1749, 1207, 1576, INT, [('window', 1207, 1270, BED), ('door', 1369, 1430, DOOR)])
vwall(1802.5, 1439, 1575, INT)
vwall(1879, 1434, 1576, INT)
hwall(1302, 1745, 1986, EXT, [('window', 1802, 1843, BATH), ('window', 1895, 1937, BATH)])
vwall(1980, 1296, 1576, EXT, [('slider', 1367, 1505, SLIDE)])

# ---------------- garden shower enclosures: wood slat walls, open to the sky ----------------
SLAT = dict(height=7.0, finish='slat')
# The renderings close the street ends of both wings: the garden showers sit under the wing roofs
# behind a white gable wall — wood louvered shutters on the south wing, a wood carriage door on the north.
hwall(555, 1986, 2125, EXT)
vwall(2125, 555, 921, EXT, [('louvered', 690, 786, dict(sill=1.0, head=8.2, white=True))])
hwall(921, 1986, 2125, EXT, [('gate', 2000, 2060, dict(head=7.5))])
hwall(1207, 1986, 2125, EXT, [('gate', 2000, 2060, dict(head=7.5))])
vwall(2125, 1207, 1572, EXT, [('louvered', 1342, 1438, dict(sill=1.0, head=8.2, white=True))])
hwall(1572, 1986, 2125, EXT)
vwall(1045, 1291, 1572, 0.25, **SLAT)
hwall(1572, 914, 1045, 0.25, [('gate', 920, 980, dict(head=7.0))], **SLAT)

rooms = [
    dict(id='kitchen', name='Kitchen', polygon=[[X(1029), Y(555)], [X(1284), Y(555)], [X(1284), Y(870)], [X(1029), Y(870)]], floor='oak', label_only=True),
    dict(id='great', name='Great Room', polygon=[[X(604), Y(555)], [X(1284), Y(555)], [X(1284), Y(1207)], [X(1290), Y(1207)], [X(1290), Y(1291)], [X(996), Y(1291)], [X(996), Y(1207)], [X(604), Y(1207)]], floor='oak'),
    dict(id='pantry', name='Pantry', polygon=[[X(1284), Y(555)], [X(1421), Y(555)], [X(1421), Y(786)], [X(1284), Y(786)]], floor='oak', ceiling=9),
    dict(id='hall', name='Hall', polygon=[[X(1284), Y(786)], [X(1421), Y(786)], [X(1421), Y(921)], [X(1284), Y(921)]], floor='oak', ceiling=9),
    dict(id='bed3', name='Bedroom 3', polygon=[[X(1421), Y(555)], [X(1749), Y(555)], [X(1749), Y(921)], [X(1421), Y(921)]], floor='oak'),
    dict(id='bath3', name='Bathroom 3', polygon=[[X(1749), Y(555)], [X(1980), Y(555)], [X(1980), Y(825.5)], [X(1749), Y(825.5)]], floor='coral', ceiling=9),
    dict(id='entry', name='Entry', polygon=[[X(1284), Y(921)], [X(1465), Y(921)], [X(1465), Y(1207)], [X(1284), Y(1207)]], floor='coral', outdoor=True, covered=True),
    dict(id='lanai', name='Lanai', polygon=[[X(217), Y(627)], [X(604), Y(627)], [X(604), Y(1207)], [X(217), Y(1207)]], floor='coral', outdoor=True, covered=True),
    dict(id='primary', name='Primary Bedroom', polygon=[[X(175), Y(1207)], [X(744), Y(1207)], [X(744), Y(1288)], [X(543), Y(1288)], [X(543), Y(1572)], [X(175), Y(1572)]], floor='oak'),
    dict(id='pcloset1', name='Primary Closet', polygon=[[X(543), Y(1288)], [X(690), Y(1288)], [X(690), Y(1386.5)], [X(543), Y(1386.5)]], floor='oak', ceiling=9),
    dict(id='pcloset2', name='Primary Closet', polygon=[[X(543), Y(1474)], [X(690), Y(1474)], [X(690), Y(1572)], [X(543), Y(1572)]], floor='oak', ceiling=9),
    dict(id='ppass', name='Primary Bathroom', polygon=[[X(543), Y(1386.5)], [X(690), Y(1386.5)], [X(690), Y(1474)], [X(543), Y(1474)]], floor='coral', ceiling=9),
    dict(id='pbath', name='Primary Bathroom', polygon=[[X(690), Y(1288)], [X(744), Y(1288)], [X(744), Y(1207)], [X(909), Y(1207)], [X(909), Y(1572)], [X(690), Y(1572)]], floor='coral'),
    dict(id='wh', name='Storage', polygon=[[X(909), Y(1207)], [X(996), Y(1207)], [X(996), Y(1291)], [X(909), Y(1291)]], floor='oak', ceiling=9),
    dict(id='vest2', name='Hall', polygon=[[X(1290), Y(1207)], [X(1423), Y(1207)], [X(1423), Y(1291)], [X(1290), Y(1291)]], floor='oak', ceiling=9),
    dict(id='powder', name='Powder', polygon=[[X(1290), Y(1291)], [X(1423), Y(1291)], [X(1423), Y(1420)], [X(1290), Y(1420)]], floor='coral', ceiling=9),
    dict(id='laundry', name='Laundry', polygon=[[X(1290), Y(1420)], [X(1423), Y(1420)], [X(1423), Y(1572)], [X(1290), Y(1572)]], floor='coral', ceiling=9),
    dict(id='bed2', name='Bedroom 2', polygon=[[X(1423), Y(1207)], [X(1749), Y(1207)], [X(1749), Y(1572)], [X(1423), Y(1572)]], floor='oak'),
    dict(id='bath2', name='Bathroom 2', polygon=[[X(1749), Y(1302)], [X(1980), Y(1302)], [X(1980), Y(1572)], [X(1749), Y(1572)]], floor='coral', ceiling=9),
    dict(id='gs3', name='Garden Shower 3', polygon=[[X(1986), Y(555)], [X(2125), Y(555)], [X(2125), Y(921)], [X(1986), Y(921)]], floor='coral', outdoor=True, covered=True),
    dict(id='gs2', name='Garden Shower 2', polygon=[[X(1986), Y(1207)], [X(2125), Y(1207)], [X(2125), Y(1572)], [X(1986), Y(1572)]], floor='coral', outdoor=True, covered=True),
    dict(id='gs1', name='Garden Shower 1', polygon=[[X(909), Y(1291)], [X(1045), Y(1291)], [X(1045), Y(1572)], [X(909), Y(1572)]], floor='coral', outdoor=True),
    dict(id='court', name='Courtyard', polygon=[[X(1465), Y(921)], [X(1753), Y(921)], [X(1753), Y(1207)], [X(1465), Y(1207)]], floor='pavers', outdoor=True),
]

# Roofs. rect = wall lines [x0, y0, x1, y1]; ridge axis 'x' or 'y'.
# Pitch 6:12 to match the steep standing-seam roofs in both exterior renderings.
roofs = [
    # Every roof in both renderings is a standing-seam Dutch hip: hip ends with a small louvered gablet at the ridge.
    dict(id='main', type='hip', rect=[X(217), Y(551), X(1465), Y(1207)], pitch=0.55, overhang=2.5, gablet=5),
    dict(id='north', type='hip', rect=[X(1100), Y(551), X(2125), Y(921)], pitch=0.55, overhang=2.0, gablet=4),
    dict(id='south', type='hip', rect=[X(1290), Y(1207), X(2125), Y(1572)], pitch=0.55, overhang=2.0, gablet=4),
    dict(id='primary', type='hip', rect=[X(175), Y(1207), X(909), Y(1572)], pitch=0.55, overhang=2.0, gablet=4),
    dict(id='gallery', type='shed', rect=[X(900), Y(1207), X(1290), Y(1291)], pitch=0.25, overhang=1.5, low='y1'),
]

def item(type, x0, y0, x1, y1, rot=0, **kw):
    """Furniture by its bounding box on the drawing (px)."""
    return dict(type=type, x=X((x0 + x1) / 2), y=Y((y0 + y1) / 2), w=ft(x1 - x0) if rot % 180 == 0 else ft(y1 - y0),
                d=ft(y1 - y0) if rot % 180 == 0 else ft(x1 - x0), rot=rot, **kw)

furniture = [
    # great room (sectional and chairs as drawn)
    dict(type='rug', x=X(803), y=Y(1035), w=ft(316), d=ft(282), material='jute'),
    dict(type='sectional', x=X(804), y=Y(934), w=ft(212), d=ft(68), rot=0, leg=dict(w=ft(80), d=ft(130)), material='linen'),
    item('coffee-round', 806, 996, 888, 1078, material='oak'),
    item('side-table', 913, 913, 953, 961, lamp=True),
    dict(type='armchair', x=X(1030), y=Y(1012), w=2.9, d=2.8, rot=90, material='linen', frame='oak'),
    dict(type='armchair', x=X(1012), y=Y(1112), w=2.9, d=2.8, rot=60, material='linen', frame='oak'),
    dict(type='stonepanel', x=X(847), y=Y(1207) - 0.42, w=ft(258), h=10, rot=180),
    item('media', 718, 1160, 976, 1188, rot=180),
    dict(type='tv', x=X(847), y=Y(1207) - 0.68, w=6.0, rot=180, elevation=4.9),
    dict(type='art', x=X(800), y=Y(555) + 0.3, w=5.5, h=3.6, style='ocean', elevation=5.6),
    dict(type='basket', x=X(690), y=Y(1100), w=1.8, h=1.5),
    dict(type='basket', x=X(1270), y=Y(1150), w=2.0, h=1.6, plant=True),
    item('dining', 750, 675, 910, 760, chairs=8, ends=2, material='oak'),
    dict(type='pendant', x=X(830), y=Y(718), drop=10.0, style='rattan', size=2.6),
    dict(type='fan', x=X(806), y=Y(1035)),
    dict(type='plant', x=X(640), y=Y(600), w=2.2, h=7, style='fiddle'),
    # kitchen
    item('island', 1060, 678, 1150, 842, sink=True, material='oak', top='quartz'),
    dict(type='stool', x=X(1043), y=Y(705), rot=90), dict(type='stool', x=X(1043), y=Y(760), rot=90), dict(type='stool', x=X(1043), y=Y(815), rot=90),
    item('counter', 1050, 559, 1205, 610, rot=0, material='oak', top='quartz', uppers='shelves'),
    item('fridge', 1205, 559, 1280, 610),
    item('counter', 1225, 678, 1280, 842, rot=90, material='oak', top='quartz', range=True, uppers='hood'),
    dict(type='pendant', x=X(1105), y=Y(722), drop=7.2, style='globe', size=1.1),
    dict(type='pendant', x=X(1105), y=Y(798), drop=7.2, style='globe', size=1.1),
    item('counter', 1290, 690, 1415, 715, material='oak', top='quartz'),
    # bedroom 3
    item('bed', 1513, 556, 1668, 735, rot=0, material='linen'),
    item('nightstand', 1432, 560, 1505, 610, lamp=True), item('nightstand', 1670, 560, 1743, 610, lamp=True),
    item('bench', 1513, 735, 1668, 790, material='linen'),
    dict(type='art', x=X(1590), y=Y(921) - 0.3, w=4.5, h=3.2, style='kapa', rot=180, elevation=5.4),
    dict(type='basket', x=X(1730), y=Y(895), w=1.8, h=1.6, plant=True),
    dict(type='rug', x=X(1590), y=Y(700), w=10, d=8, material='jute'),
    dict(type='fan', x=X(1590), y=Y(735)),
    # bath 3
    item('vanity', 1752, 780, 1975, 822, rot=180, double=True),
    item('toilet', 1820, 556, 1860, 600),
    item('shower', 1883, 556, 1975, 694),
    item('wardrobe', 1752, 556, 1800, 688, rot=270),
    # bedroom 2
    item('bed', 1440, 1330, 1600, 1490, rot=270, material='linen'),
    item('nightstand', 1430, 1270, 1475, 1330, lamp=True, rot=270), item('nightstand', 1430, 1490, 1475, 1550, lamp=True, rot=270),
    dict(type='armchair', x=X(1700), y=Y(1240), w=2.8, d=2.8, rot=210, material='linen', frame='oak'),
    dict(type='rug', x=X(1560), y=Y(1410), w=8, d=10, material='jute'),
    dict(type='art', x=X(1749) - 0.3, y=Y(1300), w=3.0, h=4.0, style='ocean', rot=90, elevation=5.4),
    dict(type='fan', x=X(1586), y=Y(1390)),
    item('vanity', 1752, 1305, 1975, 1345, rot=0, double=True),
    item('toilet', 1820, 1525, 1860, 1568, rot=180),
    item('shower', 1883, 1434, 1975, 1568, rot=180),
    item('wardrobe', 1752, 1439, 1800, 1568, rot=270),
    # powder / laundry
    item('vanity', 1380, 1320, 1420, 1380, rot=90),
    item('toilet', 1355, 1340, 1395, 1385, rot=90),
    item('washer', 1360, 1520, 1418, 1570, rot=180),
    item('counter', 1295, 1520, 1360, 1570, rot=180, material='oak', top='quartz'),
    # primary suite
    item('bed', 280, 1400, 445, 1572, rot=180, material='linen'),
    item('nightstand', 210, 1515, 270, 1568, lamp=True, rot=180), item('nightstand', 455, 1515, 515, 1568, lamp=True, rot=180),
    dict(type='armchair', x=X(255), y=Y(1278), w=3.0, d=3.0, rot=135, material='linen', frame='oak'),
    item('side-table', 255, 1310, 315, 1365),
    item('media', 295, 1215, 425, 1245, rot=0),
    dict(type='tv', x=X(360), y=Y(1213), w=5.0, rot=0, elevation=4.4),
    dict(type='rug', x=X(360), y=Y(1460), w=11, d=9, material='jute'),
    dict(type='art', x=X(362), y=Y(1572) - 0.35, w=5.0, h=2.6, style='kapa', rot=180, elevation=6.9),
    dict(type='basket', x=X(520), y=Y(1540), w=1.8, h=1.6, plant=True),
    dict(type='fan', x=X(360), y=Y(1390)),
    item('tub', 833, 1300, 895, 1415),
    item('shower', 810, 1475, 905, 1568, rot=180),
    item('vanity', 695, 1295, 740, 1365, rot=270),
    item('vanity', 695, 1478, 740, 1548, rot=270),
    item('toilet', 845, 1215, 895, 1260),
    item('wardrobe', 548, 1292, 685, 1330), item('wardrobe', 548, 1530, 685, 1568, rot=180),
    # lanai (dining + living)
    item('grill', 300, 633, 480, 690, rot=0),
    item('outdoor-dining', 330, 803, 470, 890, chairs=8, ends=2),
    dict(type='outdoor-sofa', x=X(400), y=Y(1178), w=ft(160), d=ft(65), rot=180),
    item('side-table', 255, 1135, 303, 1183), item('side-table', 495, 1135, 543, 1183),
    item('coffee-rect', 350, 1100, 448, 1150, material='teak'),
    dict(type='outdoor-chair', x=X(290), y=Y(1050), w=ft(70), d=ft(70), rot=0),
    dict(type='outdoor-chair', x=X(500), y=Y(1050), w=ft(70), d=ft(70), rot=0),
    dict(type='fan', x=X(400), y=Y(790)), dict(type='fan', x=X(400), y=Y(1080)),
    dict(type='tv', x=X(400), y=Y(1211), w=5.5, rot=180, elevation=5.0, outdoor=True),
    # garden showers
    dict(type='outdoor-shower', x=X(2060), y=Y(640)), dict(type='outdoor-shower', x=X(2060), y=Y(1490)), dict(type='outdoor-shower', x=X(980), y=Y(1340)),
]

posts = [[X(217), Y(627)], [X(217), Y(1207)], [X(1465), Y(921)], [X(1465), Y(1207)]]
beams = [dict(a=[X(217), Y(627)], b=[X(217), Y(1207)]), dict(a=[X(1465), Y(921)], b=[X(1465), Y(1207)])]

plan = dict(
    name='Na Hiku · Aepo Nei Lot 25',
    note='Traced from the Na Hiku Buyer Preview Package, Lot 25 floor plan, at 23 px/ft (300 dpi). Renderings and plan are the developer\'s; this model is an interpretation.',
    units='ft', plate=10.0, grade=-0.6,
    start=dict(pos=[X(1600), Y(1063)], look=[X(1284), Y(1063)]),
    rooms=rooms, walls=walls, roofs=roofs, furniture=furniture, posts=posts, beams=beams,
)

# The guest ohana, traced from its own drawing. The front rendering shows it as the white shuttered
# pavilion left of the walk, short end to the street, so the drawing is turned 90 degrees:
# drawing x (bath end at 3137) runs toward the street, drawing y runs east.
XF, YL = 122.0, 32.3          # street face, and the face toward the walk
def oX(px): return round(XF - (3137.5 - px) / S, 2)
def oY(py): return round(YL + (py - 1389) / S, 2)
oh_walls = []
def oh(a, b, t, ops=()):
    (ax, ay), (bx, by) = a, b
    L = ((oX(bx) - oX(ax)) ** 2 + (oY(by) - oY(ay)) ** 2) ** 0.5
    def at(p): return round(abs(p) / S, 2)
    oh_walls.append(dict(a=[oX(ax), oY(ay)], b=[oX(bx), oY(by)], t=t, openings=[dict(type=o[0], at=round(o[1] / S, 2), width=round((o[2] - o[1]) / S, 2), **(o[3] if len(o) > 3 else {})) for o in ops]))
# openings given as offsets (px) from the wall's start point a
oh((2632, 1389), (3142, 1389), EXT, [('window', 30, 78, BED), ('window', 247, 295, BED), ('window', 437, 501, BATH)])
oh((2632, 1753.5), (3142, 1753.5), EXT, [('window', 26, 73, BED), ('window', 257, 305, BED), ('door', 398, 496, DOOR)])
oh((2636.5, 1386), (2636.5, 1757), EXT, [('slider', 45, 326, SLIDE)])
oh((3137.5, 1386), (3137.5, 1757), EXT, [('louvered', 40, 150, dict(sill=1.0, head=8.4, white=True)), ('louvered', 220, 330, dict(sill=1.0, head=8.4, white=True))])
oh((3005.5, 1386), (3005.5, 1757), INT, [('door', 159, 237, DOOR)])
oh((3005, 1700), (3137, 1700), INT)
walls += oh_walls
rooms += [
    dict(id='ohana', name='Guest Ohana', polygon=[[oX(2636), oY(1389)], [oX(3005), oY(1389)], [oX(3005), oY(1753)], [oX(2636), oY(1753)]], floor='oak'),
    dict(id='ohbath', name='Ohana Bath', polygon=[[oX(3005), oY(1389)], [oX(3137), oY(1389)], [oX(3137), oY(1700)], [oX(3005), oY(1700)]], floor='coral', ceiling=9),
    dict(id='ohlanai', name='Ohana Lanai', polygon=[[oX(2575), oY(1389)], [oX(2636), oY(1389)], [oX(2636), oY(1753)], [oX(2575), oY(1753)]], floor='coral', outdoor=True, covered=True),
]
roofs.append(dict(id='ohana', type='hip', rect=[oX(2575), oY(1389), oX(3137), oY(1753)], pitch=0.55, overhang=2.0, gablet=3.5))
posts += [[oX(2575), oY(1389)], [oX(2575), oY(1753)]]
beams.append(dict(a=[oX(2575), oY(1389)], b=[oX(2575), oY(1753)]))
furniture += [
    dict(type='bed', x=oX(2830), y=oY(1475), w=ft(170), d=ft(150), rot=90, material='linen'),
    dict(type='nightstand', x=oX(2700), y=oY(1412), w=2, d=1.6, lamp=True, rot=90), dict(type='nightstand', x=oX(2960), y=oY(1412), w=2, d=1.6, lamp=True, rot=90),
    dict(type='armchair', x=oX(2700), y=oY(1690), w=2.8, d=2.8, rot=45, material='linen', frame='oak'),
    dict(type='vanity', x=oX(3070), y=oY(1408), w=5, d=1.8, rot=0, double=False),
    dict(type='toilet', x=oX(3100), y=oY(1660), w=1.6, d=2.4, rot=270),
    dict(type='outdoor-chair', x=oX(2605), y=oY(1470), w=2.8, d=2.8, rot=90),
    dict(type='outdoor-chair', x=oX(2605), y=oY(1660), w=2.8, d=2.8, rot=90),
    dict(type='fan', x=oX(2820), y=oY(1570)),
]

# The garage: the cedar carriage-door pavilion right of the walk in the front rendering.
# Not on the Lot 25 drawing; sized to mirror the ohana.
GX0, GX1, GY0, GY1 = XF - 22.0, XF, 12.3 - 15.9, 12.3
walls += [
    dict(a=[GX1, GY0], b=[GX1, GY1], t=EXT, openings=[dict(type='carriage', at=3.45, width=9.0, head=8.0, sconces=True)]),
    dict(a=[GX0, GY0], b=[GX0, GY1], t=EXT, openings=[dict(type='window', at=6.0, width=4.0, sill=3.5, head=7.5)]),
    dict(a=[GX0, GY1], b=[GX1, GY1], t=EXT, openings=[dict(type='door', at=3.0, width=3.0, head=8.0)]),
    dict(a=[GX0, GY0], b=[GX1, GY0], t=EXT, openings=[dict(type='window', at=9.0, width=4.0, sill=3.5, head=7.5, shutters=True)]),
]
rooms.append(dict(id='garage', name='Garage', polygon=[[GX0, GY0], [GX1, GY0], [GX1, GY1], [GX0, GY1]], floor='concrete', ceiling=9.5))
roofs.append(dict(id='garage', type='hip', rect=[GX0, GY0, GX1, GY1], pitch=0.55, overhang=2.0, gablet=3.5))
furniture.append(dict(type='golfcart', x=(GX0 + GX1) / 2 + 2, y=(GY0 + GY1) / 2, rot=90))

out = Path(sys.argv[1] if len(sys.argv) > 1 else 'plans/lot25.json')
out.write_text(json.dumps(plan, indent=1))
print(f'{len(walls)} walls, {len(rooms)} rooms, {len(furniture)} pieces -> {out}')

# ---------------- site: pool, planting, street (from the two exterior renderings) ----------------
# Compass: plan +x (toward the street) is north, plan +y is east; the ocean lies south-southwest.
plan['compass'] = dict(north=[1, 0], east=[0, 1])
plan['site'] = dict(
    # One of the fourteen Na Hiku homesites: ~61 ft of frontage on the Na Hiku access road (north),
    # fairway 7 and the ocean beyond the back (south). The house is drawn square to its lot.
    lot=[-34.4, -8, 150, 53.5], oceanDir=[-0.91, 0.42], seaLevel=-230, bank=5.0,
    pool=dict(rect=[-31, 1, -17, 31], spa=[-23.5, 1, -17, 7.5], edge='x0', drop=3.0, deck=3),
    paths=[dict(rect=[X(1753), 19.8, 152, 24.8], material='stepping'), dict(rect=[GX1, GY0, 152, GY1], material='grassPavers')],
    walls=[dict(pts=[[-34.4, -8], [-34.4, -2]], height=1.8), dict(pts=[[-34.4, 34], [-34.4, 53.5]], height=1.8)],
    loungers=[[-28.5, -5, 90], [-24.5, -5, 90]],
    palms=[[-29.5, -5.5, 34], [-26, -1.2, 38], [-8, 47, 36], [-40, -4, 30], [95, -6, 30], [92, 51, 34], [30, -5.5, 36], [36, 51, 31],
           [72, -5, 27], [89, 13.5, 29], [90, 31.5, 31], [61, 17.0, 23], [65, 27.8, 25], [-42, 40, 32], [140, -5, 28], [140, 50, 31]],
    plumeria=[[102, 15.2, 0.9], [104, 29.4, 0.9], [-4, 50, 1.2], [44, 50], [139, 30.5, 0.8], [137, 14.5, 0.8]],
    beds=[dict(rect=[-34, 36, -20, 40], kind='bougainvillea'), dict(rect=[-34.2, -7, -31.5, 0.5], kind='bougainvillea'),
          dict(rect=[-42, -8, -35.5, 53], kind='bougainvillea', density=0.6),
          dict(rect=[96, 16.2, 121, 19.2], kind='ti'), dict(rect=[96, 25.4, 121, 28.4], kind='ti'),
          dict(rect=[123, 15.5, 150, 19.2], kind='gardenia'), dict(rect=[123, 25.4, 150, 29.5], kind='gardenia'),
          dict(rect=[86, -4, 99, 15.8], kind='monstera'), dict(rect=[86, 28.8, 97, 47], kind='monstera'),
          dict(rect=[57, 16.3, 67.5, 19.3], kind='groundcover'), dict(rect=[57, 25.3, 67.5, 28.2], kind='groundcover'),
          dict(rect=[-30, -8, 150, -6], kind='hedge'), dict(rect=[-30, 51.5, 150, 53.5], kind='hedge'),
          dict(rect=[-2, -3.5, 16, -1], kind='monstera'), dict(rect=[36, 46, 58, 49], kind='bougainvillea'),
          dict(rect=[8, 46, 30, 49], kind='gardenia'), dict(rect=[40, -3.5, 47, -1], kind='ti')],
)
plan['viewpoints'] = [
    dict(id='front', pos=[166, 22.3], eye=30, absolute=True, look=[66, 22.3], lookH=4, fov=50, sun=[58, 320], photo='ref/front.png'),
    dict(id='back', pos=[-54, -2], eye=5.2, absolute=True, look=[6, 18], lookH=6.0, fov=64, sun=[44, 215], photo='ref/back.png'),
    dict(id='great-room', pos=[X(1240), Y(1150)], look=[X(620), Y(800)], fov=72),
    dict(id='kitchen', pos=[X(760), Y(1000)], look=[X(1280), Y(620)], fov=72),
    dict(id='lanai', pos=[X(560), Y(1150)], look=[X(230), Y(700)], fov=72),
    dict(id='primary', pos=[X(520), Y(1260)], look=[X(250), Y(1520)], fov=72),
    dict(id='primary-bath', pos=[X(720), Y(1420)], look=[X(900), Y(1300)], fov=75),
    dict(id='bedroom-3', pos=[X(1720), Y(890)], look=[X(1500), Y(600)], fov=72),
    dict(id='courtyard', pos=[X(1900), Y(1063)], eye=5.4, look=[X(1284), Y(1063)], fov=65),
]
out.write_text(json.dumps(plan, indent=1))
print('with site + viewpoints ->', out)
