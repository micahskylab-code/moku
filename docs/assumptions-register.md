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
| Sun positions | Computed for real dates: front 21 Jun 10:00 HST (alt 53°, az 80°); back 20 Nov 13:30 HST (alt 45°, az 202°) | tools/gen_lot25.py viewpoints |

## Scale-derived estimates (E)
| Item | Value | How derived and checked |
|---|---|---|
| E-1 Floor-plan scale | 23 px/ft at 300 dpi | p6 has no dimension strings or scale bar, so the scale was fitted to the stated areas. Modelled net areas: main 2,280 sq ft against 2,300 gross stated; lānai + entry 522 against 494; ʻohana + bath 332 against 352. The fridge symbol measures 3.26 ft against its 36″ label. **Estimated accuracy ±3–8 % linear.** Overlay: scratchpad/verify/plan_overlay.jpg |
| E-2 Walls, openings, rooms | Positions, lengths, thicknesses (0.5 ft ext / ~0.4 int), door and window widths | Traced from p6 (tools/gen_lot25.py `hwall`/`vwall`); inherits E-1 |
| E-3 Kitchen, bath fixtures, furniture layout | As drawn on p6 | Traced; symbol sizes include outlines |
| E-4 ʻOhana floor plan | 352 sq ft programme | p6 inset; same scale as E-1 assumed |

## Inferred or assumed geometry (I)
| Item | Value used | Basis | Document that would resolve it |
|---|---|---|---|
| I-1 Plate and ceiling height | 10.0 ft plate; vaulted ceilings follow the roof | Default for this house type; interiors on p7 board | Building sections, interior elevations |
| I-2 Window and door heights | Bed/living sill 1.5, head 8.0; bath 4.5/8.0; kitchen 4.0/8.0; sliders head 9.0; great-room pocket door head 9.5 | p5 rendering, by eye | Exterior elevations, window/door schedule |
| I-3 Roof | Hips at pitch 0.55 (≈6.6:12), skirt 0.25, overhangs 2.0–3.0 ft, Dutch gablets 3.5 ft, standing seam (16″ panels, 1½″ seams modelled as geometry, raised hip and ridge caps) | p4/p5 renderings | Roof plan, elevations, sections |
| I-3a **Great-room roof form** | A cross hip over the great room and entry (plan x 24.7–56.1 ft): ridge runs across the view (plan y) at about 18.6 ft and about 10 ft long. Street and back planes at 0.55; the hip ends at 0.95 (≈11.4:12). The main hip's 17.8 ft ridge along plan x dies into its back plane. The lānai end is unchanged. | **Inferred from the p4 rendering, not the plan.** p4 shows a broad trapezoid with its ridge across the view over the glazed entry. Equal pitches on this 37 × 28 ft block would give a triangular hip end, so the hip ends were steepened. The client said "give it your best guess" (critique-preview3-front #2). | Roof plan, front and side elevations |
| I-2a Lānai frontage (back) | The cedar header (10×14) is dropped to a 7′-11″ underside with a painted frieze up to the soffit. The lānai's two side-wall openings get cedar louvered shutter panels (sizes unchanged). The right-hand double-hung on the TV wall moves 3.2 ft clear of the corner post. | **Follows the p5 rendering, not the plan.** The plan shows unglazed openings, and the header at the plate hid behind the gutter (critique-preview3-back #8). | Exterior elevations, window/door schedule, framing plan |
| I-4 **Garage pavilion** | **22.0 × 15.9 ft (≈350 sq ft)**, 9 × 8 ft carriage door, at the street end of the walk | Not on p6 at all; from p4 front rendering | Garage/carport plan and elevations, architectural site plan |
| I-5 **ʻOhana placement** | Faces the walk opposite the garage (street face x = 122 ft, walk face y = 32.3 ft) | p6 draws it as a separate inset with no siting; position from p4 | Architectural site plan (plot plan) for the actual homesite |
| I-6 **Lot width and shape** | **61.5 × 184.4 ft modelled (11,341 sq ft)**; neighbours ~70 ft apart | Nā Hiku fairway-7 lot sizes not supplied (p9 lists "Fairway 7 homes 1 through 14" separately); spacing from satellite registration | Subdivision plat, boundary + topographic survey of the homesite |
| I-7 Which homesite | The 7th of 14 from the north-west end | Assumed | Developer: lot number and plat |
| I-8 Design used on the Nā Hiku lot | The Lot 25 (Aepo Nei) design | Client: "those are the spec homes… they made for that area" | Developer confirmation of the fairway-7 home designs |
| I-9 Site registration | lat 21.8908, lon −159.4832, **±25 m**; plan +x bearing 46.3°; pad 17.6 m above sea level | Matched to imagery and DEM (scripts/geo_register.py) | Survey with coordinates, finished-floor elevation |
| I-10 Pool, spa, vanishing edge | Water 30 × 13 ft, 4.5 ft deep; spa about 7.5 × 8 ft set into the pool; 3 ft drop to a 2.5 ft catch basin | p5 rendering | Pool plans and sections |
| I-11 Grading and retaining wall | Floor 0, grade −0.6 ft; ~5 ft drop behind the lot on a coral retaining wall with return walls at the side lines | p5 rendering and DEM slope | Civil grading/drainage plan, wall details |
| I-12 Materials and finishes | Galvalume standing seam, white lap siding, black frames, cedar, coral stone, white oak, etc. | p4/p5 renderings, p7 design board (concept, not a spec) | Finish schedule, specification book |
| I-12a Great-room feature wall (behind the TV) | Painted white board-and-batten, not the coral stone sample | Follows the plantation wall in the p7 board's lānai photo instead of the board's coral swatch. Seen through the glass under the warm interior lights, the coral read as an amber panel (critique-preview3-back #10) | Interior elevations, finish schedule |
| I-14a Neighbour copies in the stills | Their roofs carry a light airlight veil (13%, camera only), so they read lighter and softer than this home | Retouching choice for the front/back stills while I-14 is open. Not a claim about the neighbours' finishes | Same as I-14 |
| I-13 Planting | Queen/foxtail/areca palms, ti, plumeria, bougainvillea, monstera, lawn | p4/p5 renderings | Landscape plan |
| I-14 Neighbouring Nā Hiku homes | Copies of this design | Assumed for context only | Developer site and architectural plans for homes 1–14 |
| I-15 Interior styling and furniture models | Per the p7 board | Concept | Furniture package and interior design drawings |

## Not claimed
- Approved architecture or construction readiness.
- Verified views from the lot. The brochure itself disclaims views.
- As-built accuracy.
