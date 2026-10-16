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
DH = dict(sill=2.5, head=8.0, dh=True)             # double-hung 1-over-1, bronze sashes (back rendering, TV wall)
DOOR = dict(head=8.0)
HALLWIN = dict(sill=2.0, head=8.0)                 # p6 draws windows (not openings) from the hall and vestibule onto the entry; heights assumed (I-2)

# ---------------- main house, north side (bedroom 3 wing + great room) ----------------
hwall(555, 588, 1986, EXT, [
    ('window', 635, 698, LIV), ('window', 966, 1029, LIV), ('window', 1330, 1377, KIT),
    ('window', 1457, 1505, BED), ('window', 1668, 1716, BED),
    ('window', 1817, 1864, BATH), ('window', 1908, 1954, BATH)])
# Lanai back wall (outdoor kitchen side) with two unglazed openings
# r4 (critique-preview3-back #8): p5 shows both openings closed by cedar louvered shutter panels; sizes unchanged
hwall(627, 217, 596, EXT, [('louvered', 241, 286, dict(sill=3.5, head=7.5)), ('louvered', 496, 540, dict(sill=3.5, head=7.5))])
# Great room west wall: thick pocket wall, 18 ft of stacking glass that disappears into the pocket
vwall(604, 551, 1211, 1.39, [('pocket', 672, 1090, dict(head=9.5, panels=6, deployed=4, rows=3))])
# Great room east wall: kitchen side openings, hall, glass pivot front door with sidelights
# r5 (critique-preview4-front #5): p4's 1 ft cedar header band over the pivot door and sidelights (register I-2b)
vwall(1284, 551, 1211, EXT, [('cased', 614, 737, DOOR), ('cased', 847, 913, DOOR), ('pivot', 959, 1168, dict(head=9.0, header=1.0))])
hwall(683, 1284, 1427, INT, [('cased', 1325, 1382, DOOR)])          # pantry north
hwall(786, 1280, 1427, INT)                                         # pantry south / hall north
vwall(1421, 551, 919, INT, [('door', 852, 919, DOOR)])              # bedroom 3 west + door from hall
hwall(921, 1280, 1753, EXT, [('window', 1330, 1377, HALLWIN), ('slider', 1497, 1682, SLIDE)])  # hall window onto the entry + bedroom 3 to courtyard
vwall(1749, 551, 919, INT, [('door', 700, 760, DOOR), ('window', 857, 919, BED)])
vwall(1802.5, 551, 688, INT)                                       # bath 3 closet / WC
vwall(1879, 551, 694, INT)                                         # bath 3 WC / shower
hwall(825.5, 1746, 1986, EXT, [('window', 1802, 1843, BATH), ('window', 1895, 1936, BATH)])
vwall(1980, 551, 831, EXT, [('slider', 622, 761, SLIDE)])           # glass to garden shower 3

# ---------------- south side: primary suite, gallery, bedroom 2 wing ----------------
# lanai TV wall (back rendering): double-hung windows either side of the TV, vertical board finish, no shutters
# r4 (critique-preview3-back #8): the right-hand window moved 3.2 ft clear of the lanai corner post (it sat behind it),
# so the TV hangs between two double-hungs as in p5; same size
hwall(1207, 169, 1000, EXT, [('window', 275, 323, DH), ('window', 471, 518, DH), ('door', 620, 701, DOOR)], outside='batten')
hwall(1207, 1280, 1753, EXT, [('window', 1330, 1377, HALLWIN), ('slider', 1497, 1683, SLIDE)])
# primary bedroom west, gable end (back rendering): a centred 10 ft 4-panel slider, 3 lites high, cylinder sconces
vwall(175, 1203, 1576, EXT, [('slider', 1275, 1505, dict(head=8.0, panels=4, rows=3, sconces=True))])
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
    dict(id='wh', name='Storage', polygon=[[X(909), Y(1207)], [X(996), Y(1207)], [X(996), Y(1291)], [X(909), Y(1291)]], floor='oak', ceiling=7.75),
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
# Pitch 6.6:12 to match the steep standing-seam roofs in both exterior renderings.
# Dutch gables (front rendering: garage, ohana and both flanking wings; back rendering: the primary wing):
# `dutch` = the hip skirt's horizontal run from the eave edge (ft) before the vertical louvered gable wall,
# which then spans ~65% of the eave and rises ~4.5 ft. The main pavilion is a plain hip (f34).
# `holes`: open-air slatted roof wells over the garden showers (front rendering, top left);
# `downspouts`: [x, y, wall axis] at the drained corners.
roofs = [
    # r4 (critique-preview3-front #2, client: 'give it your best guess'): p4 shows the great-room pavilion's street
    # face as a broad trapezoid with its ridge ACROSS the view over the glazed entry. Inferred from that rendering
    # (no roof plan, register I-3): a cross hip over the great room + entry, ridge along plan y at ~18.6 ft (the main
    # hip's ridge, 17.8 ft, dies into its back plane), street / back planes at the house pitch, the hip ends at
    # 11.4:12 so the ridge runs ~10 ft across as in p4. Listed first so it owns the street plane it shares with the
    # main hip. The lanai end and the back view keep the plain main hip.
    dict(id='great', type='hip', ridge='y', rect=[X(744), Y(551), X(1465), Y(1207)], pitch=0.55, endPitch=0.95, overhang=2.5),
    dict(id='main', type='hip', rect=[X(217), Y(551), X(1465), Y(1207)], pitch=0.55, overhang=2.5),
    # its eaves kick out into a 3:12 skirt (back rendering, b30): a shallower hip whose planes cross the main's
    # 6" outside the wall lines, so it only shows as the lower-pitch band over the overhang (the union keeps
    # the higher surface); interior vaults and wall heads are unchanged
    dict(id='main-skirt', type='hip', rect=[X(217), Y(551), X(1465), Y(1207)], pitch=0.25, overhang=3.0, plate=10.0 - 0.3 * 0.5),
    dict(id='north', type='hip', rect=[X(1100), Y(551), X(2125), Y(921)], pitch=0.55, overhang=2.0, dutch=3.5, dutchEnds='hi',
         holes=[[75.8, 9.2, 80.3, 15.0]], downspouts=[[X(2125), Y(921), 'y']]),
    dict(id='south', type='hip', rect=[X(1290), Y(1207), X(2125), Y(1572)], pitch=0.55, overhang=2.0, dutch=3.5, dutchEnds='hi',
         holes=[[75.8, 29.6, 80.3, 35.4]], downspouts=[[X(2125), Y(1207), 'y']]),
    dict(id='primary', type='hip', rect=[X(175), Y(1207), X(909), Y(1572)], pitch=0.55, overhang=2.0, dutch=3.5, dutchEnds='lo',
         downspouts=[[X(175), Y(1572), 'y']]),
    # the gallery link: a low-slope (1.2:12) metal roof tucked under the main hip's eave and the wings, so no
    # flat wedge shows in the valley (f33); the storage room under it gets a lower flat ceiling
    dict(id='gallery', type='shed', rect=[X(900), Y(1207), X(1290), Y(1291)], pitch=0.1, overhang=1.0, low='y1', plate=7.95),
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
    # p5 lanai TV on the batten wall above the sofa; its back on the wall's lanai face (Y(1207) - 0.25) - at
    # Y(1211) it sat inside the 6" wall and never rendered (critique r2 back #13)
    dict(type='tv', x=X(400), y=Y(1207) - 0.36, w=5.5, rot=180, elevation=5.0, outdoor=True),
    # garden showers
    dict(type='outdoor-shower', x=X(2060), y=Y(640)), dict(type='outdoor-shower', x=X(2060), y=Y(1490)), dict(type='outdoor-shower', x=X(980), y=Y(1340)),
]

# lanai: 10x10 rough-sawn cedar posts, 10x14 header; entry: 8" cedar posts under an 18" cedar-clad header box
posts = [[X(217), Y(627), 0.833], [X(217), Y(1207), 0.833], [X(1465), Y(921), 0.667], [X(1465), Y(1207), 0.667]]
# r4 (critique-preview3-back #8): the lanai header dropped to a 7'-11" soffit as in p5 (at the plate it hid behind the
# gutter from any eye near deck height), a painted frieze above it up to the soffit
# r5 (critique-preview4-back #9): the header stands 2" proud of the frieze (p5's shadow line under the soffit)
beams = [dict(a=[X(217), Y(627)], b=[X(217), Y(1207)], w=0.833, h=1.167, ext=1.0, top=9.1, frieze=True, proud=0.17),
         # r5 (critique-preview4-front #5): p4's cedar header over the entry. At the plate it sat behind the great
         # roof's gutter from the street eye (sight lines pass under the gutter at ~7.9 ft here, and the pivot door's
         # 9 ft head is hidden too): dropped to a 7'-3" underside with a painted frieze above, like the lanai (I-2b)
         dict(a=[X(1465), Y(921)], b=[X(1465), Y(1207)], w=0.667, h=1.5, ext=0.0, material='cedar', plates=False, top=8.75, frieze=-1)]

plan = dict(
    name='Nā Hiku spec home · Lot 25 design · Kukuiʻula',
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
# street face (front rendering): two narrow 2'-3" x 6'-6" white louvered shutter assemblies in lap siding
oh((3137.5, 1386), (3137.5, 1757), EXT, [('louvered', 114, 166, dict(sill=1.2, head=7.7, white=True)), ('louvered', 259, 311, dict(sill=1.2, head=7.7, white=True))])
oh((3005.5, 1386), (3005.5, 1757), INT, [('door', 159, 237, DOOR)])
oh((3005, 1700), (3137, 1700), INT)
walls += oh_walls
rooms += [
    dict(id='ohana', name='Guest Ohana', polygon=[[oX(2636), oY(1389)], [oX(3005), oY(1389)], [oX(3005), oY(1753)], [oX(2636), oY(1753)]], floor='oak'),
    dict(id='ohbath', name='Ohana Bath', polygon=[[oX(3005), oY(1389)], [oX(3137), oY(1389)], [oX(3137), oY(1700)], [oX(3005), oY(1700)]], floor='coral', ceiling=9),
    dict(id='ohlanai', name='Ohana Lanai', polygon=[[oX(2491), oY(1389)], [oX(2636), oY(1389)], [oX(2636), oY(1753)], [oX(2491), oY(1753)]], floor='coral', outdoor=True, covered=True),
]
roofs.append(dict(id='ohana', type='hip', rect=[oX(2491), oY(1389), oX(3137), oY(1753)], pitch=0.55, overhang=2.0, dutch=3.5, dutchEnds='hi',
                  downspouts=[[XF, YL, 'y']]))
posts += [[oX(2491), oY(1389)], [oX(2491), oY(1753)]]   # p6 lānai corner posts (the lānai is ~6.3 ft deep)
beams.append(dict(a=[oX(2491), oY(1389)], b=[oX(2491), oY(1753)]))
furniture += [
    dict(type='bed', x=oX(2830), y=oY(1475), w=ft(170), d=ft(150), rot=90, material='linen'),
    dict(type='nightstand', x=oX(2700), y=oY(1412), w=2, d=1.6, lamp=True, rot=90), dict(type='nightstand', x=oX(2960), y=oY(1412), w=2, d=1.6, lamp=True, rot=90),
    dict(type='armchair', x=oX(2700), y=oY(1690), w=2.8, d=2.8, rot=45, material='linen', frame='oak'),
    dict(type='vanity', x=oX(3070), y=oY(1408), w=5, d=1.8, rot=0, double=False),
    dict(type='toilet', x=oX(3100), y=oY(1660), w=1.6, d=2.4, rot=270),
    dict(type='outdoor-chair', x=oX(2540), y=oY(1470), w=2.8, d=2.8, rot=90),
    dict(type='outdoor-chair', x=oX(2540), y=oY(1660), w=2.8, d=2.8, rot=90),
    dict(type='fan', x=oX(2820), y=oY(1570)),
]

# The garage: the cedar carriage-door pavilion right of the walk in the front rendering.
# Not on the Lot 25 drawing; sized to mirror the ohana.
GX0, GX1, GY0, GY1 = XF - 22.0, XF, 12.3 - 15.9, 12.3
walls += [
    dict(a=[GX1, GY0], b=[GX1, GY1], t=EXT, openings=[dict(type='carriage', at=3.45, width=9.0, head=8.0, sconces=True)]),
    dict(a=[GX0, GY0], b=[GX0, GY1], t=EXT, openings=[dict(type='window', at=6.0, width=4.0, sill=3.5, head=7.5)]),
    dict(a=[GX0, GY1], b=[GX1, GY1], t=EXT, openings=[dict(type='door', at=3.0, width=3.0, head=8.0),
                                                     dict(type='window', at=19.4, width=1.5, sill=2.5, head=7.5)]),   # narrow window by the front corner
    dict(a=[GX0, GY0], b=[GX1, GY0], t=EXT, openings=[dict(type='window', at=9.0, width=4.0, sill=3.5, head=7.5, shutters=True)]),
]
rooms.append(dict(id='garage', name='Garage', polygon=[[GX0, GY0], [GX1, GY0], [GX1, GY1], [GX0, GY1]], floor='concrete', ceiling=9.5))
roofs.append(dict(id='garage', type='hip', rect=[GX0, GY0, GX1, GY1], pitch=0.55, overhang=2.0, dutch=3.5, dutchEnds='hi',
                  downspouts=[[GX1, GY1, 'y'], [GX1, GY0, 'y']]))
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
    # pool: rect = weir face (x0) and tile faces; spa = its water (tile faces), set into the back wall with
    # pool water wrapping its seaward side and the steps either side (back rendering)
    pool=dict(rect=[-31, 1, -17, 31], spa=[-23.5, 10.5, -17, 17], edge='x0', drop=3.0, deck=3),
    # r5 (critique-preview4-front #8, back #6; register I-13b): the entry walk is single 2 x 4 ft cut-stone slabs
    # [along, across, joint ft] centred on the walk with 5 in grass joints (p4); the grass-paver drive gets a tan stone
    # border [far side, walk side ft] (15 in on the walk side, p4); a paved deck at the pool's left end carries the
    # two chaises (p5), up to the bougainvillea bed; its pool-side and inner edges on the 2 ft paver grid
    paths=[dict(rect=[X(1753), 19.8, 152, 24.8], material='stepping', slabs=[2.0, 4.0, 0.42]),
           dict(rect=[GX1, GY0, 152, GY1], material='grassPavers', border=[1.0, 1.25]),
           dict(rect=[-31.5, -7, -24, 0], material='coral')],
    # coral retaining wall on the back lot line, returning down the bank at both side lines
    # (a wall's top follows the ground at its first point, so each run starts on the lot line)
    # return walls step down the bank in 1.6 ft runs (each run's top follows the ground at its start), so no tall pier stands proud
    walls=[dict(pts=[[-34.4, -8.6], [-34.4, 1]], height=0.35), dict(pts=[[-34.4, -8.6], [-36, -8.6], [-37.6, -8.6], [-39.2, -8.6], [-41, -8.6]], height=0.35),
           # r5: the long run right of the pier carries a raised planter (p5: bougainvillea spilling over the right wall,
           # critique-preview4-back #10): its face carried 0.9 ft up, 1.4 ft of soil between 4" curbs (~0.63 m overall)
           dict(pts=[[-34.4, 31], [-34.4, 54.1]], height=0.35, planter=dict(rise=0.9, width=1.4, curb=0.33)),
           dict(pts=[[-34.4, 54.1], [-36, 54.1], [-37.6, 54.1], [-39.2, 54.1], [-41, 54.1]], height=0.35)],
    # chaises [x, y, rot]: side by side on the pool-end deck, backs to the side yard, feet to the pool (p5); placed so
    # the r5 back view sees their backs above the bougainvillea planter and clear of the queen palm trunks (back #6)
    loungers=[[-29.85, -3.6, 0], [-26.75, -3.6, 0]],
    # tall palms [x, y, height ft, lean, kind] (scripts/palms.py grows the species): the brochure's queen palms
    # (Syagrus, 25-30 ft) - two in the left planter in front of the lanai, one at the right lawn corner - and the
    # two palms on the far verge that frame the front view (fronds hanging into its top corners); no tall
    # 'telephone pole' palms in the mid-ground
    # (height = clear trunk to the crown; the crown adds ~8-10 ft. Back pair (critic r2 back #1): trunks 19.5-21 ft so
    # that from the level r3 back eye (5 ft) the crowns sit ~1.5-2 m above the ridge line - the frame top is only
    # ~24 ft up at their distance, so taller trunks would push the crowns out of frame; both stand left of the lanai
    # post in a mondo planter at the chaises' foot, so the lanai opening reads clear to their right, as in p5 - the
    # left one is on the side lot line, it cannot move further left. The third stands in the bougainvillea at the
    # right end of the pool wall, as in p5.)
    # the front framing pair stand at the lot's street corners, trunks just outside the front view: only frond tips
    # reach into its top corners (~8-10% of the frame)
    palms=[[-19.9, -6.7, 21, 1, 'queen'], [-18.6, -3.3, 19.5, 1.2, 'queen'], [-31, 39, 24, 1.2, 'queen'],
           [149, 51.2, 37, 1, 'queen'], [149, -6.6, 29, 1, 'queen']],   # r5: front pair 37 vs 29 ft, no twin crowns (critique-preview4-front #6)
    # understorey palms [x, y, height ft, kind, stems]: areca / lipstick clumps, foxtail / christmas / pygmy date
    # singles, cycads - layered in the courtyards and gaps, as in the renderings (thinned r3: the back view's
    # roofline reads against the sky, critic r2 back #3)
    arecas=[[60, 16.8, 9], [66, 28.2, 10], [89, 13, 11], [90, 32, 12], [36, 50.5, 14],
            [140, -5, 13], [118, 51, 12], [46, -5.5, 12],
            # entry courtyard: lipstick palms (scarlet crownshafts) and christmas palms either side of the walk
            # (kept off the walk axis so the glass entry reads between them; the walk pair stand back by the wing
            # walls, clear of their eaves, so they flank the entry as in p4 - critic r2 front #9)
            # r5 (critique-preview4-front #5): the walk-axis crowns 2.5 ft further out toward the wing corners, and
            # scripts/palms.py prunes the fronds that point at the walk, so the glass entry reads clear between them
            [98.6, 12.5, 13, 'lipstick'], [114.0, 29.6, 14, 'lipstick'], [119.5, 17.0, 11, 'lipstick', 4],
            [96.8, 10.0, 14, 'christmas'], [90.8, 35.0, 14.5, 'christmas'],   # r4: 2 ft out toward the wing walls, 12-14 ft (front #6); r5: clear of the 6.3 ft ʻohana lānai eave
            [87.2, 11.0, 15, 'christmas'], [86.8, 33.7, 14, 'christmas'],
            # mid-ground fill between and behind the roofs
            [93, 5, 14], [90.4, 40.5, 13], [92.6, 45, 6, 'roebelenii', 2], [62.5, 17.6, 6, 'roebelenii'], [63, 27, 7, 'roebelenii'],
            # r5 (critique-preview4-front #7): the left foxtail pair and areca 5 ft further from the ʻohana (toward the
            # street and the lot line), so its street face takes the 10:00 sun
            [95, -6, 22, 'foxtail'], [146, 52.2, 20, 'foxtail', 2], [100, 50.6, 19, 'foxtail'], [136, 52.4, 10], [128, -6, 14],
            [114, -6.2, 18, 'foxtail'], [99, -5.6, 13], [76, 50.5, 13], [56, 50.8, 16, 'foxtail'],
            # back: a few palms right of the bedroom wing (half the r2 count; the tall hedge behind does the screening)
            [-20, 50, 16], [14, 50.2, 14], [-14, 48.6, 13],
            # front corners of the view: pygmy date and sago fronds in the bottom corners
            [147.4, 48.4, 6, 'roebelenii', 2], [147.4, -4.4, 3.5, 'cycad', 2], [130, 49, 3, 'cycad'],
            # r5 interim side-yard screen (critique-preview4-front #4 / back #8; register I-13a): 10-14 ft areca clumps
            # on both side lot lines, cutting each neighbour copy's roof below its gablet in the front view, and behind
            # the bedroom wing so the next roof is hidden below about y 300 of the back view
            [66, 52.4, 13], [86, 52.6, 14], [108, 52.6, 12], [123, 52.8, 11],
            [70, -6.9, 13], [82, -7.0, 14], [106, -6.9, 12], [121, -7.0, 11],
            [-6, 52.4, 13], [4, 52.6, 14], [22, 52.4, 13.5], [30, 52.6, 12.5]],
    # r5 (critique-preview4-front #2): the street pair hug the pavilions' walk-side corners, 4-5 ft off their faces,
    # at about half the r4 size, so the walk's start and a strip of lawn read; the right one stays left of the garage
    # door jamb (p4)
    plumeria=[[-4, 50, 1.2], [44, 50], [126.5, 29.4, 0.5], [126.0, 15.8, 0.48]],
    specimens=[[16, -16.0, 0.45, 'shower']],      # a pink shower tree at the far left of the back view (r4: by the side lot line, clear of the left wing, back #6)
    # beds stay clear of the coral retaining wall on the lot line (x -35.3 .. -33.5, cap to -35.4 / -33.4)
    # curve: the bed's sides (plan x0 / x1 / y0 / y1) that sweep in soft curves with a tan stone edging (scripts/plants_bpy.py);
    # edge=False: a planting inside another bed (no edging of its own)
    beds=[dict(rect=[-33.2, 36, -20, 40], kind='bougainvillea', curve='x1y0y1'), dict(rect=[-33.2, -7, -31.5, 0.5], kind='bougainvillea'),
          # r5: the raised planter on the right wall (site.js planterRun: soil x -34.97 .. -33.57, y 30.46 .. 54.64), one
          # row of bougainvillea 1 ft in from the outer face, spilling over the coping toward the bank (p5)
          dict(rect=[-34.97, 30.46, -33.57, 54.64], kind='bougainvillea', density=1.7, edge=False),
          # the chaise planter: the two queen palms rise from a mondo island at the chaises' foot (p5)
          dict(rect=[-21.3, -8.0, -15.6, -2.2], kind='mondo', curve='x0x1y0y1'),
          # the bank below the pool wall: glossy Asiatic jasmine right up to the wall, full cover (no raw soil), its lawn
          # edge a soft curve with stone edging (critic r2 back #12); no elephant ears (back #4)
          dict(rect=[-42, -8, -35.5, 53], kind='jasmine', density=2.1, curve='x0'),
          dict(rect=[-47, -22, -35, -9.2], kind='jasmine', density=2.2, curve='x0y0'),
          # entry courtyard: mondo grass under everything, ti in loose clumps (not rows), tradescantia at the garage
          # (thinner on the walk side so the leaf shapes read in the shade, critic r2 front #6)
          dict(rect=[96, 16.2, 121, 19.2], kind='mondo', density=0.8), dict(rect=[96, 25.4, 121, 28.4], kind='mondo', density=0.6),
          dict(rect=[96.8, 16.4, 99.6, 19], kind='ti', edge=False), dict(rect=[108.4, 16.4, 111, 19], kind='ti', edge=False),
          dict(rect=[102.6, 25.6, 105.2, 28.2], kind='ti', density=0.7, edge=False), dict(rect=[114.6, 25.6, 116.8, 28.2], kind='ti', density=0.6, edge=False),
          dict(rect=[117, -7.8, 123, -4.4], kind='tradescantia'),
          # beds along the walk on the front lawn (p4): one mondo bed each side, its lawn edge sweeping in soft curves
          # with stone edging (critic r2 front #13; layout assumed, I-13), gardenia at the pavilion ends and a silver
          # dichondra ribbon along the walk inside it
          dict(rect=[123, 13.6, 150, 19.3], kind='mondo', density=0.75, curve='y0'), dict(rect=[123, 25.3, 150, 31.4], kind='mondo', density=0.75, curve='y1'),
          dict(rect=[123, 15.6, 130, 18.4], kind='gardenia', density=0.7, edge=False), dict(rect=[123, 26.4, 131, 29.4], kind='gardenia', density=0.7, edge=False),
          dict(rect=[131, 17.4, 150, 19.2], kind='dichondra', edge=False), dict(rect=[132, 25.4, 150, 27.4], kind='dichondra', edge=False),
          dict(rect=[86, -4, 99, 15.8], kind='monstera'), dict(rect=[86, 28.8, 93.2, 47], kind='monstera'),   # r5: stops at the ʻohana lānai edge
          dict(rect=[57, 16.3, 67.5, 19.3], kind='groundcover'), dict(rect=[57, 25.3, 67.5, 28.2], kind='groundcover'),
          # lot lines: a clipped hedge only where it is out of the hero views; loose monstera understorey elsewhere;
          # behind the back lawn a 7 ft screen hedge on the side lot line hides the neighbour's pool (critic r2 back #11)
          dict(rect=[22, -8, 95, -6], kind='hedge'), dict(rect=[96, -8, 150, -6.2], kind='monstera', density=0.7),
          dict(rect=[30, 51.5, 95, 53.5], kind='hedge'), dict(rect=[-1, 51.6, 30, 53.4], kind='monstera', density=0.6),
          dict(rect=[-33.4, 51.7, -1, 53.4], kind='screen'),
          dict(rect=[96, 51.6, 150, 53.4], kind='monstera', density=0.45),
          # back: a ti bed along the left-wing foundation (red ti over mondo), monstera at its end; ti and mondo at the
          # primary bedroom's corner so its windows look out on planting
          dict(rect=[-2, -3.5, 14, -1], kind='ti', density=0.9, edge=False), dict(rect=[-2, -3.8, 16, -1], kind='mondo', curve='y0'),
          dict(rect=[14, -3.5, 18, -1], kind='monstera', edge=False),
          dict(rect=[-3, 40, -0.4, 44.2], kind='ti', density=0.8, edge=False), dict(rect=[-3, 39, -0.4, 44.6], kind='mondo'),
          dict(rect=[0, 44.8, 8, 46.6], kind='mondo'), dict(rect=[1.5, 45, 5.5, 46.4], kind='ti', edge=False),
          # the layered screen right of the bedroom wing: magenta bougainvillea in front of the screen hedge (p5; its copy on
          # the next lot no longer puts big heliconia leaves in the back view's left edge, critic r2 back #3), red heliconia
          # further along, a red hibiscus at the wing corner
          dict(rect=[-30, 48.8, -16, 51.4], kind='bougainvillea', density=0.8), dict(rect=[9, 48.6, 21, 51], kind='heliconia', density=0.7),
          dict(rect=[-3.6, 45, -0.6, 47.6], kind='hibiscus'), dict(rect=[-12, 49.4, -4.5, 51.4], kind='bougainvillea'),
          dict(rect=[50, -7.6, 56, -4.6], kind='hibiscus'),
          dict(rect=[36, 46, 58, 49], kind='bougainvillea'),
          dict(rect=[8, 46, 30, 49], kind='gardenia'), dict(rect=[40, -3.5, 47, -1], kind='ti')],
)
plan['viewpoints'] = [
    # hero views framed like the brochure renderings (2200x1161, 1.9:1; fov is vertical, ~24-26 mm lens)
    # suns are real moments at Kukui'ula (alt, world azimuth from +x toward +z; true north = world az 313.9,
    # from the site registration in geodata/realsite.json):
    #   front: 21 Jun 10:00 HST (alt 53, compass 80)   back: 20 Nov 1:30 pm HST (alt 45, compass 202)
    # front: from the brochure frame (horizon ~29% down, pavilions ~77% of the width, their bases ~85% down) ->
    # ~62 ft out from the pavilion fronts, ~27 ft up, pitched ~8.5 deg down; the street stays out of frame
    dict(id='front', pos=[170, 22.3], eye=21, absolute=True, look=[60, 22.3], lookH=2.0, fov=40, sun=[53, 34], aspect=1.895, photo='ref/front.png'),   # r3: ~48 ft out so the pavilions span ~77%
    # back: elevated three-quarter view over the vanishing edge onto pool, spa, chaises and lanai (critic r1)
    dict(id='back', pos=[-59.4, -11.2], eye=9.8, absolute=True, look=[-7, 23], lookH=9.8, fov=38.5, shiftY=-0.13, sun=[45.2, 156.3], aspect=1.895, photo='ref/back.png'),   # r4: in and up (~3 m above the deck), level + lens shift (plumb verticals); sun 20 Nov 13:30 HST (alt 45, compass 202) side-lights the facade; r5: fov 43 -> 38.5 and look 3 ft left so the house fills ~25% and sits near centre (critique-preview4-back #4)
    dict(id='front-wide', pos=[166, 22.3], eye=30, absolute=True, look=[66, 22.3], lookH=4, fov=50, sun=[58, 320]),
    dict(id='back-wide', pos=[-54, -2], eye=5.2, absolute=True, look=[6, 18], lookH=6.0, fov=64, sun=[44, 215]),
    dict(id='great-room', pos=[X(1240), Y(1150)], look=[X(620), Y(800)], fov=72),
    dict(id='kitchen', pos=[X(760), Y(1000)], look=[X(1280), Y(620)], fov=72),
    dict(id='lanai', pos=[X(560), Y(1150)], look=[X(230), Y(700)], fov=72),
    dict(id='primary', pos=[X(520), Y(1260)], look=[X(250), Y(1520)], fov=72),
    dict(id='primary-bath', pos=[X(720), Y(1420)], look=[X(900), Y(1300)], fov=75),
    dict(id='bedroom-3', pos=[X(1720), Y(890)], look=[X(1500), Y(600)], fov=72),
    dict(id='courtyard', pos=[X(1900), Y(1063)], eye=5.4, look=[X(1284), Y(1063)], fov=65),
]
# real-life details (fixtures, hardware, utilities, styling): tools/details_ext.py + tools/details_int.py
sys.path.insert(0, str(Path(__file__).parent))
import details_ext, details_int
plan['details'] = details_ext.DETAILS + details_int.DETAILS
out.write_text(json.dumps(plan, indent=1))
print('with site + viewpoints ->', out, f"({len(plan['details'])} details)")
