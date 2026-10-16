# Assumptions register — Nā Hiku spec home (Lot 25 design), concept visualization

**Status: concept visualization.** This is not construction documentation or as-built documentation, and it is not a verified view.
It is the best-supported model from the data supplied so far (client direction: "give it your best guess", "use all data we have").
The brochure says its renderings are "preliminary… for illustration purposes only" and "not… shown to proportion or scale" (pp. 1–5).

Each element below is classed as one of three kinds:
- **S — supplied measurement.** Stated in the brochure, or measured real-world data.
- **E — scale-derived estimate.** Traced from the p6 floor plan at a derived scale.
- **I — inferred or assumed geometry.** Read off renderings, or a reasonable default.

## Supplied measurements (S)
| Item | Value | Source |
|---|---|---|
| Main house AC area | 2,300 sq ft | Brochure p6 (Lot 25 floor plan) |
| Guest ʻohana AC area | 352 sq ft | p6 |
| Total AC | 2,652 sq ft | p6 |
| Covered lānai | 494 sq ft | p6 |
| Homesite (Lot 25, Aepo Nei) | 13,195 sq ft | p6. Not the Nā Hiku lot; see I-8 |
| Programme | 4 bedrooms, 4.5 baths, plus room names and labels | p6 |
| Sized labels on the plan | "36″ REF", "24″ SPEED OVEN" | p6 |
| Terrain around the site | USGS 3DEP 1 m DEM (HI_FEMAR9Kauai_2019_D19), 1/3″ DEM | geodata/SOURCES.txt |
| Ground colour, roads, footprints, trees | Sentinel-2 L2A 2023–26; OSM + Microsoft footprints (Overture); Meta/WRI canopy heights | geodata/SOURCES.txt |
| Sun positions | Computed for real dates: front 21 Jun 10:00 HST (alt 53°, az 80°); back 20 Nov 13:30 HST (alt 45°, az 202°). The dates were chosen for the light (the back for side light); each sun position is the real one for its date and site | tools/gen_lot25.py viewpoints |

## Scale-derived estimates (E)
| Item | Value | How derived and checked |
|---|---|---|
| E-1 Floor-plan scale | 23 px/ft at 300 dpi | p6 has no dimension strings or scale bar, so the scale was fitted to the stated areas. Modelled net areas: main 2,280 sq ft against 2,300 gross stated; lānai + entry 522 against 494; ʻohana + bath 332 against 352. The fridge symbol measures 3.26 ft against its 36″ label. **Estimated accuracy ±3–8 % linear.** Overlay: scratchpad/verify/plan_overlay.jpg |
| E-2 Walls, openings, rooms | Positions, lengths, thicknesses (0.5 ft ext / ~0.4 int), door and window widths | Traced from p6 (tools/gen_lot25.py `hwall`/`vwall`); inherits E-1 |
| E-3 Kitchen, bath fixtures, furniture layout | As drawn on p6 | Traced; symbol sizes include outlines |
| E-2a Tracing corrections (round 5, from the model-view review) | The ʻohana lānai now runs to p6's corner posts: 6.3 ft deep, ≈ 90 sq ft (it was traced 2.66 ft deep). The hall and the vestibule have windows onto the entry, as p6 draws them; they were modelled as open doorways. Their sill and head heights are assumed (I-2) | Re-traced from p6; inherits E-1 |
| E-4 ʻOhana floor plan | 352 sq ft programme | p6 inset; same scale as E-1 assumed |

## Inferred or assumed geometry (I)
| Item | Value used | Basis | Document that would resolve it |
|---|---|---|---|
| I-1 Plate and ceiling height | 10.0 ft plate; vaulted ceilings follow the roof | Default for this house type; interiors on p7 board | Building sections, interior elevations |
| I-2 Window and door heights | Bed/living sill 1.5, head 8.0; bath 4.5/8.0; kitchen 4.0/8.0; sliders head 9.0; great-room pocket door head 9.5 | p5 rendering, by eye | Exterior elevations, window/door schedule |
| I-3 Roof | Hips at pitch 0.55 (≈6.6:12), skirt 0.25, overhangs 2.0–3.0 ft, Dutch gablets 3.5 ft, standing seam (16″ panels, 1½″ seams modelled as geometry, raised hip and ridge caps) | p4/p5 renderings | Roof plan, elevations, sections |
| I-3a **Great-room roof form** | A cross hip over the great room and entry (plan x 24.7–56.1 ft): ridge runs across the view (plan y) at about 18.6 ft and about 10 ft long. Street and back planes at 0.55; the hip ends at 0.95 (≈11.4:12). The main hip's 17.8 ft ridge along plan x dies into its back plane. The lānai end is unchanged. | **Inferred from the p4 rendering, not the plan.** p4 shows a broad trapezoid with its ridge across the view over the glazed entry. Equal pitches on this 37 × 28 ft block would give a triangular hip end, so the hip ends were steepened. The client said "give it your best guess" (critique-preview3-front #2). | Roof plan, front and side elevations |
| I-2a Lānai frontage (back) | The cedar header (10×14) is dropped to a 7′-11″ underside with a painted frieze up to the soffit, set 2″ behind the beam's face so the beam stands proud with a shadow line (r5, p5). Posts 10×10, warm rough-sawn cedar (about sRGB 150/105/70). The lānai's two side-wall openings get cedar louvered shutter panels (sizes unchanged). The right-hand double-hung on the TV wall moves 3.2 ft clear of the corner post. | **Follows the p5 rendering, not the plan.** The plan shows unglazed openings, and the header at the plate hid behind the gutter (critique-preview3-back #8). | Exterior elevations, window/door schedule, framing plan |
| I-2b Entry header and roof wells (front) | The entry's 8×18 cedar porch header (plan x 56.1 ft) is dropped to a 7′-3″ underside with a painted frieze above, so it shows under the great roof's gutter from the street. A 1 ft cedar-clad header band, 3″ proud, also runs across the pivot door and sidelights (head 9.0 ft). The two roof wells over garden showers 2 and 3 (4.5 × 5.8 ft) are cedar-lined, with 2×4 cedar slats on edge at 4″ centres running down the fall line, tops 2″ below the metal. | **Follows the p4 rendering, not the plan.** p6 shows neither the header nor the wells' construction (critique-preview4-front #5, #11). | Exterior elevations, roof plan, details |
| I-4 **Garage pavilion** | **22.0 × 15.9 ft (≈350 sq ft)**, 9 × 8 ft carriage door, at the street end of the walk | Not on p6 at all; from p4 front rendering | Garage/carport plan and elevations, architectural site plan |
| I-5 **ʻOhana placement** | Faces the walk opposite the garage (street face x = 122 ft, walk face y = 32.3 ft) | p6 draws it as a separate inset with no siting; position from p4 | Architectural site plan (plot plan) for the actual homesite |
| I-6 **Lot width and shape** | **61.5 × 184.4 ft modelled (11,341 sq ft)**; neighbours ~70 ft apart | Nā Hiku fairway-7 lot sizes not supplied (p9 lists "Fairway 7 homes 1 through 14" separately); spacing from satellite registration | Subdivision plat, boundary + topographic survey of the homesite |
| I-7 Which homesite | The 7th of 14 from the north-west end | Assumed | Developer: lot number and plat |
| I-8 Design used on the Nā Hiku lot | The Lot 25 (Aepo Nei) design | Client: "those are the spec homes… they made for that area" | Developer confirmation of the fairway-7 home designs |
| I-9 Site registration | lat 21.8908, lon −159.4832, **±25 m**; plan +x bearing 46.3°; pad 17.6 m above sea level | Matched to imagery and DEM (scripts/geo_register.py) | Survey with coordinates, finished-floor elevation |
| I-10 Pool, spa, vanishing edge | Water 30 × 13 ft, 4.5 ft deep; spa about 7.5 × 8 ft set into the pool; 3 ft drop to a 2.5 ft catch basin | p5 rendering | Pool plans and sections |
| I-10a Vanishing-edge detailing (round 5) | The weir spills over its whole length except the last ~10 cm (0.33 ft) at the right pier, which is a dry stone return under a bullnosed coping. The falling water is drawn as one continuous sheet that gets whiter (more aerated) from the lip to the foot. The catch basin uses the pool's water colour | Illustrative (critique-preview4-back #1). p5 shows the sheet running to the pier, but its end detail cannot be read | Pool plans and sections, weir detail |
| I-11 Grading and retaining wall | Floor 0, grade −0.6 ft; ~5 ft drop behind the lot on a coral retaining wall with return walls at the side lines | p5 rendering and DEM slope | Civil grading/drainage plan, wall details |
| I-11a Right-hand wall planter (round 5) | The lot-line wall right of the pool (plan y 31 → 54.1 ft) has a raised planter on top. Its face is carried 0.9 ft higher, with 1.4 ft of soil between two 4″ curbs (~0.63 m overall), and one row of bougainvillea spills over the coping toward the bank. Stone cladding is laid with ~15 cm stones low on the walls and ~8.5 cm stones high | **Follows the p5 rendering, not the plan.** p5 shows bougainvillea over the right wall; the plan does not show the wall (critique-preview4-back #10) | Landscape plan, wall details |
| I-12 Materials and finishes | Galvalume standing seam, white lap siding, black frames, cedar, coral stone, white oak, etc. | p4/p5 renderings, p7 design board (concept, not a spec) | Finish schedule, specification book |
| I-12a Great-room feature wall (behind the TV) | Painted white board-and-batten, not the coral stone sample | Follows the plantation wall in the p7 board's lānai photo instead of the board's coral swatch. Seen through the glass under the warm interior lights, the coral read as an amber panel (critique-preview3-back #10) | Interior elevations, finish schedule |
| I-14a Neighbour copies in the stills | Their roofs carry an airlight veil (28%, camera only; raised from 13% in round 5 so the copies stop reading as one roofscape with this home), so they read lighter and softer than this home | Retouching choice for the front/back stills while I-14 is open. Not a claim about the neighbours' finishes | Same as I-14 |
| I-13 Planting | Queen/foxtail/areca palms, ti, plumeria, bougainvillea, monstera, lawn | p4/p5 renderings | Landscape plan |
| I-13a Side-yard screen planting and plumeria siting | 10–14 ft areca clumps along both side lot lines (front yard plan x 66–123; behind the bedroom wing plan x −6–30). The two street plumerias sit 4–5 ft off the pavilion faces at about half the round-4 size. The front corner queen palms are 37 ft and 29 ft. The entry-courtyard palms are pruned on the walk side. | **Interim retouching choice, not from a plan.** The screen hides the assumed neighbour copies (I-14) below their gablets; p4 shows open fairway and softened neighbours instead. Plumeria positions follow p4. | Landscape plan; the developer's site plan for homes 1–14 (I-14) |
| I-13b Hardscape layout | **Entry walk:** single 2 × 4 ft honed tan stone slabs, centred on the 5 ft walk strip (plan x 68.6–152), with 5 in grass joints. The slabs sit 1½ in above the lawn. **Drive:** a tan stone border of 2 ft cut pieces along both long sides of the grass-paver drive, 15 in wide on the walk side and 12 in on the far side. **Pool deck:** a 7.5 × 7 ft paved strip at the pool's left end (plan x −31.5 to −24, y −7 to 0). It carries two teak chaises side by side, backs to the side yard and feet to the pool. | Slab size, joints, border and stone colour follow the p4 rendering; the deck and chaises follow p5. Not on the p6 plan. The deck and chaise positions are also set so the round-5 back camera sees the chaises above the planter and clear of the palm trunks. | Landscape / hardscape plan, pool deck plan |
| I-14b Neighbour copies' gardens | On each copied lot, the queen palms are kept, swapped for foxtails or a shade tree, or left out, by a per-lot hash. Kept palms vary ±25 % in height. The back-yard queens on the two adjacent lots are left out. | Assumed, so that the copies do not repeat one skyline. The back view's camera stands in the left neighbour's side yard. | Same as I-14 |
| I-14 Neighbouring Nā Hiku homes | Copies of this design | Assumed for context only | Developer site and architectural plans for homes 1–14 |
| I-15 Interior styling and furniture models | Per the p7 board | Concept | Furniture package and interior design drawings |
| I-16 Background retouching in the stills (round 5) | Real-site land: at least 25% airlight (horizon sky) from ~200 m and ~40% less saturation by 200 m; footprint massing: at least 30% airlight beyond ~250 m, darker walls with eave shadow, storey openings and a dark base. Open turf on the real terrain is drawn as golf fairway and rough (mowing stripes) and a dark coastal canopy band with scattered roofs runs along the shore, instead of the raw Sentinel-2 colour. Background trees are spreading monkeypod / kiawe / kamani crowns in groves, and a belt of canopy trees is planted along the foot of each background building 300–4,000 ft off | Retouching choices for the stills (camera only). The tree positions are the canopy-height data's. The groves, building belts, fairway layout and coastal roofs are illustrative, not surveyed | Site photos or drone views from the lot; golf course plan |

## Not claimed
- Approved architecture or construction readiness.
- Verified views from the lot. The brochure itself disclaims views.
- As-built accuracy.
