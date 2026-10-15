# Nā Hiku · Lot 25: real-life detail inventory

**What this is:** a list of what the finished, lived-in house would actually have, written from the point of view of someone who has built and photographed single-storey plantation-modern homes in Poʻipū and Kukuiʻula. The brochure renderings leave most of this out, and real photographs always show it. The list is organised by area. For each item it gives the real product or spec typical on Kauaʻi, the dimensions and mounting height, the count and location on this plan, and the colour or finish.

## Conventions

- **Coordinates** are plan feet from `plans/lot25.json`. **+x = north** (toward the Nā Hiku road / street, x ≈ 150). **+y = east.** The pool is at x −31…−17, so south is the ocean side. Walls are named by their fixed coordinate. "Wall y 0.17" is the 60-ft **west** elevation, "y 44.39" is the **east** elevation, "x 0 / x 1.83" are the **south** (pool) faces, and "x 84.78 / x 122" are the **north** (street) faces.
- **AFF** = above finished floor. **AFG** = above finished grade. Keep the model's grade at −0.6 ft: the slab floor sits 7" above grade, as Kauaʻi builders actually set it.
- **Albedo** = linear diffuse reflectance for shaders (§0.3).
- ⚠ **Plan check** marks places where the traced plan or furniture list could not be built that way. A real builder would change these, and a viewer who knows houses will notice them. All of them are collected at the end.
- **Age setting.** Model the house about **12–18 months after completion**: staged but lived in. Planting has filled in, wood has started to weather, and there are a few signs of use. A brand-new spec home photographed on hand-over day is the less believable option, because it looks like CG.

---

## 0. Kauaʻi baseline: code and climate facts that show up in a photo

### 0.1 Climate as it appears in the picture
- **Trade winds.** ENE, from a bearing of about 60–70°, at 10–20 mph about 70% of the time. In plan terms the wind blows **from the street-east corner toward the pool-west corner** (toward −x, −y). The effects to show:
  - Palm fronds stream to the WSW.
  - Areca and ti leaves flag in the same direction.
  - Pool water has fine capillary ripples.
  - Market umbrellas are closed or tied.
  - Linen drapery at open sliders bellies inward on east and north openings.
- **Rain.** The Poʻipū dry side gets about 35–45 in a year, mostly from winter Kona storms and passing trade showers. Afternoon cumulus banks over the mountains to the north: Kahili / Waiʻaleʻale cloud cap, and the Hāʻupu (Hoary Head) ridge to the NE. The ocean horizon to the SSE is usually hazy.
- **Sun.** Latitude 21.9° N, so:
  - The sun is **south of the zenith except about 27 May–17 July**.
  - Noon altitude is about 45° in December and about 88° in June.
  - The north (street) faces sit in **open shade most of the year**. They catch low, raking sun only in the first and last 2–3 hours of the day between late March and late September.
  - The south (pool and lānai) side is sunlit all day, all year. In winter, sun reaches about 8–10 ft into the 16.8-ft-deep lānai. From May to August at midday the lānai floor is fully shaded.
  - ⚠ The `front` viewpoint sun of altitude 58° / azimuth 320° cannot happen here. At 58° altitude the furthest north the sun gets is azimuth about 280°, which is June 21 at about 3 pm HST.

  Real sun positions (altitude / azimuth):

  | Date | 8 am | 10 am | 2 pm | 4 pm | 5 pm |
  |---|---|---|---|---|---|
  | Jun 21 | 26/74 | 53/80 | 71/279 | 44/282 | 30/285 |
  | Sep 22 | 21/98 | 48/115 | 60/229 | 35/255 | 21/262 |
  | Dec 21 | 9/120 | 31/138 | 40/206 | 23/231 | 11/239 |

- **Salt.** The lot is about 0.5–1 mile from the shore and about 230 ft up (model sea level −230). Manufacturers treat that as coastal or marine exposure:
  - Exposed hardware is 316 stainless or coastal-rated powder coat.
  - Bare 304 stainless "tea-stains" (brown freckles) within a year.
  - Galvanised parts grow white rust at cut edges.
  - Black aluminium chalks slightly on sun faces.
  - Glass on the ocean side carries a faint salt film.
- **UV.** The index is 11–12 for most of the year.
  - Unoiled cedar silvers in 6–12 months.
  - Teak goes grey within a season.
  - Plastics yellow, and cheap black plastics go chalky grey.
  - White Sunbrella stays white.
- **Red dirt.** Kauaʻi's iron-rich oxisol stains everything at ground level a rusty orange-brown, sRGB about (150, 80, 50). It shows on grout, the bottom course of siding, the bottom rail of cedar, mow curbs and hose ends.

### 0.2 Code and practice items that are physically visible
| Topic | What is real on Kauaʻi | Where it shows |
|---|---|---|
| Hurricane ties | Hurricane ʻIniki (Cat 4, 1992) hit Poʻipū directly, so every rafter, beam and post is tied: Simpson H2.5A/H10A at rafters, MSTC/LSTA straps, HDU holdowns, CCQ/ECCQ post caps, CBSQ/ABU standoff post bases. Hawaiʻi-amended IRC/IBC design wind is about 130 mph ultimate plus topographic speed-up. | Only where structure is exposed: lānai beam and posts, entry beam and posts, ʻohana lānai, garage interior. Elsewhere it is hidden behind T&G and siding. |
| Connector corrosion class | ZMAX (G185) hot-dip galvanised is the minimum with treated lumber. Stainless (304/316) is used for salt "severe" exposure. For architectural exposed timber, use Simpson "Outdoor Accents" black powder-coated ZMAX (APB post base, APL/APT ties, APHH hangers) with hex-head structural screws, or custom black-painted steel knife plates with ¾" through-bolts. | Bolt heads and black plates on the cedar. |
| Termites | Hawaiʻi amendments require termite-resistant structure: borate-treated ("Hi-Bor") framing indoors, ACQ/CA ground-contact treatment outdoors, or light-gauge steel studs (very common here). Also soil pre-treatment, basaltic termite barrier granules at slab penetrations, and monitoring bait stations after occupancy. | **Sentricon / Trelona bait stations:** round 5–6" flush caps (dark green or tan) at grade, 18–24" off the foundation, every 10–20 ft. About **18 around the main house, 6 around the ʻohana, 6 around the garage.** |
| Fire sprinklers | Hawaiʻi law bars counties from mandating sprinklers in new one- and two-family homes. | **No sprinkler heads anywhere.** Don't add them. |
| Smoke / CO alarms | Hard-wired, interconnected, with battery backup: one in each bedroom, one outside each sleeping area, one per storey. A combination smoke/CO unit goes in halls if any fuel-burning appliance exists. | §8–11: 6 in the main house (3 bedrooms, great room near the primary door, 2 halls), 1 in the ʻohana. |
| Safety glazing | A tempered or laminated "bug" (small sandblasted logo, about ¾ × ½", in one lower corner) is required on all door glass and sidelites, on glass within 24" of a door, on panes over 9 sf with the bottom under 18" AFF, and on glass near tubs and showers. | Visible in close-ups on every slider, the pivot door, and the bath windows near showers. |
| Pool barrier | IRC Appendix G / ISPSC as adopted. A barrier of at least 48", self-closing and self-latching gates with the latch at 54" or higher. Where the house is part of the barrier, every door opening toward the pool needs a UL-2017 alarm or a self-closer. | Poolguard-type door alarms beside the lānai pocket door and the primary slider. A black welded-wire fence hidden inside the boundary hedges. A MagnaLatch gate in the side yards. |
| Solar water heating | HRS §196-6.5 requires a solar water heater on new single-family homes unless a variance is granted, usually for a heat-pump water heater, often paired with PV. | Either a 4 × 10 ft flat-plate collector on a south roof slope, or a heat-pump water heater in the "wh" closet (more likely today). |
| Seabird lighting | Kauaʻi County rules and the Kukuiʻula Design Review Board (DRB) require fully shielded, downward-only exterior lighting at 3000 K or below (2700 K or amber preferred). This protects endangered Newell's shearwater (ʻaʻo) and Hawaiian petrel (ʻuaʻu), especially during the Sept 15 – Dec 15 fledging season. | **Down-only** cylinder sconces, no wall-washing uplights, very little landscape uplighting, warm colour temperature. Night shots look dim and amber compared with mainland CG. |
| Screens | Insect screens on every operable window and door (mosquitoes, moths, geckos). | Grey, softened lower sashes, and retractable screen housings at slider heads. |
| Ceiling fans | In every bedroom, the great room, the lānai, the ʻohana. | §7–11. |
| Outdoor showers | Standard here. This plan has three garden showers; a pool-rinse post is common as well. | §6, §10, §11. |
| Shoes off | Universal on Kauaʻi. | Slippers ("rubbah slippahs") and a shoe bench at every entry. This is the single most local lived-in cue. |
| Clotheslines | Hawaiʻi's solar-access law protects clotheslines on single-family lots, and power costs about $0.45/kWh. | A retractable line in the laundry side garden (§11). |
| ʻOhana | A Kauaʻi "guest house" (500 sf or less, verify) may not have a kitchen. A wet bar is acceptable. | §2. No range in the ʻohana. |

### 0.3 Albedo / colour targets (the biggest single CG giveaway is wrong albedo)
| Material | Linear albedo | sRGB approx (sunlit, neutral WB) | Notes |
|---|---|---|---|
| White exterior paint (SW 7006 Extra White, LRV 86 / Hardie "Arctic White") | 0.80–0.84 | 236, 236, 231 | Never 1.0. Satin, roughness about 0.45. |
| White interior paint (BM Chantilly Lace OC-65 or White Dove OC-17) | 0.82–0.88 | 240, 238, 232 | Walls eggshell (roughness about 0.55), trim semi-gloss (about 0.3). |
| Black window / door frames (powder or anodised) | 0.04–0.05 | 22, 23, 24 | Roughness 0.35–0.5. Frames must show sky reflections, never a void. |
| Standing seam, painted "Ash/Dove Gray" Kynar | 0.30–0.40 | 140, 144, 148 | Dielectric with clear-coat spec, roughness 0.30–0.35. |
| Bare Galvalume (if chosen) | metallic, base about 0.55 | 160, 162, 165 | Roughness 0.25–0.35, slightly anisotropic along the panel. |
| Western red cedar, oiled, new | 0.20–0.30 | 160, 100, 66 | Salmon to honey, varies board to board. |
| Western red cedar, 12–18 months | 0.28–0.38 | 150, 138, 120 | Silvering on sun faces, honey in shade. |
| White oak floor, natural matte | 0.40–0.50 | 205, 178, 140 | Rift/quartered, roughness 0.5–0.6. |
| Coral stone / cream limestone | 0.55–0.65 | 222, 210, 186 | Porous normal map. |
| Lawn (zoysia / paspalum) | 0.08–0.14 | 80, 115, 45 | Much darker than CG lawns. Shade turns blue-green. |
| Palm / monstera leaf (upper) | 0.06–0.12 | 55, 85, 30 | Strong transmission in backlight. |
| Areca frond (sun-yellowed) | 0.12–0.18 | 120, 135, 55 | Yellower than you think. |
| Asphalt, aged | 0.12–0.18 | 95, 95, 93 | |
| Tan sand-finish concrete curb | 0.40–0.45 | 200, 185, 155 | |
| Jute rug | 0.35–0.40 | 185, 155, 110 | |
| Teak, oiled / silvered | 0.25–0.30 / 0.35–0.45 | 150, 105, 65 / 155, 150, 140 | |
| White Sunbrella canvas | 0.72–0.78 | 232, 228, 218 | Never pure white; creams in sun. |
| Matte black fixtures | 0.03–0.04 | 18, 18, 18 | Roughness 0.5; show fingerprints on levers. |
| White quartz | 0.78–0.82 | 238, 238, 236 | Polished, roughness 0.05–0.1, with soft reflections. |

---

## 1. Street, front approach, and garage pavilion

### 1.1 Street edge (x ≈ 150–152)
- **Nā Hiku road surface.**
  - *Spec:* asphalt concrete, 20–24 ft wide, aged to mid-grey, with lighter tyre polish in the wheel paths, a few darker sealed cracks and patch rectangles, and oil drips down the lane centre.
  - *Finish:* albedo 0.12–0.18.
- **Road edge.**
  - *Spec:* most Kukuiʻula internal streets have **no sidewalk**. They have a concrete roll curb or a flat 2-ft concrete valley gutter: light grey, broom finish, control joints every 5 ft, expansion joints every 20 ft, with grass shoulders of 4–8 ft up to the lot line.
  - *Where:* the full lot frontage, y −8 → 53.5.
- **Driveway apron.**
  - *Spec:* a County-standard concrete apron from the curb to the lot line, broom-finished, about 16 ft wide with flared wings, with a straight cold joint where it meets the grass pavers.
  - *Where:* y −3.6 → 12.3, x 150 → about 156.
- **Utility furniture.** Real lots always have some in the shoulder. Utilities are underground in Kukuiʻula.
  - (a) **KIUC pad-mount transformer.** Green steel box about 40 × 40 × 32" on a concrete pad, shared by 2–4 lots. Put it on the lot line with the west neighbour (about x 151, y −10). Leave a 3-ft clear working face toward the street and screen the other three sides with clusia or naupaka.
  - (b) **Concrete handholes.** 2–3 grey precast boxes about 17 × 30" with lids stamped ELECTRIC, TELEPHONE and CATV, flush in the grass shoulder near y −6…−2.
  - (c) **Kauaʻi Department of Water meter box.** Concrete, about 13 × 24", with a cast-iron or composite lid reading WATER, at about (150, 15) between the drive and the walk. Grass grows over its edges.
  - (d) **Sewer lateral cleanout.** A 4" cap in a 10" round green valve-box lid at about (150, 30).
- **Street lighting.** None, or only low shielded bollards (seabird rules). Don't add street-lamp poles.
- **Mailbox.** **None.** Kukuiʻula uses cluster mailboxes. A curbside mailbox reads as mainland.
- **Address marker.** Kauaʻi needs numbers at least 4" tall with a ½" stroke, contrasting, visible from the road. The Kukuiʻula idiom:
  - A **30–36" coral-stone or ipe post / low monument** at the walk entry, east side, about (150, 27).
  - **4–5" brushed 316 stainless or black numerals** on it (a four-digit address).
  - Often a separate carved-wood **house-name plaque** ("Hale …", about 6 × 24", natural koa or teak, oiled).
  - A second set of 5" black numerals on the garage street face, right of the door, at about 60" AFG (y ≈ 11).
- **Lot-line hedges.**
  - *Spec:* **Clusia rosea** (autograph tree, thick paddle leaves) or **naupaka** (Scaevola taccada, the native coastal hedge), 5–6 ft tall and 2–3 ft deep, clipped flat on top with a slightly ragged face. A black vinyl-coated 48" welded-wire pool-barrier fence runs inside it, visible only in gaps (§6.8).
  - *Where:* model beds y −8…−6 and y 51.5…53.5, x −30 → 150.

### 1.2 Driveway (x 122–152, y −3.6–12.3, 30 × 16 ft)
- **Grass pavers.**
  - *Spec:* the reference shows **hexagonal concrete grass cells**. The real-world equivalents are concrete turf block or a plastic ring grid (TRUEGRID Pro Lite, Grasspave2) filled with sod.
  - *Look:* the concrete or grid rims show as a pale tan honeycomb at about 30–40% of the area. Grass in the cells is thinner and yellower than the lawn. **Two worn wheel tracks** (centres about 5'-2" apart, each 10–12" wide) are browner. There is an oil spot and a few red-dirt tyre marks at the garage end.
  - *Edges:* 8" tan sand-finish concrete header bands on the sides and street end.
- **Garage apron.**
  - *Spec:* a concrete slab 4 ft deep × 11 ft wide in front of the carriage door, tan sand finish to match the curbs, sloped ¼"/ft away from the door. A 4" polymer channel drain with a black grate runs along the door line (garage floor about ½" higher).
  - *Where:* x 122–126, y −1.2…9.9.
- **Curved mow curbs** (the tan serpentine bands in the reference).
  - *Spec:* poured concrete mow curb, 6" wide × 6–8" deep, flush with the lawn, integral colour (Davis "Sandstone" or "Mesa Buff"), sand or light broom finish, with tooled joints every 4–5 ft.
  - *Real look:* grass blades overhang it, edges are slightly chipped, a few joints have cracked through, and red dirt and mulch spill onto the bed side.
  - *Count:* about 180–220 linear ft across the front yard.

### 1.3 Front walk, street to courtyard (x 68.61–152, y 19.8–24.8: 83 × 5 ft)
- **Step slabs.**
  - *Spec:* the reference shows large light-tan rectangular pads with grass joints. Real options: precast architectural concrete step slabs, 24 × 48 × 2½" in "sand"/"natural", or honed Indonesian limestone (*paras/palimanan*) or coral stone at 600 × 1200 × 40 mm.
  - *Size/count:* 48" wide (inside the 5-ft walk, 6" of grass each side). Laid on a 30" module with 6" joints, that is about **33 pads**. Near the street the reference turns the walk into a continuous tan concrete band. Keep that for the last 8–10 ft.
  - *Joints:* zoysia, or **dwarf mondo grass** (Ophiopogon japonicus "Nana") plugged at 4–6".
  - *Real imperfections:* ±⅛–¼" lippage between pads, ¼" arrised edges, one or two hairline cracks, a slight hollow worn in the centre line, irrigation-overspray mineral rings, fallen plumeria flowers (browning), red dirt at the outer ends, and string-trimmer scuffs on the edges.
- **Path lights.**
  - *Spec:* solid cast brass or copper path lights with a hat shade, 18–22" tall (FX Luminaire PO, Unique Lighting "Pagoda", Kichler copper), 2700 K, 2–4 W LED, **shielded with downward throw only**. Brass ages to brown-black, copper to dark bronze. Never powder-coated aluminium, which pits near salt.
  - *Where:* staggered every 9–10 ft, alternating sides, set 6–10" outside the pad edge: about **9 lights** on the walk (x 75 → 148).
  - *Visible detail:* the 6" stake and a short loop of black low-voltage cable at the base where mulch has washed away. A transformer (stainless box, 12 × 10", 24" AFG) sits on the garage's east wall, or on a post behind the monstera bed.
- **Irrigation in the walk beds.** Pop-up spray heads at 12" in beds, Rain Bird 1812 or Hunter MP rotators at 6", every 10–12 ft, plus brown ½" drip tubing peeking out of the mulch at bed edges.
- **Flanking beds** (model): ti at x 96–121 (both sides), gardenia at x 123–150 (both sides), monstera at x 86–99 (both sides), plumerias at (102, 15.2), (104, 29.4), (137, 14.5), (139, 30.5), arecas at (89, 13) and (90, 32). See §12 for realism.

### 1.4 Garage pavilion (x 100–122, y −3.6–12.3: 22 × 15.9 ft, 9.5-ft ceiling)
- **Carriage door.**
  - *Spec:* 9'-0" × 8'-0" sectional overhead door clad in Western red cedar, carriage-house style (Clopay Reserve Wood or similar). The reference has a top band of **4 clear lites** separated by 3–4" stiles, and two lower bands of vertical T&G boards with a 4" mid-rail. It is a *sectional* door, so there are horizontal section joints about every 24", hidden in the rails.
  - *Hardware:* an optional pair of black strap hinges (18") per leaf and two 8" black handles at the centre stile, to sell the "carriage" look. They are decorative only.
  - *Seals:* a black rubber bottom astragal (½" visible) and white PVC stop moulding with a grey flexible flap on the jambs and head.
  - *Finish:* Sikkens Cetol SRD "Natural" or Penofin Cedar. New, it is honey-salmon with board-to-board variation (salmon, honey, chocolate streaks, a few tight knots). After a year the bottom 12–18" is greyer and splashed with red dirt; the top band under the eave stays richer.
  - *Through the lites:* the dim interior, an opener light, the white golf-cart roof.
  - *Where:* street face x 122, y −0.15…8.85.
- **Opener and controls.**
  - **Wall-mount jackshaft opener** (LiftMaster 8500W): a grey box about 12 × 9" on the right-hand jamb inside, because of the low headroom under the hip.
  - **Photo-eye safety sensors:** small black boxes 6" AFF on both inside jambs, with amber and green LEDs.
  - **Exterior keypad** (LiftMaster 877MAX, grey/black, 3 × 4"): on the right jamb trim at 60" AFG.
- **Sconces.**
  - *Spec:* black aluminium or brass **down-only cylinders**, 4½" diameter × 14" tall, 2700 K, 10–12 W, coastal-rated (Hinkley Coastal Elements, WAC "Tube Architectural", Visual Comfort). The reference shows light out of the bottom only.
  - *Mounting:* centred 7'-0" AFG (top about level with the door head), 18" outside each jamb, on white **mounting blocks**.
  - *Count:* 2, at y ≈ −1.6 and 10.3.
  - *Visible detail:* gecko droppings on the wall below, a small spider web at the cap, a slight light falloff cone on the siding at dusk.
- **Walls.** The street face beside the door reads as smooth flat panel with 5/4 × 4 trim at the jambs and corners (reference). The side walls are lap siding (§4.2). Corner boards are **white**. ⚠ The current render has black corner trims; real ones are white, with a slim dark downspout at one corner.
- **Man door.**
  - *Spec:* 3'-0" × 8'-0" fibreglass or solid-core exterior door, half-lite or solid, painted white or black, with a matte black lever at 36" and a deadbolt at 42". Hinges are 316 stainless or black. A door sweep and a 4-ft-square concrete stoop.
  - *Where:* east wall y 12.3 at x 103–106, facing the walk.
  - *Light:* one shielded sconce on the latch side at 6'-6".
  - ⚠ *Plan check:* the 7.5-ft ti bed (y 16.2–19.2) sits between this door and the walk. Add 3 stepping pads (24 × 36") from the walk to the stoop, or nobody can reach the door.
- **Windows.**
  - South face (x 100): one 4'-0" × 4'-0" window, sill 3'-6", at y 2.4–6.4, facing the main house.
  - West face (y −3.6): one 4 × 4 window at x 109–113 with cedar shutters.
  - Both are black single-hung or slider units with exterior screens.
- **Roof.**
  - *Spec:* hip at 6.6:12, 2-ft overhang, a louvered Dutch gablet at each north and south end. Gutters and downspouts (§4.5): the reference shows a slim dark downspout at the street-east corner. Use 2 downspouts, at the NE (122, 12.3) and SW (100, −3.6) corners.
  - *Accessory:* a **rain sensor** (Hunter Mini-Clik, small grey cylinder on a bracket) on the fascia near the SW corner.
- **Service entrance** (the garage is the obvious place for it).
  - *Spec:* a **KIUC 200 A meter-main combination** (Eaton or Square D), grey steel about 13 × 38". Glass meter with a white face, centred at 5'-0" AFG. A 2" grey PVC conduit drops into the ground in a short sweep. Many owners paint the box to match the wall white; the meter glass stays clear.
  - *Next to it:* a grey telecom NID about 8 × 10" (Hawaiian Telcom fibre or Spectrum coax) with a ¾" conduit.
  - *Where:* the west face (y −3.6) at x ≈ 102–104, reached from the driveway side.
- **Hose bib and outlet.**
  - *Spec:* one brass hose bib with a vacuum breaker at 18" AFG on the garage south face (x 100, y ≈ 10). One GFCI weather-resistant outlet with a grey "in-use" bubble cover at 18" AFG nearby.
- **Interior** (seen through the lites and the man door).
  - *Surfaces:* painted drywall walls and a flat 9.5-ft ceiling in white. **Epoxy flake floor**, light grey with black/white flake, satin.
  - *Lighting:* two 4-ft LED wraparound fixtures.
  - *Outlets:* 4 duplex at 42" AFF (above bench height).
  - *EV charger:* Tesla Wall Connector (white glass, 15 × 6") on the east wall at 48".
  - *Golf cart:* white or oyster Club Car Onward 2-seat at (113, 4.35), plugged in with a black cord to the wall outlet.
  - *Storage:* white melamine cabinets along the south wall. A **surfboard rack** on the west wall with a 9'-0" longboard and a 6'-2" shortboard at 5–7 ft AFF. Two boogie boards. Two striped Tommy Bahama-style backpack beach chairs. A blue or white cooler, a beach umbrella, two golf bags on a stand, two beach-cruiser bikes on ceiling hooks.
  - *Kauaʻi-specific:* **hurricane plywood panels**, ½" ply stencilled with window numbers ("W-4 BED 3"), leaning against the west wall.
  - *Irrigation controller:* Hunter Hydrawise or Rain Bird ESP-TM2 in a grey 9 × 10" box at 60" beside the man door.
  - *Optional battery:* Tesla Powerwall 3 (white, 43 × 24 × 7.6") on the north wall at 12" AFF to the bottom, if PV is fitted.

---

## 2. ʻOhana (x 97.54–122, y 32.3–48.13: 352 sf; room 16 × 15.8, bath 5.7 × 13.5)

### 2.1 Exterior
- **Street face (x 122): louvered shutter pairs.**
  - *Spec:* **two pairs of white louvered shutters**, closed for bath privacy (reference). Each pair is about 4'-9" wide × 7'-4" tall, sill 12" AFG. Frames are 1⅜–1¾" thick; stiles 2½"; rails 3½" top and 5" bottom; 2½" louvres. They can be plantation-style operable (side-hinged on black or 316 strap hinges with a centre slide bolt), or fixed Bahama-style on aluminium. Behind them is an obscure-glass casement or a **Breezway Altair glass louvre window** (a very Hawaiʻi product).
  - *Finish:* white semi-gloss.
  - *Real look:* louvres show a dark interior gap, slight sag on one leaf, and mildew grey in the lower louvre recesses.
  - *Where:* y 33.9–38.7 and 41.7–46.5.
- **West face (y 32.3, facing the walk).**
  - Two shuttered windows, 2'-1" × 6'-6", sill 18" (x 101.3–103.4 and 110.8–112.9).
  - One high bath window, 2'-9" × 3'-6", sill 54", with obscure glass (x 119.0–121.8).
  - A downspout at the street-west corner (122, 32.3), as in the reference.
- **East face (y 48.15).**
  - Two shuttered windows (x 101.1–103.2 and 111.2–113.3).
  - An **entry door** 4'-3" (a 3'-0" door plus a 1'-3" fixed sidelite, or a 3'-6" door) at x 117.3–121.6.
  - A 4 × 5 ft step-stone stoop.
  - A coir mat with **2 pairs of slippers**.
  - One shielded sconce on the latch side at 6'-6".
  - A ductless condenser on a wall bracket or 3-ft pad at about (109, 49.8): Mitsubishi MUZ-GL class, 31 × 22 × 11", warm white, with a white line-hide channel up to the eave.
- **South face (x 100.22).**
  - *Spec:* a **12'-2" × 9'-0" slider**, 3 or 4 panels, black, with the 3-high SDL grid of the primary slider. A retractable screen housing (Phantom or Centor, black, 3 × 3") at the head.
- **ʻOhana lānai.**
  - *Spec:* two 8 × 8 rough-sawn cedar posts at (97.54, 32.3) and (97.54, 48.13). An 8 × 12 rough-sawn cedar beam spanning 15.8 ft with Outdoor Accents connectors. A T&G soffit ceiling with 2 wet-rated 3" downlights.
  - ⚠ *Plan check:* the lānai is only 2.66 ft deep, which is an eave, not a lānai. The two 2.8-ft outdoor chairs at (98.85, 35.8 / 44.1) do not fit under it. Real fix: deepen it to 6–8 ft (x 92–100), or put the chairs on a paver pad outside the posts.
- **Roof.** Hip 6.6:12 with louvered gablets at the north (street) and south ends, 2-ft overhang, gutters with 2 downspouts (the NW one is visible in the reference).

### 2.2 Interior
- **Shell.** White oak floor, white board-and-batten walls, white T&G vault (as §8), with a 9-ft flat drywall ceiling over the bath.
- **Bed.**
  - *Spec:* king (76 × 80) on an oak or cane-headboard frame, at (108.63, 36.04), head against the west wall y 32.3.
  - *Linens:* white percale duvet, 2 Euro shams 26", 2 king shams, a lumbar pillow in sand stripe, an oatmeal waffle throw folded at the foot.
  - *Nightstands:* oak, 24–26" tall, at (102.98, 33.3) and (114.28, 33.3), each with a 26" ceramic lamp.
  - ⚠ The west-wall windows (sill 18") land behind the south nightstand (window x 101.3–103.4) and behind the headboard (window x 110.8–112.9). Real fix: re-centre the bed at x ≈ 107.1 in the 7'-5" pier between the windows, and use black swing-arm wall sconces plus 12" floating oak shelves instead of nightstands.
- **Wet bar instead of a kitchen** (Kauaʻi guest-house rule).
  - *Spec:* a 4'-6" oak base cabinet, quartz top at 36", a 15" bar sink with a matte black faucet, a **24" under-counter fridge**, one floating oak shelf at 54" with 4 mugs and 2 glasses, a Nespresso machine and an electric kettle on the counter. **No range or cooktop.**
  - *Where:* east wall y 48.15 between x 113.3 and 117.3.
- **Wardrobe.** None in the furniture list. Add a 4-ft open hanging rail with an oak shelf at 66" on the north part of the east wall, or a 4 × 2 ft wardrobe. Add a teak luggage rack at the foot of the bed.
- **Ductless head.**
  - *Spec:* Mitsubishi MSZ-GL class, white, 31 × 12 × 9", with a white condensate line inside the wall.
  - *Where:* east wall above the windows, about 8'-6" AFF to the top, centred x ≈ 106.5.
- **Other room items.**
  - Fan: 52" black airfoil at (108.2, 40.17), with the downrod sized so the blades sit at about 9 ft.
  - Smoke/CO alarm on the ceiling at about (108, 44).
  - Outlets: 5 at 16" AFF.
  - Switches: a 3-gang at 48" inside the entry door (fan, downlights, bath), plus a wall fan control.
  - Optional 50" TV on the bed-facing wall.
- **Bath door.** 3'-4" opening at x 116.26, y 39.1–42.5. Use a **sliding barn door**: white-oak plank or painted white, on a black flat-bar track at 8'-3" with black rollers.
- **Bath.**
  - Vanity: 5-ft single, oak shaker, at (119.07, 33.13) on wall y 32.3.
  - ⚠ The high window (sill 54") is right behind the sink, so there is room for only an 18"-tall mirror. Real fix: hang a 24" round black-framed mirror on a black ceiling rod in front of the glass, or move the window.
  - **Shower:** ⚠ none in the furniture list. A real ʻohana bath must have one. Spec: a 3'-0" × 5'-0" walk-in at x 119–122, y 38.5–43.5, behind the street-face louvres, with a ⅜" low-iron glass panel, matte black fittings, a pebble or 2" hex floor, and a linear drain.
  - Toilet at (120.37, 44.08).
  - Exhaust fan: 8" square white Panasonic WhisperCeiling grille.
  - Accessories: towel bar at 48", toilet-paper holder at 26", a 16" towel ring beside the vanity.

---

## 3. Entry courtyard, covered entry and walk

### 3.1 Courtyard (x 56.09–68.61, y 16.09–28.52: 12.5 × 12.4 ft, open to sky)
- **Floor.** The same slab pads as the walk, laid as a tighter field (1" sand joints) across the whole walk width. Planting beds sit at the edges.
- **Paved landings at the bedroom sliders.**
  - ⚠ *Plan check:* the model's groundcover beds (y 16.3–19.3 and 25.3–28.2) and the arecas at (60, 16.8) and (66, 28.2) run right across both bedroom sliders (x 57.5–65.5). Code requires a landing outside an exterior door, and nobody plants against a slider.
  - *Real fix:* a **4-ft-deep paved landing** outside each slider (pads at 1" joints). Keep groundcover only at x 66–68.6 and at the corners. Move the two arecas to the corners at (67.5, 17) and (67.5, 27.5).
- **Planting.** Dwarf mondo or lauaʻe fern groundcover. One feature plant per corner (e.g., a 6-ft *Pritchardia* loulu palm or red ti cluster). 2–3 bird's-nest ferns.
- **Feature (common, optional).** A 24–30" basalt or lava-stone bubbling bowl on a pebble bed, with a small brass jet.
- **Lighting.** 2 shielded brass step or path lights. The entry downlights spill into the courtyard. No uplights.
- **Rain chains.** The north-wing and south-wing hips meet the main hip in **valleys that dump water at the two inside corners by the entry posts** (≈ 56, 16 and 56, 28.5). The real detail: a short gutter at each corner with a **black or copper cup rain chain** to a 24"-diameter basin of 1–2" black Mexican beach pebbles over a drain grate.
- **Hose bib.** One, at 18" AFG on the bed-3 north notch wall (x 68.43, y ≈ 12.5), with a 50-ft green rubber hose coiled in a woven or galvanised hose pot.

### 3.2 Covered entry (x 48.22–56.09, y 16.09–28.52)
- **Posts and beam.**
  - *Spec:* two **10 × 10 rough-sawn Western red cedar posts** at (56.09, 16.09) and (56.09, 28.52). An **8 × 14 rough-sawn cedar beam** over the 12.4-ft span.
  - *Base:* each post stands on a black **standoff base** with a 1" visible gap above the stone (Simpson CBSQ / APB style), with a ¼" chamfer at the post foot.
  - *Head:* a black knife plate or ECCQ cap, with **2–4 visible ¾" hex bolt heads** and black square washers on each face at the beam.
  - *Texture:* band-saw or circular-saw texture, seasoning checks ¼–⅜" wide running up the post faces, one or two loose knots.
- **Front clerestory (reference).** Above the beam the reference shows a cedar-framed glass clerestory or trellis under the gablet. Model it as a 2 × 6 cedar frame with clear glass and a black head flashing.
- **Ceiling.** 1 × 6 T&G V-groove soffit, painted white, sloped with the hip.
  - Lights: 2 wet-rated 3" round downlights, 2700 K, plus an optional black metal lantern (24" tall, 12" square) hung from a short chain with its bottom at 7'-6" AFF over the doormat.
  - One Wi-Fi access point disc (white, 7") beside a downlight, a common real-world addition.
- **Floor.** Coral stone, 24 × 24 or 16 × 32 honed, 3/16" sand-coloured grout, sloped ⅛"/ft toward the courtyard. A **1"-wide stainless slot drain** across the threshold line at x ≈ 56.
- **Front door: pivot assembly in the 9'-1" opening on wall x 48.22, y 17.74–26.83.**
  - *Spec:* a black thermally-broken aluminium or steel-look pivot door, about 4'-6" × 9'-0", with a 2-wide × 4-high SDL grid (reference). Two fixed sidelites of about 2'-3". All clear tempered glass with bugs.
  - *Pivot:* FritsJurgens-type or a floor closer. A small **stainless cover plate** (3 × 10") is visible in the stone at the pivot point, about 9" in from the jamb.
  - *Hardware:* a **black ladder pull 48–60" long**, centred about 42" AFF on both faces. A smart deadbolt (Yale or Schlage, black keypad) at 42". A black weather sweep. A **flush ½" bronze-anodised saddle threshold** at the oak-to-stone transition.
- **Doorbell.** Video doorbell (Ring or Nest, black) at 48" on the latch-side jamb trim.
- **Hall doors onto the entry.**
  - ⚠ *Plan check:* the two "cased" openings from the west hall (y 16.09, x 50.2–52.3) and the east hall (y 28.52, x 50.2–52.3) open onto this **outdoor** entry, so they must be exterior doors.
  - *Real spec:* 3'-0" × 8'-0" black full-lite aluminium doors, tempered, weather-stripped, with thresholds, retractable screens and black levers.
- **Lived-in props.**
  - A **teak shoe bench** 40 × 14 × 18" against the west hall wall, with 3–4 pairs of slippers on the floor and one pair crooked.
  - A coir doormat 2'-6" × 4'-0" (natural, slightly flattened in the centre).
  - **2 large planters** flanking the door: 24"-diameter white or sand glazed ceramic or fibreglass, holding a *Strelitzia nicolai* (6 ft) or a kentia palm.
  - A beach umbrella or golf umbrella in a basket.
  - A woven lauhala tray for keys inside the door (§8).

---

## 4. Exterior walls, roofs, eaves, windows and doors (all elevations)

### 4.1 Base, slab and grade line (this is where CG looks most fake)
- **Exposed slab and skirt.** The concrete slab edge shows **6–8" above finished grade**: smooth form-finish, painted to match the white or left a light grey, with a crisp ¾" chamfer. A **1 × 8 water-table / skirt board** (Hardie trim, white) sits on it with a **Z-flashing** above, and the lap siding starts from there. Wood siding never touches soil (6" clearance) or paving (2").
- **Drip / gravel strip.** An 18–24"-wide band of **¾" grey river gravel or black cinder** sits under every eave that has no gutter. Where gutters exist, it still follows the foundation as a termite-inspection and splash strip, edged with a 4" black steel or aluminium edging or a tan concrete mow strip. ⚠ The current render runs lawn straight into the siding.
- **Red-dirt splash.** On the bottom 6–12" of siding and skirt board wherever bare soil or mulch meets the wall, and heaviest under roof drips: a fine orange-brown speckle gradient.
- **Termite stations.** As §0.2.
- **Crawl / weep.** Slab on grade has no crawl vents. Real buildings do have **weep screed**, a ¼" gap line at the bottom of the trim.

### 4.2 Lap siding
- *Spec:* **James Hardie HardiePlank Lap, Smooth**. In Hawaiʻi fibre cement is chosen because termites can't eat it. Factory ColorPlus "Arctic White", or primed and site-painted SW 7006.
- *Exposure:* 7¼" plank at **6" exposure**. The reference reads 5–6". From the water table (about 8" above floor) to the frieze under the soffit (about 9'-4" AFF), that gives about **17 courses** on the main house.
- *Butt joints:* planks are 12 ft long, so a 60-ft wall shows **4–5 staggered vertical butt joints per course band**. They are faint hairlines with a slight caulk sheen, offset at least 2 stud bays between courses. CG lap siding never has them; real walls always do.
- *Shadow line:* each course casts a 3/16–¼" shadow under the drip edge. In raking north light at dawn or dusk the courses read strongly. At high summer sun they almost vanish.
- *Fasteners:* blind-nailed (invisible). A few nail-head dimples show through paint near the corners.
- *Waviness:* ±1/16" plane waviness, visible as gentle highlight wobble along long walls at grazing view.
- *Caulk:* at every trim junction, a ¼" bead of white elastomeric with a slight sheen difference.

### 4.3 Trim
- **Corner boards.** 5/4 × 4 (3½") at all outside corners, white. Inside corners get 5/4 × 2 or 2 × 2.
- **Frieze board.** 1 × 8 at the top of every wall under the soffit, white.
- **Window and door casing.** 5/4 × 4 flat (3½") on all sides, with a sloped sill nose and a **head drip cap / Z-flashing** (aluminium, white, about ⅜" projection) above every head. The reference shows thin trim, which this matches.
- **Mounting blocks.** This is the most-missed real detail. **Every sconce, outlet, hose bib, dryer vent, meter and camera on the lap siding sits on a flat white PVC mounting block** (Mid-America split block), 7 × 7" for fixtures and 5 × 7" for receptacles, so it doesn't sit on the angled laps.

### 4.4 Roofs (standing seam with Dutch-hip louvered gablets)
- **Panels.**
  - *Spec:* 24-gauge steel, **16" panel width**, 1–1½" mechanically seamed or snap-lock ribs, with **2 pencil striations** in each pan.
  - *Finish:* Kynar 500 painted "Ash Gray" / "Dove Gray" / "Slate Gray". The reference reads as a cool mid-grey matte, which is painted, not mill finish. The Kukuiʻula DRB favours low-gloss finishes to limit glare toward the golf course. Bare Galvalume is the alternative and looks brighter and more specular when new.
- **Seam direction.** ⚠ Every panel runs **straight down the slope, perpendicular to the eave**, on every face. On hip faces, panels are cut on the diagonal where they meet the hip line. The brochure renders draw horizontal "courses" on the hip faces and diagonal seams on the fronts, which is wrong in real life.
- **Panel length.** Main hip from eave to ridge is about 19 ft along the slope. That is one length, with no end laps.
- **Oil-canning.** Gentle waviness in the flat pans, about 1–3 mm. It shows as wobbly reflections of the sky and a non-uniform sheen, especially on the big south and west faces. The striations reduce it but don't remove it. **This is the #1 standing-seam realism cue.**
- **Hips and ridges.** A 10"-wide vented hip cap with a Z-closure on each side and visible pop rivets or stainless pancake screws every 12–18" on the cap flanges. Hip lines are **the same colour as the roof** (reference). ⚠ The current render outlines hips in charcoal.
- **Eave.** Panels overhang a hemmed drip edge or cleat by ½–¾", showing the hem as a thin bright line. Seam ends are hemmed or folded over.
- **Valleys.**
  - *Spec:* open W-valleys, 16–24" wide, same colour, with a 1–2" gap where the panels stop either side.
  - *Where:* the north and south wings and the primary wing meet the main hip at about (40–56, 0–16), (48–56, 28.5–44) and the gallery shed.
  - *Real look:* palm fronds, plumeria leaves and dry bougainvillea bracts collect in the valleys and at gutter outlets.
- **Dutch-hip gablets.**
  - *Spec:* vertical triangular gable faces near the top of each hip end, infilled with **fixed horizontal louvres**: 1 × 4 blades, about 3" on centre at 45°, painted white or roof-matched grey. Behind them is **black or stainless insect / bird screen**, so the gaps read nearly black, not see-through. A rake flashing caps each gablet, in roof colour.
  - *Size:* ⚠ In the reference, gablets are about **50–60% of the roof width** (garage: a triangle about 12 ft wide × 3–3.5 ft tall). Check that the `gablet` parameter delivers that.
  - *Lived-in detail:* a **myna-bird nest** (dry grass poking out) in one louvre bay, and a few streaks below.
- **Penetrations.** Place them on the slopes facing away from the street and pool where possible, as real designers do.
  - *Plumbing vents:* about 5 for the main house (bath 2, bath 3, primary bath, powder/laundry, kitchen/pantry) and 1 for the ʻohana. 2–3" pipes painted roof colour, with **grey EPDM Dektite boots**. Put them on the east-facing slope of the south wing and the west-facing slope of the north wing.
  - *Kitchen hood:* a 10" round roof jack with a cap on the main roof's west slope near (44, 4).
  - *Bath exhaust and dryer:* through the soffit or wall (§4.5 and §11), not the roof.
- **PV (very likely on a real Kauaʻi spec home, but optional because the renders show none).**
  - *Spec:* about **20–24 all-black 400–430 W modules** (about 68 × 45" each), flush-mounted 4–6" off the roof on **S-5! seam clamps** with no penetrations, black-framed with dark-blue/black cells.
  - *Where:* concealed slopes only, the west-facing slope of the north wing (x 42–84, y −2…7). Never on the courtyard or the pool-facing hero slopes.
  - *Look:* modules reflect the sky as a dark blue-grey mirror with fine cell grid lines. Show a little dust and bird droppings.
- **Solar thermal (if no HPWH variance).** One 4 × 10 ft flat-plate collector, about 3" thick, with an aluminium frame and copper lines in roof-colour paint, on the south-facing slope of the primary wing at (5–15, 32–40).

### 4.5 Eaves, soffits, fascia, gutters
- **Overhang.** 2'-6" on the main hip, 2'-0" on the wings, ʻohana and garage. The fascia bottom is about **8'-5" AFF** (10-ft plate minus overhang × pitch).
- **Fascia.** 2 × 8 (7¼") wrapped in **roof-colour metal**. The reference reads as a slim same-colour grey band.
- **Soffit.**
  - *Spec:* 1 × 6 T&G V-groove, painted white, running perpendicular to the wall, with a 1 × 2 cove at the frieze.
  - *Ventilation:* a continuous 2" white perforated aluminium strip vent near the fascia, or 2" round louvre plugs at 24" on centre.
  - *Reference note:* the small evenly spaced features under the eaves (about 24" on centre) on the garage and ʻohana are either exposed painted rafter tails or soffit vents. Real plantation-modern uses either. Pick one and apply it everywhere.
  - *Real look:* soffits are the **most mildewed surface** on a Kauaʻi house. Grey-green speckle shows in the shaded north and east soffits and corners, plus spider webs at the inside corners and fascia returns.
- **Gutters.**
  - *What is typical here:* older dry-side Poʻipū homes often skip gutters (deep eaves plus a gravel drip strip). **New Kukuiʻula homes usually have them**, because the drainage plans and DRB route roof water to drywells. The reference renders show them: a slim dark gutter line with corner downspouts on the ʻohana and garage.
  - *Spec:* **6" seamless K-style or box gutter in "Charcoal" or roof-matched aluminium**, fixed with hidden hangers at 24".
  - *Downspouts:* **3 × 4" rectangular**, same colour, with 2 straps per run (black screws). They end in a **4" black PVC drain inlet or a green NDS pop-up emitter** out in the lawn. A splash block reads cheap; don't use one.
  - *Counts:* main house about 10 downspouts (all outside corners plus mid-run on the 60-ft walls), ʻohana 2, garage 2.
  - *Rain chains:* 2 at the courtyard valleys (§3.1), plus optionally 1 at the lānai NW corner.
  - *Real look:* a few seed pods or leaves at the gutter outlets, a hairline dark drip stain under the outlets where seams weep, and brown water streaks down the downspout straps.

### 4.6 Windows (count from the plan)
- **Frames.**
  - *Spec:* black fibreglass or aluminium (e.g., Milgard Ultra or Marvin Elevate fibreglass, or Western Window Systems aluminium). **Black inside and out.** Frame face about 2½–3" outside. Dual-pane low-E: the glass reads slightly grey-green-blue in reflection, with **faint double reflections** from the two panes.
- **Tall single-hungs** (sill 18", head 8'-0", 2'-1" to 2'-9" wide × 6'-6").
  - *Count:* 16. West wall: 4 (x 20.0, 34.4, 55.7, 64.9). Bed-3 north notch: 1. Lānai side of the primary: 2 (y 28.52 at x 1.2, 12.9). Primary east: 2 (y 44.39 at x 1.8, 12.2). Bed-2 east: 2. Bed-2 north notch: 1. ʻOhana: 4. The garage has one more, a 4 × 4 single-hung on its west face.
  - *Operation:* **one-over-one single-hung** with the meeting rail at about 50–55% of height (reference).
  - *Screen:* a **half-height exterior screen on the lower sash** (charcoal fibreglass 18 × 16 mesh in a black frame). The lower half reads **noticeably greyer and less reflective** than the upper. This is a strong cue.
  - *Hardware:* black sash lock at the meeting rail, two lift handles.
  - *Glass:* tempered with a bug (bottom at 18"). Some builders temper these anyway.
- **High windows** (sill 4'-0" to 4'-6", head 8'-0", about 2'-0" × 3'-6" to 4'-0").
  - *Count:* 10 in the main house: pantry 1, bath 3 ×2, bath 2 ×2, primary bath 1, laundry 1, powder 1, lānai west wall ×2 (sill 3'-6", head 7'-6"). Plus 1 in the ʻohana bath.
  - *Spec:* awning or casement, black crank handle folded flat. **Obscure glass in all baths and the powder** (satin-etch or rain pattern, which reads milky white from outside and glows at night). Interior screens.
- **Louvred openings** (garden showers 2 and 3 north walls x 84.78, 4'-2" × 7'-2", sill 1'-0"; ʻohana street face ×2).
  - *Spec:* white fixed louvre panels, or **Breezway Altair louvre windows** (white aluminium frame with 4–6" clear or frosted glass blades). Screen behind.
- **Shutters.** On the 16 tall windows plus the garage west window.
  - *Spec:* pairs of **side-hinged louvered Western red cedar shutters**. Each leaf is half the window width plus ¼" overlap, at full casing height: for example 2 × 17" × 78" on the 2'-9" units, 2 × 13" × 78" on the 2'-1" units. That is **34 leaves total** (17 windows × 2).
  - *Construction:* 1⅜" thick; stiles 2¼"; top rail 3½"; bottom rail 5"; one mid-rail at the meeting-rail height; fixed 2" louvres at 45°.
  - *Hardware:* black-coated 316 **strap hinges** (2 per leaf, 10–12" long) on pintles in the casing. **S-shaped "shutter dogs"** (black, 4–5") screwed through the siding at the lower outer corner of each open leaf, about 30–36" AFG. Leaves stand ¼–½" off the wall, giving a crisp shadow line.
  - ⚠ The reference reads like one narrow louvered leaf beside each window. Real operable shutters come in pairs sized to cover the opening. If the design really is single leaves, they are decorative and should be fixed.
  - *Real look:* every leaf a different tone (salmon to cinnamon to grey). Sun-side tops and louvre top-edges silvering. The bottom rail dark and water-marked. Fine dust and mildew in the louvre recesses. One leaf very slightly out of plumb.

### 4.7 Exterior doors and sliders
- **Lānai pocket multi-slide** (wall x 18.65, y 5.26–23.43: 18'-2" × 9'-6").
  - *Spec:* **Western Window Systems Series 600 multi-slide**, black, 4 or 5 panels of about 3'-8"–4'-6" each, **pocketing** into the 16½"-thick wall.
  - *Sill:* a **flush sill** with 3–4 stainless or bronze track lines visible in the floor at the oak-to-coral junction, plus weep slots on the lānai side.
  - *Panel hardware:* 2½" interlocks; flush finger pulls on the pocket edges; a black D-pull or flush pull on the lead panel at 38–40" AFF.
  - *Pocket jamb:* a dark slot with **brush seals**.
  - *Screen:* a **motorised retractable screen** (Phantom Executive) recessed in the header as a 1¼" slot. Over a full width the mesh looks like a faint grey veil when deployed.
- **Primary slider** (x 0, y 30.4–42.6: 12'-2" × 9'-0").
  - *Spec:* 4 panels, black, each with a **3-high grid** of equal lites (reference). Raised 1" sill track. A black handle with a thumb-latch lock at 40".
  - *Light:* **2 down-only black cylinder sconces** flanking it at y ≈ 29.4 and 43.6, centred 7'-0" AFG (reference).
- **Bedroom 3 slider** (y 16.09, x 57.5–65.5: 8'-0" × 9'-0"). 2 panels, sliding screen, opening onto the courtyard. **Bedroom 2 slider** (y 28.52): the same.
- **Gallery slider** (y 32.17, x 38.65–46.7: 8'-1"). 2 panels, onto the laundry side garden. One sconce.
- **Bath 3 and bath 2 sliders to the garden showers** (x 78.48, 6'-0"). 2 panels. Clear or reeded glass. A **reeded or frosted** finish is more realistic for privacy.
- **Primary bath slider to garden shower 1** (x 31.91, y 32.8–41.0: 8'-2"). 2 panels, clear, with a roller shade inside.
- **Laundry door** (wall x 48.5, y 38.5–40.5: 2'-0").
  - ⚠ A 24" exterior door is narrower than real practice. Use 2'-8" minimum: a half-lite white or black door with a black lever.
- **Door hardware throughout.** Matte black (Emtek or Baldwin), lever centre at 36" AFF, deadbolt at 42". Tempered bugs on all glass.
- **Pool door alarms.** On the lānai pocket door and the primary slider: a **white Poolguard-type alarm box** (about 3 × 6") on the interior jamb at **54" AFF** with a push-to-pass button. Exterior side: optional MagnaLatch-style gates in the side yards (§6.8).

### 4.8 Exterior electrical, plumbing and other wall-mounted items (all on mounting blocks)
- **GFCI weather-resistant outlets with in-use bubble covers.**
  - *Spec:* grey or white Intermatic / TayMac covers, 18" AFG.
  - *Count:* entry 1, courtyard 1, west yard 2, east side garden 1, lānai 3 (§7), pool equipment 1, garage 1, ʻohana 1. **About 11.**
- **Hose bibs.**
  - *Spec:* brass, ¾", with a vacuum breaker, 18" AFG.
  - *Count:* 6:
    - west wall at about (33, 0.17) beside the condensers, with a **wall-mounted hose reel** (Suncast or Liberty Garden, green or brown)
    - courtyard (§3.1)
    - side garden at about (44, 44.39)
    - pool / lānai on the lānai west wall outside at about (2.5, 3.3)
    - garage
    - ʻohana east wall
- **Dryer vent.** A 4" louvred white hood at 18" AFG on the laundry wall (y 44.39, x ≈ 53), with **visible lint fuzz** and a grey film on the siding above.
- **Bath and powder exhaust terminations.** 4" soffit vents with damper flaps (white) near each bath, or wall caps under the eaves.
- **Range-hood make-up.** None visible.
- **Security cameras** (common lived-in addition). 4 small white or black bullet or dome cameras (UniFi or Ring) under the eave corners at about 8 ft: NE garage, entry, SW lānai, SE primary.
- **Hurricane plywood anchors** (subtle, optional). ¼" stainless threaded sleeves, flush in the casing at 12" on centre around a few windows, for owners who pre-cut plywood (the panels in the garage, §1.4).

### 4.9 Elevation checklist
- **North / street (x 84.78, the courtyard mouth, the ʻohana and garage street faces).** Louvred garden-shower walls, the bed-3 and bed-2 notch windows, the open courtyard with rain chains, the garage door with sconces and keypad, the ʻohana closed louvre shutters, 2 downspouts per pavilion, path lights, house numbers. Mostly in **open shade** (§0.1).
- **West (y 0.17 and the garage at y −3.6).** 7 main windows (4 shuttered), the lānai west wall with 2 windows, the meter-main and NID on the garage, the hose reel, 2 AC condensers, the pool equipment enclosure (§5), the gravel strip, the kitchen hood roof jack above, PV on the north-wing west slope.
- **South / pool (x 0, x 1.83).** The primary 12-ft gridded slider with 2 sconces, the lānai beam and 2 posts, the outdoor TV visible deep inside, the main hip's south gablet, downspouts at the outer corners.
- **East (y 44.39, the ʻohana at y 48.15).** 2 shuttered primary windows, the primary bath high window, garden shower 1's **7-ft horizontal cedar slat wall** (1 × 4 slats with ½" gaps) and gate, the open side garden with the gallery slider and **clothesline**, the laundry door and dryer vent, the bed-2 and bath-2 windows, the garden shower 2 wall.

---

## 5. Side yards and utilities

- **West side yard (y −6…0.17, about 6 ft clear).**
  - *Path:* a stepping-pad path (24 × 36" pads at 30" on centre) from the driveway to the pool, x 100 → −10, so the pool tech and the yard crew can get through.
  - *Ground:* gravel strip along the house, lauaʻe fern or mondo between the pads, the clusia/naupaka hedge on the lot line.
  - *Gate:* a 4-ft black aluminium picket gate with a **MagnaLatch** (latch 54" or higher) at about x 95 where the side yard meets the front. It is part of the pool barrier.
- **AC condensers (main house).**
  - *Spec:* ducted central heat-pump AC, typically a 3-ton plus a 2-ton unit (Carrier, Trane, or a Mitsubishi multi). Each about 30 × 30 × 33" or 37 × 37 × 13" (side-discharge). Warm grey or white. **Coastal "blue fin" coil coating**, so the fins look faintly blue-green.
  - *Mounting:* each on a 3 × 3 ft concrete or composite pad 3" above grade.
  - *Services:* an **AC disconnect box** (grey, 6 × 10") at 48" on the wall beside each unit. White **line-hide channel** (Fortress / SpeediChannel) up to the soffit. A ¾" white PVC condensate line dripping onto the gravel, with a green algae stain.
  - *Where:* west wall between the great-room windows, x 24–32, y −4.5…−1.5, screened by the areca at (30, −5) plus a 5-ft horizontal cedar slat screen.
  - *Real look:* leaves stuck to the fan grille top, red dirt at the pad edges.
- **Pool equipment pad.**
  - *Spec:* a concrete pad about **12 × 4½ ft** at x 4–16, y −5.5…−1, in the west side yard beside the lānai's outdoor-kitchen wall. That keeps it about 25–35 ft of pipe from the pool and away from bedrooms. A **5-ft cedar slat screen** matching the garden showers runs on its south and east faces, with a slat gate. Move the model's monstera bed (x −2…16, y −3.5…−1) to wrap the south end of the screen (x −3…4), so the back-lawn view sees foliage, not equipment. On the pad:
    - **2 variable-speed pumps** (Pentair IntelliFlo3 VSF, one for the pool and one for the vanishing-edge return), about 30 × 12 × 14", black and grey
    - a **cartridge filter** (Pentair Clean & Clear Plus 420: grey tank, 22" diameter × 46" tall)
    - a **heat-pump pool heater** (Pentair UltraTemp 140, 35" cube, almond/grey, top-discharge fan)
    - a **propane spa heater** (MasterTemp 400, almond, 30 × 31 × 29")
    - a **salt cell** (IntelliChlor IC40 in a clear-grey housing)
    - an **IntelliCenter load centre** (grey, 24 × 36") on a 4 × 4 post or the screen
    - 2–3 Jandy or Pentair 3-way valves with black handles
    - **white Schedule 40 PVC piping, 2–2½"**, with unions, labelled with Sharpie ("SPA RTN", "EDGE")
  - *Lived-in look:* a 5-gal bucket, a test kit, a spare cartridge in a bag, a coiled cleaner hose.
- **Propane.** Kauaʻi has no utility natural gas. For the spa heater and the outdoor grill: either **2 × 100-lb grey cylinders** chained to the screen inside the enclosure, or a **buried 250-gal tank** shown only as an 18" grey or green dome lid in the side-yard lawn at about (−10, −4), at least 10 ft from openings.
- **Water heater.** A **heat-pump water heater** (Rheem ProTerra 65-gal, white cylinder 22" diameter × 63") in the **"wh" storage closet** (x 31.91–35.7, y 28.52–32.17), behind a **louvred door** (the HPWH needs the air) or a door with a transfer grille.
- **House water entry.**
  - *Spec:* a copper or PEX riser with a **brass PRV, a ball-valve shutoff and a hose bib**, under a small white cover box or on the wall at 18–30".
  - *Where:* west wall near bath 3, about (77, 0.17).
- **Irrigation.**
  - **Backflow preventer:** a brass PVB (Febco 765, 1") 12" above the highest head, about 30" tall overall, near the front at about (146, −4) behind the gardenias, in a **green insulated bag** or a fake-rock cover.
  - **Valve boxes:** 6–8 rectangular green 10 × 15" lids (Carson), grouped in 3 manifolds: front at (145, 0), west yard at (40, −5), back lawn at (−14, −5). Lids sit at grade, slightly proud, often with mulch on top.
  - **Non-potable water:** if the lot is on Kukuiʻula's non-potable irrigation system, **heads and lids are purple** (the US convention for non-potable water). Verify before modelling.
- **Drainage.**
  - **Area drains:** NDS 9" square atrium or flat grates, green or black, in the lawn low spots: 4 in the back lawn, 2 in the side yards, 1 in the courtyard as a brass or stone-insert grate.
  - **Drywell lids:** 1–2 round 24" cast-iron or concrete lids stamped DRAIN, in the back lawn at about (−10, 20) and the side yard.
  - **Downspout ends:** green 4" round **pop-up emitters** in the lawn, 6–10 ft from the house.
  - **Sewer cleanouts:** a white or black 4" two-way cleanout cap at grade near each wing (about (86, 18), (40, 46), (0, −2)).
- **Trash and recycling.**
  - *Spec:* **two 96-gal wheeled carts** (colour per Kauaʻi County / hauler) in a **3-sided cedar slat enclosure**, 5 × 3 × 4'-6", with an open top.
  - *Where:* beside the garage south wall at about (97, −2). Carts get rolled to the street weekly; red-dirt wheel tracks to it are optional.
- **Side garden (east, x 37.83–48.5, y 32.17–44.39).**
  - *Floor:* coral stone pads at 2" gravel joints. Lauaʻe fern under a single plumeria or *Pritchardia*.
  - *Clothesline:* a **retractable 5-line clothesline** (Breezecatcher or Hills) on the laundry wall x 48.5 at 6'-0" AFG, extending to a 4 × 4 post at x ≈ 40. On a lived-in day it holds 2–3 beach towels and a rash guard.
  - *Other:* the gallery slider sconce, the side-garden hose bib.
- **East side yard (y 44.39…51.5, about 7 ft).** Stepping pads, gravel strip, hedge, a black welded-wire barrier fence inside the hedge, and a MagnaLatch gate at about x 88.

---

## 6. Back lawn, pool, spa and coral-stone retaining wall

### 6.1 Lawn (x −17…0 between the pool and house; around the pool and to the hedges)
- **Turf.**
  - *Spec:* **zoysia** ("Zeon" or "El Toro", fine-bladed, dense) or **seashore paspalum** (what Kukuiʻula's golf course uses; very salt-tolerant, bright). Mowed at 1–1¼" with a reel mower, so there are **visible alternating stripes about 21–26" wide**, light and dark depending on the view direction.
  - *Albedo:* 0.10–0.13. Blades 2–3 mm wide, with variation in height, colour and tip browning.
- **Real imperfections.**
  - A slightly **browner, thinner band 12–24" wide along the pool coping** (splash plus salt-chlorinated water).
  - **Greener rings** around sprinkler heads.
  - A worn path from the lānai to the loungers.
  - A few weeds: nutsedge spikes, a dandelion-like *Sonchus*, spurge.
  - **Mushrooms after rain** (a small cluster).
  - Scratch marks and a feather (chickens, §12).
- **Sprinkler heads.** Rain Bird 1804 or Hunter Pro-Spray PRS40 bodies with **MP Rotator** nozzles. Caps are 2¼" black (or purple). Every **12–15 ft around the lawn edges** and at the mid-lawn on large areas.
  - *Count:* about **14** in the back lawn (perimeter about 120 ft), 4–6 around the pool, about **20** in the front lawns.
  - *Look:* each head sits at grade with a 1" bare ring.
- **Edges.** A tan mow curb against beds, a gravel strip against the house, and a turf-to-coping joint at the pool (a ¼" gap with grass hanging over).

### 6.2 Pool (x −31…−17, y 1…31: 14 × 30 ft; long axis east–west; vanishing edge along the south side x −31)
- **Coping.**
  - *Spec:* **12"-wide × 2"-thick sawn coral stone or cream limestone**, eased or bullnose front, 1–1½" overhang over the tile. Joints every 24" (3/16" grout).
  - *Real look:* slightly darker wet zones near the steps and spa spill. **White calcium bloom** in the joints.
- **Waterline tile.**
  - *Spec:* a **6" band of 6 × 6 glazed porcelain** in ocean-blue or teal. **Fujiwa** is the classic Hawaiʻi pool tile and has hand-variable glaze. The reference shows teal-blue with tile-to-tile variation.
  - *Waterline:* the water sits at **mid-tile** (3" down), not brimming. A **faint white scale line** at the water level and a slightly darker band just below.
- **Interior.**
  - *Spec:* **Pebble Tec / Pebble Sheen** in "Aqua Blue" or "Blue Surf", a speckled aggregate finish.
  - *Look:* the floor shows **mottling** and **caustic light networks** in sun. Depth darkens the colour from pale aqua at the steps (3'-6") to a deeper blue at the 5'-6" end. Steps have a **1" contrasting tile line on each nosing** (common design, not required).
- **Fittings.**
  - **Main drains:** 2 anti-entrapment VGB covers, 9" round, white or tinted to match, about 3 ft apart at the deepest point.
  - **Returns:** 4–6 white or grey "eyeball" fittings about 18" below the waterline.
  - **Lights:** **2 pool lights** (Pentair IntelliBrite 5G, about 10" lens) on the north wall facing south, 18" below the waterline, plus 1 in the spa. Their niche rings show by day as stainless rings.
  - **Skimmer:** 1 at the east end near (−20, 30), with a 10" round grey lid on the coping and **a few leaves inside**.
  - **Autofill:** a 6" round lid on the deck.
  - **Cleaner:** a **robotic pool cleaner** (Dolphin, grey/blue, about 17 × 17 × 11") on the pool floor or parked on its caddy by the equipment gate, with a floating blue cable.
- **Steps.** 3–4 steps plus a bench at the east end (y 27–31), 12" treads.

### 6.3 Vanishing edge and catch basin
- **Weir.** Along the full 30-ft south side (x −31). A **knife-edge or ¼"-chamfered stone/tile weir** with the water spilling as a sheet about ⅛–¼" thick at the lip.
  - *Real behaviour:* the sheet is **never perfectly uniform**. It breaks into strands and fingers where the weir is slightly out of level (±1/16"), and the **trade wind pushes it**, so the upwind (east) end runs thinner. The falling sheet is translucent with white turbulence at impact.
- **Spillway face.** About 3 ft tall (`drop` 3). Tiled to match the waterline, or the coral stone.
  - *Look:* a dark wet band, **white calcium streaks** (scale lines following the flow), and green-black algae in the corners.
- **Catch basin.**
  - *Spec:* about 2'-6" wide × 30 ft long with 12–18" of water, at the base, inside the retaining wall. The interior is darker (charcoal or dark blue plaster or tile) so it reads as depth.
  - *Look:* the water is **turbulent and foamy** at the fall line, with leaves and bougainvillea bracts collected at the downwind end.
  - *Fittings:* 1 large suction grate and an overflow pipe.

### 6.4 Raised spa (x −23.5…−17, y 1…7.5: 6.5 × 6.5 ft, at the pool's NW corner)
- *Spec:* raised **about 18" above the pool water**, walls clad in the waterline tile. A **spillway notch 24" wide** on the pool side with a sheeted overflow, or a full-perimeter spill on 2 sides (reference).
- *Inside:* a perimeter bench at 20" below the water, **6–8 stainless jet faces**, 1 light, 1 step.
- *Controls:* a **Pentair iS4 SpaCommand** button panel (white or grey, 3 × 5") recessed in the coping, or on a post near the lānai.
- *Look:* water slightly steaming at dawn (optional), surface glassy versus the rippled pool.

### 6.5 Coral-stone retaining wall (south edge, x ≈ −34.4, where the land falls about 5 ft; also the planter walls in the reference)
- *Spec:* reinforced CMU or concrete, clad in **coral stone veneer** (Philippine or Caribbean "keystone" coral stone, 1½–2" thin-cut) in irregular/random-ashlar pieces 8–20" (reference). Joints are tight (⅛–⅜") with sand-coloured mortar. Capped with **14"-wide × 2" sawn coral stone coping** with a 1" drip overhang.
- *Look:*
  - Stone-to-stone tone variation: cream, tan, grey-white, a few pinkish pieces. Visible fossil shells and coral polyp pores.
  - **Weep holes:** 2" PVC at 6–8 ft on centre, 6–12" above the lower grade, each with a **dark streak below**.
  - **Black and green algae streaks** under the coping drip line.
  - White efflorescence blooms near the base.
  - Red-dirt splash at the base.
  - Grass or bougainvillea spilling over the top.

### 6.6 Deck and loungers
- **Deck.** A 3-ft coral-stone deck (`deck` 3) on the non-vanishing sides, 24 × 24 pavers with sand joints, sloped away from the pool to a 2" slot drain or to lawn.
- **Loungers.**
  - *Spec:* **2 teak chaises** (Kingsley Bate or Gloster, about 78 × 28", backs adjustable) at (−28.5, −5) and (−24.5, −5), on a small coral-stone pad (not on lawn, or their feet sink).
  - *Cushions:* **white Sunbrella**, 3" thick, with welts, slightly creased.
  - *Props:* a **rolled striped beach towel** on each, a pair of sunglasses on one.
- **Side table.** A teak table between the chaises with a water bottle and a paperback.
- **Umbrella.** A **9–11-ft cantilever or market umbrella** (Tuuci or Santa Barbara Designs) in "Canvas Natural" Sunbrella. **Closed and tied** (trade winds), or half open.
- **Pool rinse shower** (common). A 316 stainless post shower (about 7'-6" tall, 4" square, foot-wash tap at 18", head at 84") at the lawn edge near (−15, 32), on a 2 × 2 ft pebble pad.

### 6.7 Plants at the pool (model)
- Foxtails at (−29.5, −5.5) and (−26, −1.2) by the loungers.
- Bougainvillea beds at the SW corner (x −33…−31.5), the planter (x −33…−20, y 36–40), and the boundary bed (x −42…−36, the full length).
- See §12. Real bougainvillea drops bracts that **float in the pool and collect in the skimmer and catch basin**. Show 10–30 magenta bracts on the water and in the basin.

### 6.8 Pool safety (§0.2)
- Door alarms at 54" (§4.7).
- **48" black vinyl-coated welded-wire fence inside the boundary hedges** along y −7 and y 52.5, and **behind the bougainvillea at the bottom of the bank** (x −36). It shows as a thin black grid line through gaps in the foliage. Its posts are 1⅞" black steel at 8 ft on centre.

---

## 7. Covered lānai and outdoor kitchen (x 1.83–18.65, y 3.3–28.52: 494 sf)

### 7.1 Structure
- **Beam.**
  - *Spec:* a **25'-2" clear span** along x 1.83. A solid cedar timber that long is not available, so the real build is a **steel W-section or glulam core wrapped in rough-sawn WRC boards**, finished about **10 × 18"**.
  - *Look:* **mitred corners** with a hairline open joint. A drainage gap at the bottom of the cladding.
- **Posts.**
  - *Spec:* 2 rough-sawn WRC posts, **10 × 10 (or 12 × 12 to match the reference's mass)**, at (1.83, 3.3) and (1.83, 28.52). The second is engaged against the primary wing wall: show a ½" gap and caulk line, or a post pocket.
  - *Base:* a black standoff base with a 1" gap above the coral stone.
  - *Head:* a black knife-plate head with 4 × ¾" through-bolts per side and black square washers (the reference shows bolt heads on the beam).
  - *Look:* seasoning checks; band-saw texture.
- **Ceiling.** 1 × 6 T&G V-groove, painted white (exterior satin), **running down the slope** as in board-7.
  - Hips are mitred with a 1 × 4 hip trim.
  - Board butt joints are staggered (lengths 12–16 ft).
  - **Grease and soot shadow** on the T&G around the outdoor hood.
  - Spider webs and a gecko or two at the corners near the lights.
- **Walls.**
  - The lānai's inner walls (TV wall y 28.52, pocket wall x 18.65, west wall y 3.3) are **vertical white board-and-batten** (reference). The exterior elsewhere is lap siding.
  - The battens die onto a 1 × 6 base at the floor and a 1 × 8 frieze at the ceiling.
- **Floor.**
  - *Spec:* coral stone or cream limestone, 24 × 24 or 16 × 32 in a French pattern (reference: light tan pavers), with 3/16" sanded grout.
  - *Slope:* falls **⅛–¼"/ft toward the lawn**. The edge drops **4–6"** to the lawn mow strip, or is flush with a 2" slot drain.
  - *Look:* a darker wet band near the edge where rain blows in, a chair-scuffed patch under the dining chairs.

### 7.2 Outdoor kitchen (counter at (9.35, 4.8), 7'-10" × 2'-6", along the west wall y 3.3)
- **Base and top.**
  - *Base:* reinforced CMU, clad in coral stone or white smooth stucco. The reference shows a white stone end panel.
  - *Top:* **2–3 cm leathered quartzite or granite** ("Taj Mahal" or "Absolute Black" leathered). Quartz is not used outdoors because it yellows in UV.
  - *Heights:* counter 36". 12" overhang on the end panel.
- **Grill.**
  - *Spec:* **36" built-in 316 stainless gas grill** (Kalamazoo, Lynx or Fire Magic), with knobs and a stainless lid.
  - *Real look:* **tea-stain freckles** on the stainless. Commonly a **fitted black or grey vinyl cover** is on the grill when not in use, which is the lived-in version.
- **Fridge and storage.** A 24" 316 outdoor fridge (True or Perlick), stainless door with a black handle, plus 2 stainless access doors and a 3-drawer unit.
- **Hood.**
  - *Spec:* **Vent-A-Hood outdoor, 42–48" wide, 316 stainless**, bottom at **36–42" above the grill** (about 6'-0"–6'-6" AFF), ducted up through the roof (cap on the west slope).
- **Sink (optional).** A 15" bar sink with a 316 gooseneck faucet.
- **Outlets.** **2 GFCI outlets** on the backsplash wall or end panel at 42–44" AFF.
- **Lighting.** Hood lights. One under-counter LED strip is optional.
- **Lived-in props.** A teak cutting board, a pepper grinder, salt in a bowl, grill tongs on a hook, a folded kitchen towel, a pineapple or a bunch of apple bananas in a wooden bowl.
- **Windows.** The 2 high windows on the west wall (x 2.9–4.8 and 14.0–15.9) flank the hood.

### 7.3 Dining, lounge, TV, fans and lights
- **Dining.**
  - *Spec:* a **teak table 6'-1" × 3'-9"**, 29½" tall, at (9.78, 12.85), with **8 teak chairs** (Gloster or Kingsley Bate, woven rope or white Sunbrella seat pads), 2 of them carvers at the ends.
  - *Look:* chairs **not perfectly aligned**, one pulled back.
  - *Table props:* a long teak or lauhala runner, a white ceramic vase with monstera leaves or ti leaves, 2–3 hurricane lanterns.
- **Lounge.**
  - *Sofa:* 7-ft teak-frame **outdoor sofa** at (9.78, 27.26), facing the TV. **White Sunbrella cushions** with welts, slightly sagging. 5–7 throw pillows (Sunbrella linen, a navy stripe, a sand bouclé).
  - *Chairs:* 2 teak lounge chairs at (5.0, 21.7) and (14.1, 21.7).
  - *Tables:* a teak coffee table 4'-3" × 2'-2" × 16" with a **woven rattan tray**, a coffee-table book, a candle and a coconut bowl. 2 teak side tables at 22".
  - *Rug:* **outdoor jute-look polypropylene rug, 9 × 12**, corners not quite square.
- **TV.**
  - *Spec:* **65" outdoor TV** (SunBriteTV Veranda or Samsung The Terrace), matte black with a thick bezel and **3–4" deep body**, on a low-profile mount.
  - *Where:* on the TV wall y 28.52, centred x ≈ 9.8, at **56–60" AFF to centre**, with a recessed TV box behind (no cords showing).
  - *Look:* the screen off and dark grey, reflecting the lānai and lawn.
- **Fans.**
  - *Spec:* **2 wet-rated 60" black fans**, airfoil 3-blade (Big Ass Fans Haiku Outdoor, Minka-Aire Light Wave Wet, Modern Forms Wynd Outdoor).
  - *Where:* at (9.78, 10.39) and (9.78, 23.0), on sloped-ceiling adapters, blades at **8'-6"–9'-0" AFF**.
  - *Control:* a wall control at 48" by the pocket door.
- **Lights.** **6 wet-rated 3" round downlights**, white trim, 2700 K, in 2 rows of 3 at about 4 ft in from the beam and the wall. Optional: a large woven outdoor pendant (e.g., 30" rope or rattan) over the dining table, bottom at 66" AFF.
- **Floor lanterns.** 2–3 teak/glass hurricane lanterns, 18–24", with pillar candles, by the sofa (reference).
- **Outlets and switches.** 3 GFCI outlets: TV box, sofa end at 16", kitchen. A switch bank by the pocket door inside at 48": lānai lights, fans, kitchen.
- **Audio.** 2 outdoor-rated in-ceiling speakers (8" round white grilles) in the T&G.
- **Pool alarm.** On the pocket-door jamb (§4.7).
- **Plants.** 2 large planters with a kentia palm or *Strelitzia*, against the posts or wall.
- **Lived-in signs.**
  - A beach towel draped over a chair back.
  - A pair of slippers by the pocket-door track.
  - **Sand** in the slider track.
  - A water glass with condensation ring on the coffee table.
  - A gecko on the wall near the sconce.

---

## 8. Great room (x 18.65–48.22, y 0.17–28.52, plus the gallery alcove x 35.7–48.48, y 28.52–32.17)

### 8.1 Shell
- **Floor.**
  - *Spec:* **engineered white oak**, ⅝–¾" thick with a 4–6 mm wear layer, **7½" wide** (9½" is also common), **random lengths 2–8 ft** (some to 12 ft), end joints staggered at least 6–8" with no "H" patterns.
  - *Grade:* rift and quartered, or live-sawn "select" with occasional pin knots.
  - *Finish:* **matte natural** (Rubio Monocoat "Pure" or Bona Traffic HD Naturale), roughness 0.5–0.6.
  - *Orientation:* planks run **north–south (along x)**, leading the eye to the lānai.
  - *Real look:*
    - micro-bevel lines
    - board-to-board tone variation of ±10%
    - **sheen variation in raking window light** (footprint paths, a faint scratch near the island)
    - slight cupping glint at the lānai doors from humidity
  - ⚠ The current realtime planks are too wide and too uniform.
- **Walls.**
  - *Spec:* **board-and-batten**: ½" MDF or drywall field with **1 × 3 battens (2½" face, ¾" proud) at 16" on centre**, floor to 10-ft plate. A **1 × 8 frieze** at the plate and a 1 × 6 flat base (some builders add a ½" shoe).
  - *Paint:* BM Chantilly Lace or White Dove, eggshell on the field, semi-gloss on the battens.
  - *Real look:* a **caulk bead** at every batten-to-field joint (a soft sheen line), filled nail holes faintly visible in raking light, battens meeting the base with a tiny shadow.
  - ⚠ The current render spaces battens at about 24", which is too wide.
- **Ceiling.**
  - *Spec:* **1 × 6 T&G V-groove, painted white (flat or matte)**, in a **hipped vault**. The ridge runs north–south at y ≈ 14.3, at about 17 ft AFF inside (the roof plane is at about 17'-10"). The slopes rise from the 10-ft plates at 6.6:12. Hip lines are trimmed with mitred 1 × 4.
  - *Board lengths:* staggered 12–16-ft lengths, so **short butt joints appear across the vault**.
  - *Real look:* a **subtle green-yellow colour cast** on the lower slopes from bounce off the oak floor and lawn (§14). Slight paint sheen streaks along the boards.
- **Tie beams (optional).** A 29.6-ft hipped vault usually has **2 exposed tie or collar beams** at about 10 ft on centre across the room (6 × 10, rough-sawn cedar to match the lānai, or painted white), with black steel strap connections. Engineers often require them, and they're very much the Hawaiʻi plantation look. The brochure doesn't show them.
- **Flat soffits.** A **9-ft drywall bulkhead** where the vault meets the 9-ft pantry and hall zones at x 48.22: smooth white with a crisp corner bead.

### 8.2 Doors and openings
- **Pocket door** (§4.7).
- **Pivot front door** (§3.2).
- **Primary bedroom door:** 3'-6" × 8'-0" at y 28.52, x 19.35–22.87. A pair of 1'-9" two-panel shaker doors, painted white, with black levers. **Door stops:** black floor domes (1" tall) or hinge-pin stops.
- **Cased openings** to the pantry and hall: 3½" flat casing with a **plantation head**: a 1 × 6 head plus a ¾" cap projecting ½".

### 8.3 Lighting, fans, controls
- **Living fan.**
  - *Spec:* **60–64" black airfoil fan** (Big Ass Fans Haiku or Modern Forms) at (27.43, 21.04).
  - *Mounting:* the ceiling there is about 13–14 ft (7.5 ft from the east plate), so use a **24–36" downrod** to put the blades at about **9'-6"–10'-0" AFF**.
- **Dining pendant.**
  - *Spec:* **rattan/woven pendant about 31" diameter** (Serena & Lily or Made Goods style) at (28.48, 7.26).
  - *Mounting:* bottom **30–34" above the table** (about 5'-0"–5'-4" AFF). The ceiling is about 13–14 ft, so about 6–7 ft of black cord or chain, with a **black canopy on a sloped-ceiling adapter**.
- **Island pendants.** 2 **opal glass globes about 13"** on black or brass stems, at (40.43, 7.43) and (40.43, 10.74). Bottom at **66–70" AFF**, i.e. 30–34" over the island. The ceiling there is about 14 ft, so the stems are **about 7 ft long**. Real installers use cord with a tight canopy.
- **Recessed lights.**
  - *Spec:* **3" round flush-trim LED downlights** (DMF or Lotus), white trim, 2700 K, set into the T&G boards.
  - *Count/where:* about **14** in the main great room, in 2 rows along the lower slopes about 4–5 ft in from each plate, at 6–8 ft on centre, plus 4 over the kitchen counters.
  - **3 adjustable 2" wall-wash downlights** about 20" off the coral stone wall to graze it.
- **Lamps.** 1 table lamp on the side table at (32.96, 16.78): ceramic or rattan base, linen drum shade, about 28" tall.
- **Switches.**
  - *Spec:* **Lutron Caséta / Diva** in white (or "Midnight" black to match the fixtures), Decora rockers, **48" AFF to centre, 4–6" off the casing on the latch side**.
  - *Banks:*
    - **4-gang** inside the pivot door, latch side at about (47.9, 27.3): entry lights, living cans, fan, dining pendant
    - **3-gang** by the pocket door at about (18.9, 24.2): lānai cans, lānai fans, outdoor kitchen
    - **3-gang** at the kitchen by the hall opening at about (47.9, 12.5): pendants, under-shelf, kitchen cans
    - **1–2-gang** at the primary door and the gallery
  - Each fan gets **a wall fan control** (a small white keypad).
- **Thermostat.** Ecobee or Nest, white, about 4 × 4", at **60" AFF** in the gallery alcove at about (40, 32.0).
- **HVAC.**
  - *Supply:* ducted from air handlers in the 9-ft zones. **Two white high-sidewall supply grilles, about 24 × 8"**, at about 9'-0" AFF on the x 48.22 wall above the hall and pantry openings, blowing south. Or a **2-slot linear diffuser, 4 ft**, in the kitchen bulkhead.
  - *Return:* a **white stamped-face return grille, 24 × 24"**, in the hall ceiling or low on the hall wall.
- **Smoke alarm.** Hard-wired, white, about 5½" diameter. Because of the vault, mount it **on the sloped ceiling within 36" horizontally of the ridge** (not in the top 4") at about (24, 15). It covers the primary bedroom's outside-sleeping-area requirement.
- **Speakers.** **4 in-ceiling 8" round white grilles** (Sonos Architectural) in the living zone around the fan, and 2 over the dining table. Paint-matched, but visibly a different texture from the T&G.
- **Outlets.**
  - **About 10 duplex at 16" AFF** around the perimeter (none in the pocket-wall zone y 5.3–23.4).
  - **1 brass or black floor box** (Lew Electric, flush flip lid, about 4 × 6") under the sectional at about (27.4, 18.6).
  - A **recessed TV box** behind the TV at about 52" AFF.
  - Outlets are placed **in the field between battens**, never straddling one.

### 8.4 Coral-stone feature wall and media
- **Feature wall.**
  - *Spec:* **coral stone veneer** (Philippine or Caribbean coral stone, or Coralina), 1½" thin-cut, sawn and honed face, in **6 × 24 and 12 × 24 stack-bond or offset pieces**. Or the rough "split" coral of board-7.
  - *Size/where:* about 11'-3" wide × floor to the 10-ft plate, on the y 28.52 wall at x 23.6–34.8.
  - *Joints:* tight, ⅛".
  - *Real look:* porous, with fossil shell and polyp pores, a cream-to-tan-to-grey mix. Both ends finished with a **¾" stone return** or a black metal L-trim. A **visible grazing-light scallop** from the wall washers.
- **Media console.** **Floating white-oak console, 11'-2" × 16" deep**, at 12–14" AFF to the underside, with **cane-front doors**. Props: 2 ceramic vases, a stack of books, a koa bowl, a small sound bar.
- **TV.** **75" (6 ft wide)**, black, with an **art-mode frame TV** option (Samsung Frame with a white or oak bezel). Centre at about **58–62" AFF** (bottom about 42"). The screen is off and reflecting the room.

### 8.5 Furniture and props (from the list, with real dimensions)
- **Sectional.**
  - *Spec:* white or ivory performance linen (Perennials, Crypton), seat 18–19", back 31–33", arms 24", **loose seat and back cushions with crowns, creases and a slight dip** where people sit. 6–8 pillows (22", linen in oatmeal, sand stripe, one muted ocean blue) **with karate-chop dents**.
  - *Where:* at (27.35, 16.65), chaise toward the lānai.
  - *Throw:* a **chunky cotton or waffle throw** draped over the chaise end, partly on the floor.
- **Coffee table.** Round white oak, 43" diameter × 16", at (29.22, 21.13). Props: a **koa wood bowl** (a classic Hawaiʻi object, about 14" with figured curly grain), 2 coffee-table books (one about surfing, one about Kauaʻi), a small white ceramic coral-shaped object (real coral collecting is illegal; décor is ceramic), a lauhala tray.
- **Armchairs.** 2 oak-frame linen chairs at (37.17, 20.04) and (36.39, 24.39), with **cane panels** in the sides or backs.
- **Rug.** **Jute, 13'-9" × 12'-3"**, chunky braid or herringbone weave, ⅜–½" thick, with a bound edge. The front sofa legs sit on it. **One corner slightly lifted or curled.** Faint vacuum stripes.
- **Dining.**
  - *Table:* white oak, about 84 × 44" × 30", at (28.48, 7.24).
  - *Chairs:* **8 chairs** with **cane backs** and white seat cushions, ends in armchairs. Seats 18", backs 32–34". **Chairs slightly askew.**
  - *Table props:* a centre runner, a **white orchid** (Phalaenopsis) in a ceramic pot, a bowl of limes or lemons.
- **Art.** A large ocean print 5'-6" × 3'-7" on the west wall y 0.47 at x ≈ 27.2. Real hanging centre is **60–64" AFF** (the model has 5.6 ft = 67"; slightly lower is more real). Thin white-oak frame with a white mat and **non-glare glass** (a soft window reflection).
- **Plants.**
  - **Fiddle-leaf fig** (Ficus lyrata), 7 ft, at (20.22, 2.13), in a seagrass basket. **2–3 leaves with brown edge spots**, one yellow leaf on the floor.
  - A 1.6-ft basket plant at (47.61, 26.04), e.g., a monstera or bird of paradise.
- **Entry landing zone.** A shallow lauhala tray for keys, sunglasses and sunscreen on the console by the pivot door at about (46.5, 27).
- **Lived-in objects.** An ʻukulele on a wall hook or stand near the media wall, a surfboard (9-ft longboard, light) leaning in the gallery alcove or wall-mounted horizontally at 7 ft, a pair of reading glasses on a book, a phone charger cable at the side table.

---

## 9. Kitchen (x 37.13–48.22, y 0.17–13.87) and pantry (x 48.22–54.17, y 0.17–10.22)

### 9.1 Layout as traced
- **Wall run:** counter along the west wall y 0.17, x 38.0–44.8 (6'-9"), with open shelves above.
- **Fridge:** x 44.8–48.0, y 0.35–2.6.
- **Range run:** along the x 48.22 wall, y 5.5–12.7 (7'-2"), with the hood.
- **Island:** 3'-11" × 7'-2" at (40.43, 9.09), long axis east–west, sink, **3 stools** on the south face at y 6.7, 9.1, 11.5.
- ⚠ *Plan check:*
  - (a) The range run overlaps the **5'-4" pantry cased opening** at y 2.74–8.09 by about 2.6 ft. Really, the pantry opening sits between the fridge and range (y 2.7–5.4, about 2'-8" clear) and the range run starts at y 5.5.
  - (b) Aisles are tight: island end to the wall counter is 35½", and island to the range counter is 39". The NKBA standard is 42". A real kitchen would shorten the island to about 6'-6" or shift it 6".

### 9.2 Cabinets and counters
- **Cabinets.**
  - *Spec:* **rift-sawn white oak, slab or 1"-rail shaker** (board-7 shows oak shaker with an open bottom shelf on the vanity, the same family). Natural matte, toe kicks 4", **inset or full-overlay doors with ⅛" reveals**.
  - *Hardware:* **matte black bar pulls**, 6" on doors and 12" on wide drawers, mounted horizontally on drawers and vertically on doors.
  - *Look:* slight door-to-door grain variation.
- **Counters.**
  - *Spec:* **3 cm white quartz** (Caesarstone "Pure White" or a soft Calacatta-look like "Frosty Carrina"), eased edge. 36" AFF. Island overhang **12–15"** on the stool side.
  - *Look:* soft blurry reflections of the windows and pendants. A **seam** on the 7-ft island (a hairline about 1/32", colour-matched) if over 120" (it isn't, so none). A seam at the L corner of the wall run.
- **Backsplash.**
  - *Spec:* **white zellige** (Clé "Weathered White" or similar handmade glazed tile) at **2 × 6 or 4 × 4**, full height to the shelves and the hood.
  - *Look:* **irregular glaze, wavy surface catching the light in a hundred small highlights**, slightly varied whites, sanded grout 1/16"–⅛". Zellige reads as real even in a low-poly scene if the normal map is right.
- **Open shelves.**
  - *Spec:* 2 **floating white-oak shelves, 2" thick × 10" deep**, on hidden steel brackets, bottoms at **54" and 70" AFF**, over the west counter run.
  - *Props:* white ceramics (plates in stacks of 6, 4–6 bowls, mugs), 2 glass jars, a small potted pothos trailing, a cookbook leaning.
  - *Lighting:* an LED tape under the lower shelf (2700 K), with a visible scallop on the zellige.

### 9.3 Appliances and fixtures
- **Range.**
  - *Spec:* **36" pro induction** (Wolf, Thermador or Bosch). Kauaʻi has no natural gas, and new high-end homes increasingly skip propane indoors. Black glass top, stainless front and knobs.
  - *Optional:* a 48" dual-fuel on propane is also seen. If so, add a CO alarm.
  - *Where:* centred on the range run at about y 9.1.
- **Hood.**
  - *Spec:* **white plaster or drywall tapered hood** (a smooth trowelled finish, sometimes with a 1½" matte black steel band at the bottom), 36–42" wide, bottom **30–36" above the cooktop** (about 66–70" AFF). A stainless liner insert with 2 LED lights and a baffle filter visible from below. Duct to the roof jack (§4.4).
- **Fridge.** **36" panel-ready built-in** (Sub-Zero or Thermador) with **white-oak panels** matching the cabinets, so it disappears. A black pull 18–24". Stainless French-door is the cheaper spec alternative.
- **Dishwasher.** **Panel-ready**, left of the island sink. A white-oak panel with a black pull. Only a ½" slot shows at the toe.
- **Microwave.** A **24" microwave drawer** in the island, stainless face, on the range side.
- **Sink.** An undermount single-bowl, 30–33", in **stainless or white fireclay**, centred on the island at about (40.4, 9.1).
  - *Faucet:* **matte black pull-down** (Brizo Litze or Delta Trinsic), about 16" tall.
  - *Water tap:* a separate **filtered-water tap** in black. Optionally an **instant-hot / air-gap cap** (black).
  - *Props:* a black soap pump and a **sponge or dish brush** in a small ceramic dish (lived-in).
- **Island outlets.** A pop-up outlet (Mockett, black or stainless, 2½" round lid) in the top, or **2 outlets on the island end panels** at 12" below the counter.
- **Backsplash outlets.** **About 6** in the wall and range runs, at **42–44" AFF**, white or black screwless plates, placed to land on tile courses. Real requirement: no point on the counter more than 24" from an outlet.
- **Trash.** A **double pull-out** (trash and recycling) in the island.

### 9.4 Lived-in kitchen props
- A **wooden fruit bowl with local fruit**: 2 papayas, a bunch of **apple bananas**, 3 limes, a lilikoʻi or two, a pineapple on the side.
- An espresso machine or drip coffee maker on the west counter, with a grinder.
- A **knife stand** or a magnetic knife strip.
- A **teak or acacia cutting board leaning on the backsplash**.
- Olive oil and salt in a bowl by the range.
- A **striped linen tea towel** over the range bar or oven handle.
- A small **potted herb** (basil).
- A paper-towel holder (black).

### 9.5 Pantry and scullery
- **Divider.** A divider wall at y 5.74 with a 2'-6" cased opening.
- **Walk-in (y 0.2–5.7).** **Open oak or white shelving**, 12–16" deep, 5 shelves from 18" to 84" AFF. Labelled glass jars, baskets, a case of water, rice bags (a Hawaiʻi staple: **25-lb Calrose**), paper goods, small appliances (rice cooker, blender).
- **Scullery counter.** 5'-5" × 13" along the divider, with a quartz top and a coffee station.
- **Window.** A high window (x 50.2–52.3, sill 4') with a roller shade.
- **Ceiling and controls.** A 9-ft flat ceiling with one 4" downlight on a **motion switch**, plus 1 outlet bank.

---

## 10. Primary suite (bedroom x 0–24.74, y 28.52–44.39; closets; bath x 22.39–31.91; garden shower 1)

### 10.1 Bedroom
- **Bed.**
  - *Spec:* **king** (frame about 86 × 90") at (8.15, 40.65), head on the east wall y 44.39, between the 2 shuttered windows (x 1.8–3.9 and 12.2–14.3).
  - *Headboard:* **cane-panel white-oak headboard**, 54–60" tall.
  - *Linens:*
    - white or ivory **linen duvet, rumpled, falling to within 2–4" of the floor** (not floating)
    - 2 Euro shams
    - 2 king pillows
    - one lumbar pillow
    - a **folded oatmeal throw on the foot**
  - *Mattress top:* 24–26" AFF.
- **Nightstands.** Oak or cane, 26" tall, at (2.83, 43.07) and (13.48, 43.07). Each has a **table lamp** (ceramic base, linen shade, 26–28"), a book, a glass of water, a small tray.
  - ⚠ The windows' 18" sills put the **nightstands and lamps directly in front of the lower glass**, which real photos would show as a silhouette. Real designers would centre narrower nightstands between the bed and the windows, or use **swing-arm wall sconces** (black, at 48–54" AFF) instead of lamps.
- **Media and seating.**
  - **TV**, 65" (5 ft), over a white-oak media console (5'-8" × 16") at (8.04, 29.52) on wall y 28.52. Centre about 54–58" AFF. That wall backs onto the lānai TV: in reality the two recessed TV boxes are **offset at least 24"** horizontally.
  - **Reading corner** at the SW (3.48, 31.61): a linen armchair with an ottoman, a side table, and **a floor lamp** (black arc or tripod, 60–66").
  - **Rug:** jute, 11 × 9, bed sitting on it with about 2 ft showing on each side.
- **Slider dressing.**
  - *Shades:* **motorised roller shades** (Lutron Sivoia or Hunter Douglas) in white solar-screen (3–5% openness), in a **recessed head pocket** (a 5" slot in the ceiling or header).
  - *Drapery:* **linen drapery** (white, floor-length, 2 panels each side, about 108" drop) on a **ceiling track** in front. Panels have a **1" puddle or break** on the floor, with folds of varying depth.
- **Fan.** 52–60" black airfoil at (8.04, 36.48), downrod to put the blades at about 9 ft.
- **Smoke alarm.** On the sloped ceiling near the ridge.
- **Switches.** At the door (3-gang: cans, fan, sconces) and **bedside** (2-gang each side, at 30–36" above the nightstand).
- **Outlets.** About 6 at 16" AFF, plus **nightstand outlets with USB-C**.
- **Art.** Kapa-pattern art (5'-0" × 2'-7") over the headboard. Bottom about 8–10" above the headboard top (the model has its centre at 6.9 ft, which is consistent with a 60" headboard).
- **Plant.** A basket plant at (15.0, 43.0).
- **Lived-in props.**
  - Slippers by the bed.
  - A sun hat on the armchair.
  - An open book face-down on the nightstand.
  - A phone charging.
  - The drapery slightly unevenly opened.

### 10.2 Primary closets (2 walk-ins, 6.4 × 4.3 ft each, 9-ft ceiling)
- **Shelving.** **White painted or oak closet systems** (California Closets / Elfa style): double-hang on one side (rods at 42" and 84"), single-hang plus shelves on the other.
- **Contents.** Half-filled: linen shirts, dresses, a beach cover-up. Shoe shelves with sandals, slippers and **golf shoes**. 2 hats on hooks. A suitcase on the top shelf.
- **Lighting.** **LED strip lighting** under the shelves and a 4" downlight.
- **Mirror.** A full-length mirror on the back of the door or the end wall.
- **Hamper.** A woven hamper.
- **Doors.** The double door pair from the bedroom on wall x 16 (y 36.4–39.9): 2 × 1'-9" two-panel shaker, white, black levers.

### 10.3 Primary bath (x 22.39–31.91)
- **Floor.**
  - *Spec:* **coral stone or porcelain coral-look, 12 × 24 or 24 × 48, honed or matte**, sand grout.
  - *Look:* slight lippage, a **bath mat** (white Turkish cotton or a kilim-pattern runner as in board-7) in front of the vanities and the tub.
- **Vanities.**
  - *Spec:* **two separate 36" floating or legged white-oak shaker vanities** (board-7) at (23.59, 33.87) and (23.59, 41.83) on wall x 22.39. **34–36" tall**, with an open bottom shelf showing **rolled white towels and a woven basket** (board-7). Black bar pulls. A white quartz top with an undermount white sink.
  - *Faucet:* **matte black widespread**, about 8" spread, with lever handles (board-7).
  - *Mirror:* **black-framed rounded-rectangle, 24 × 36"**, bottom at **42–44" AFF** (board-7).
  - *Light:* **black 2-light bar sconce with opal globes** **above each mirror at about 78–80" AFF** (board-7), or flanking sconces at 66".
  - *Props:* **amber glass soap pumps**, a ceramic cup, a **vase with a eucalyptus or olive branch**, a small jewellery dish (board-7 styling).
  - *Accessories:* a hand-towel ring at 54" beside each vanity.
- **Tub.**
  - *Spec:* **freestanding soaking tub, about 66 × 32"** (the plan has 60 × 32; 66 is more common in primaries), white matte stone resin (Victoria + Albert or MTI), at (29.96, 35.07) in front of the slider to garden shower 1.
  - *Filler:* a **floor-mount matte black tub filler** (about 36" tall) with a hand shower.
  - *Props:* a **teak tub tray** across the tub with a candle and a book.
  - *Accessories:* a towel bar or **heated towel ladder** (black) beside it.
- **Shower** (about 4'-2" × 4'-0" at (29.67, 42.2)).
  - *Glass:* a **⅜" low-iron glass panel and 24" door**, matte black hinges and a 12" pull, black U-channel at the wall. Bugs in the bottom corners. **Hard-water spots** at the lower 2 ft.
  - *Walls:* **white zellige or 3 × 12 glossy handmade-look tile**, or the board-7 look (white tile with a black-trim glass panel).
  - *Floor:* **2" hex honed marble or pebble mosaic**, sloped to a **36" stainless linear drain** at the back wall.
  - *Niche:* a **recessed niche 12 × 24"**, bottom at 42" AFF, with a quartz shelf, holding 3 bottles and a loofah.
  - *Fittings:* a **thermostatic valve** with a black trim at 44–48" AFF. A **12" square or round ceiling rain head** (black). A **hand shower on a 30–72" slide bar** (black).
  - *Window:* the high window at x 25.2–27.3 (sill 54") is tempered and obscure.
- **WC.**
  - *Spec:* the toilet at (30.22, 29.85) in the north end. **Toto Drake II / Ultramax II, one-piece, skirted, elongated, white**, seat down.
  - *Accessories:* toilet-paper holder at **26" AFF, 8–12" in front of the bowl** (black). A small plant or tissue box on the tank.
  - *Separation:* a pocket door or a half wall on the plan side (as traced it is open; real primaries usually give the WC a pocket door).
- **Exhaust.** **2 Panasonic WhisperCeiling fans** (8" square white grilles): one over the shower, one at the WC. Humidity-sensing.
- **Ceiling lights.** 4" white downlights × 4 in the 9-ft ceiling zones. Over the tub, a **damp-rated pendant** or a 3" downlight.
- **Switches.** At the entry: **3-gang** (vanity lights, cans, fan timer). Outlets: **GFCI within 36" of each basin**, i.e. 1 per vanity on the side wall at 42–44" AFF.
- **Hooks.** **Robe hooks** at 66–70" AFF by the shower and tub (black, 2).
- **Slider to garden shower 1.** 2 panels, with a **white roller shade** half down.

### 10.4 Garden shower 1 (x 31.91–37.83, y 32.17–44.39: open to the sky)
- **Enclosure.**
  - *Spec:* **7'-0" horizontal cedar slat walls** (1 × 4 WRC slats with ½–¾" gaps, on 4 × 4 posts at 6 ft on centre with stainless screws) on x 37.83 and y 44.39.
  - *Gate:* a **slatted gate (2'-7")** on y 44.39 at x 32.4–35.0 with a stainless or black **thumb latch at 42"**.
- **Floor.** **Coral stone pads or Indonesian pebble mosaic** (flat-cut river pebbles on mesh), sloped to a **brass or stainless 4" drain**, plus a border of 2" black Mexican beach pebbles at the walls.
- **Shower.**
  - *Spec:* a **freestanding outdoor shower column** at (35.0, 34.3): 316 stainless or **natural brass/bronze** that is going brown and green. Matte black chalks to grey outdoors here.
  - *Heights:* an 8" head at about 84" AFF, a thermostatic mixer at 42", and a **foot-wash tap at 18"**.
- **Fittings.** A **teak bench** (36 × 14 × 18"). **3 stainless towel hooks** on the slat wall at 66". A teak caddy shelf with a shampoo bottle.
- **Planting.**
  - A **plumeria** (small) or a **Pritchardia** palm in a corner bed.
  - **Bird's-nest fern** (Asplenium nidus) and **lauaʻe** at the base, **shell ginger** or **red ginger**.
  - Real look: **moss and green algae** on the shaded north face of the slats, water marks on the bench.
- **Light.** One **wet-rated black bulkhead or a down-only sconce** on the house wall at 7 ft.
- **Lived-in props.** A **striped beach towel over the slat wall top**, a pair of slippers.

---

## 11. Bedrooms 2 and 3, baths 2 and 3, garden showers 2 and 3, powder, laundry, halls

### 11.1 Bedroom 3 (x 54.17–68.43, y 0.17–16.09) and Bedroom 2 (x 54.26–68.43, y 28.52–44.39)
- **Beds.**
  - *Bedroom 3:* a queen or king at (61.54, 4.11), head on the west wall y 0.17.
  - *Bedroom 2:* at (58.48, 37.35), head on the west wall x 54.26.
  - *Spec:* linen bedding as §10.1, with lighter styling: 2 sleeping pillows, 2 shams, 1 lumbar, a throw. Upholstered linen or cane headboards. A **bench at the foot** (Bedroom 3: (61.54, 9.2), 6'-9" linen).
- **Nightstands and lamps.** As the model, at 24–26" tall.
  - ⚠ Bedroom 3: the nightstands at x 56.2 and 66.6 sit **in front of the 18"-sill windows** (x 55.7–57.8, 64.9–67.0). Real: narrower 20" nightstands placed between the bed and the window, or swing-arm sconces.
- **Art.**
  - ⚠ Bedroom 3's kapa art at (61.52, 15.79) on wall y 16.09 hangs **over the courtyard slider** (x 57.5–65.5). Move it to **over the headboard on the west wall**, centred at x 61.5, bottom 8–10" above the headboard.
  - Bedroom 2's ocean art on the x 68.43 wall at (68.13, 32.57): OK, but keep it clear of the window ending at y 31.26.
- **Courtyard sliders.**
  - *Shades:* **white roller shades plus sheer linen drapery**. For privacy from the courtyard and entry, **typically drawn about halfway** on a lived-in day.
  - *Screen:* a sliding screen panel parked over the fixed side.
- **Closets.** The wardrobes in the bath zones (69.6, 3.1) and (69.6, 41.4) are **reach-in closets with doors**: 2 bi-pass or hinged shaker panels, white, black pulls. Inside: hanging guest clothes and **extra pillows in a bag on the shelf**.
- **Bedroom 2 corner.** An armchair at (66.3, 29.96).
- **Fans.** 52" black airfoil at (61.52, 8.0) and (61.35, 36.48). Blades at about 9 ft.
- **Smoke alarms.** 1 each, near the vault ridge.
- **Outlets.** About 5 each at 16".
- **Switches.** A 2-gang at 48" inside each door on the latch side: Bedroom 3's door at x 54.17, y 13.1–16.0; Bedroom 2's door at x 54.26, y 28.5–31.5.
- **Doors.** 2'-10"–3'-0" × 8'-0" two-panel shaker, white, black levers, black floor or hinge stops. **Door undercut ¾"** shows a strip of light under closed doors.
- **Jute rugs.** 10 × 8 (Bedroom 3) and 8 × 10 (Bedroom 2).

### 11.2 Baths 2 and 3 (x 68.43–78.48; mirror images)
- **Layout.** A closet alcove (x 68.4–70.8), a **WC alcove** between the short walls at x 70.76 and x 74.09 (toilet at (72.39, 1.17) / (72.39, 43.28)), and a **4 × 6 shower** at x 74.3–78.3. A **9'-8" double vanity** on the opposite wall.
- **Vanity.**
  - *Spec:* white-oak shaker, 2 sinks at about x 71.0 and 76.0, quartz top, black widespread faucets.
  - ⚠ The **2 high windows (sill 54", head 96") are directly behind the sinks** on walls y 11.93 and y 32.65, so a wall mirror fits only between 36" and 54". A real build would do one of these: (a) **pivot or round mirrors hung from black ceiling rods in front of the glass** (a real Hawaiʻi designer move, though faces get backlit); (b) mirrors on the flanking wall segments with the sinks shifted outboard; or (c) move the windows to sit above the WC and shower. Pick (a) to keep the elevations.
- **Shower.**
  - *Glass:* a **frameless ⅜" glass panel plus door** on the 6-ft side.
  - *Tile:* **white 3 × 12 or zellige walls**, coral or pebble floor, linear drain.
  - *Fittings:* black thermostatic valve at 44", wall rain head on an arm at 80" AFF, hand shower.
  - *Niche:* a recessed niche with bottles.
- **Slider.** The 6-ft slider to the garden shower (x 78.48) in **reeded glass**.
- **Exhaust and lights.** An exhaust fan in each. Vanity lighting: 2 black sconces at 66–72" or a bar above. 4" downlights.
- **Floor and props.** Coral floor, a **bath mat**, a **towel bar at 48" by the shower** with a white towel slightly askew.

### 11.3 Garden showers 2 and 3 (x 78.74–84.78; covered, under the wing roofs)
- **Enclosure.** Solid side walls in lap siding outside, white board-and-batten inside.
  - **North wall:** a **white louvred opening** 4'-2" × 7'-2" at sill 12".
  - **Gate:** a slatted cedar gate 2'-7" on the courtyard side (y 16.09 / 28.52, x 79.35–81.96), with a 42" thumb latch.
- **Ceiling.** T&G under the roof, with a **wet-rated downlight**.
- **Floor.** Coral pavers with pebble edges and a 4" drain.
- **Shower.** A **wall-mounted exposed outdoor shower** (316 or brass: valve at 42", head at 80") at (81.96, 3.87) and (81.96, 40.83).
- **Fittings.** A teak bench, 2 hooks.
- **Planting.** A potted **staghorn fern** or bird's-nest fern hanging on the wall. **Green algae on the grout at the low point.**

### 11.4 Powder (x 48.48–54.26, y 32.17–37.78) and laundry (x 48.48–54.26, y 37.78–44.39)
- ⚠ **Plan check:** as traced, the laundry is reachable only **through the powder** (two 4-ft cased openings in series), and the powder has **no door**. Real: **a 2'-8" pocket door** into the powder from the hall (vest2), the laundry entered **from the hall or the side garden** (it has the exterior door), and the opening between them closed or doored. The vanity at (53.26, 34.74) and the toilet at (52.17, 35.28) also **overlap** in the furniture list. Real layout: vanity on the east wall x 54.26 (y 32.5–35.1), toilet on the west wall below the window (y 36–37.5).
- **Powder fittings.**
  - *Vanity:* a **floating 30" oak vanity with a vessel or integral sink** and a black wall-mount or deck faucet.
  - *Mirror:* a round black mirror 24".
  - *Light:* one black sconce at 66–70".
  - *Walls:* **grasscloth or a dark accent** (the one room designers go bold): a deep navy or a seagrass wallpaper.
  - *Accessories:* a hand-towel ring at 54", toilet-paper holder at 26", a candle, a small orchid.
- **Laundry fittings.**
  - **Appliances:** a **front-load washer and dryer** (27" each, white or graphite) side by side under a **quartz counter** at 36", or stacked (the model's single 2.5-ft "washer" implies stacked; real side-by-side needs 5 ft).
  - **Sink:** a utility sink in the 2'-10" counter at (50.11, 43.22) with a black faucet.
  - **Hanging:** a **hanging rod** with 2–3 hangers, a wall-mounted drying rack.
  - **Window:** the high window at x 50.35–52.44, sill 54".
  - **Dryer vent:** to wall y 44.39 (§4.8).
  - **Door:** the exterior door to the side garden (§4.7, widen to 2'-8").
  - **Floor:** coral tile.
  - **Electrical:** a GFCI outlet at 42" and a 30 A dryer receptacle behind the dryer (not visible).
  - **Props:** a laundry basket with a few beach towels, a detergent bottle, an iron.
  - **Sub-panel:** the **main house electrical sub-panel** (Square D QO, 200 A, grey flush 14½ × 30" cover, often painted white) on the interior wall at 5'-0" to centre, with a panel directory card inside.

### 11.5 Halls
- **Ceilings.** 9-ft flat drywall, smooth. Use **4" white downlights** at 6–8 ft on centre in the west hall (x 48.2–54.2, y 10.2–16.1) and vest2.
- **Smoke / CO.** **Combination smoke/CO alarms**, one in each hall at about (51.2, 13.2) and (51.4, 30.3).
- **Return and access.** **HVAC return grille** in the west hall ceiling, 24 × 24 white. **Attic access hatch** (22 × 30", white, with trim) in a 9-ft ceiling zone, e.g., the west hall. Air handlers live above.
- **Wi-Fi.** A white access-point disc on the ceiling.
- **Art and storage.** A small framed photo or a lauhala-woven hanging.
- **Storage / wh closet** (x 31.91–35.7, y 28.52–32.17). The HPWH (§5) behind a **white louvred door 3'-0"**. Also brooms, a step stool, beach-towel shelves.

---

## 12. Landscape and planting realism

### 12.1 Palms
- **Foxtail palm** (*Wodyetia bifurcata*).
  - *Where (model):* (−29.5, −5.5), (−26, −1.2), (−8, 47), (95, −6), (140, 50).
  - *Real size:* field-grown specimens are craned in at **8–12 ft clear trunk, 16–22 ft overall**. After 12–18 months they are still about **18–24 ft**. The model's 30–38 ft is a 15–20-year-old tree.
  - *Trunk:* **smooth light grey with closely spaced pale leaf-scar rings** (every 2–4"), **8–10" diameter**, often a slight **bottle swelling** low down.
  - *Crownshaft:* **bright glossy green, 3–4 ft**.
  - *Crown:* 8–10 plumose fronds, 7–9 ft long, with **leaflets radiating all round the rachis** (the "foxtail").
  - *Fruit:* **clusters of 2" fruit** below the crownshaft, green ripening to **orange-red**.
  - *Dead fronds:* **one or two browning lower fronds** hanging down.
  - ⚠ The current Cycles back render has tall smooth trunks with small heads, which read as royal or Washingtonia palms, not foxtails.
- **Areca palm** (*Dypsis lutescens*).
  - *Where (model):* 12 clumps, 9–15 ft.
  - *Real form:* **clumps of 8–15 cane-like stems**, 1½–3" diameter, **yellow-green with rings**, arching fronds.
  - *Real colour:* in full sun, **noticeably yellowish** (potassium-hungry). **Brown leaf tips** and a few dead fronds tucked in the clump, sheath debris at the base.
  - *Use:* planted as screens 3–4 ft from walls (they hit the eaves when too close).
- **Optional native fan palm.** **Loulu** (*Pritchardia*), the native fan palm, as a courtyard or shower specimen: 6–10 ft, with a stiff costapalmate fan head.
- **Palm bracing** (new-construction tell). Every transplanted palm installed in the first 6–12 months is braced with **3 or 4 2 × 4 timber legs** to a **burlap-padded wood collar strapped with steel bands** at 1/3 of trunk height. At 12–18 months the braces are usually **gone, leaving faint strap scars**. Choose one consistently.

### 12.2 Flowering trees and shrubs
- **Plumeria.**
  - *Where (model):* 6 trees at (102, 15.2), (104, 29.4), (−4, 50), (44, 50), (139, 30.5), (137, 14.5).
  - *Species:* the reference's white-flowered *P. obtusa* "Singapore" (evergreen-ish, rounded glossy leaves) or *P. rubra* "Celadine" (white/yellow, deciduous).
  - *Form:* **candelabra branching**, thick grey succulent branches with **leaf rosettes only at the branch tips**, flower clusters at the tips.
  - *Size:* about 10–14 ft high and wide at install.
  - *Real look:*
    - **Fallen flowers on the pavers and lawn below**, some white, some browning.
    - **Plumeria rust** (orange powdery spots on leaf undersides; leaves yellowing in patches).
    - **Leaf drop Dec–Mar** with bare tips, which matters for the month you set.
- **Bougainvillea.**
  - *Spec:* magenta "Barbara Karst" or "Raspberry Ice".
  - *Real form:* a woody, thorny shrub or vine trained **along the top of retaining walls, over the boundary bank and on walls**, with **long arching canes**, papery bracts in clusters, lots of green leaf between flushes.
  - ⚠ Never free-standing magenta mounds dotted on the lawn, which is what the current render has.
  - *Litter:* bract litter on the lawn, pool and pavers.
- **Ti** (*Cordyline fruticosa*).
  - *Mix:* **green ti** (the traditional Hawaiian planting by doorways, for protection and luck) and **red/maroon ti** ("Rubra", "Firebrand").
  - *Real form:* **clusters of 3–7 canes of differing heights** (2–6 ft) per plant. Leaves clustered in the top 1–2 ft with **older leaves drooping and browning beneath**, and leaf scars on bare cane below.
  - ⚠ Never rows of identical lollipops on bare stalks (current render). Space at 2–3 ft in irregular drifts.
- **Gardenia.**
  - *Species:* *G. jasminoides* or **tiare** (*G. taitensis*, the Tahitian gardenia with pinwheel flowers).
  - *Form:* glossy dark-green shrubs 3–5 ft, **white flowers with some browned ones**, often **sooty mould or whitefly** dulling the leaves. Use as a low hedge along the walk at 3 ft on centre.
- **Monstera** (*M. deliciosa*).
  - *Real form:* leaves 18–36" with fenestrations and splits. **Juvenile leaves without holes** mixed in. **Aerial roots** snaking to the soil. One or two **torn or yellowing leaves**. Leaves face the light.
  - *Where:* the beds at x 86–99 and on the lānai's west side.
- **Common additions a Kukuiʻula landscape architect would use.**
  - **Naupaka** hedges, **ʻilima** (native, yellow-orange flowers) groundcover, **ʻakulikuli**.
  - **Bird's-nest fern** and **lauaʻe fern** (the ubiquitous shade groundcover).
  - **Dwarf mondo** in joints, **Asiatic jasmine** groundcover.
  - **Red and shell ginger**, **heliconia** (*H. psittacorum*) in the shower gardens.
  - **Crotons** (sparingly), **Strelitzia nicolai** at corners.
  - **Silver groundcover** (the reference shows a silver-blue groundcover, e.g., *Dichondra* "Silver Falls" or *Plectranthus*) along the beds.

### 12.3 Bed construction
- **Mulch.** **2–3" dark-brown shredded green-waste mulch** (Kauaʻi green waste), or black cinder in places. **Red dirt showing through** at edges and under drip lines.
- **Drip irrigation.** **½" brown drip tubing** with emitters visible at bed edges, plus **6" wire stakes**.
- **Plant spacing.** Groundcover and grasses at 12–18", shrubs at 3 ft, staggered (no grid).
- **New-planting tells** (if set at under 6 months):
  - **Sod seams** (16 × 24" or 2 × 4 ft pieces) visible as a faint grid.
  - **Mounded root balls** 2–3" proud.
  - **Nursery tags** (white plastic) on a few shrubs.
  - Plant gaps.

### 12.4 Fauna (cheap, extremely convincing)
- **Feral chickens (moa).** Kauaʻi's signature: **a rooster (red/gold/green-black tail) and a hen with 3–5 chicks** on the lawn or in the mulch. Scratching marks in the mulch nearby.
- **Nēnē.** A pair of nēnē (Hawaiian geese, grey-brown with a buff-striped neck) grazing on fairway 7 in the background. They are common at Kukuiʻula.
- **Birds.** **Common mynahs** on the lawn or roof ridge. A **red-crested cardinal** (grey with a red head). **Zebra doves**. **Cattle egrets** on the golf course.
- **Geckos.** **House geckos** (pale, 3–4") on the walls near exterior lights, especially at night shots.
- **At night.** A cane toad on the lawn.

### 12.5 Background (from the pool looking north, and from the street looking south)
- **Looking north (mauka).**
  - The green ridge of the **Hāʻupu range** (Hoary Head) to the NE.
  - The central mountains with a **cloud cap**.
  - Neighbours' Dutch-hip roofs among palms.
  - **No power lines** (underground).
- **Looking south (makai).**
  - **Fairway 7** of the Kukuiʻula golf course:
    - seashore paspalum, bright
    - **white sand bunkers**
    - a flagstick with a flag
    - a **concrete cart path**
    - the occasional **white golf cart** and tiny golfers
  - **Dense mixed canopy**: kiawe, monkeypod, coconuts near the coast.
  - **Red-dirt** patches.
  - **Resort roofs** at the coast.
  - A **hazy ocean horizon** at about 230 ft elevation (horizon dip ≈ 0.27°).

---

## 13. Weathering, imperfections and lived-in signs (age setting: 12–18 months)

### 13.1 Roof and metal
- **Roof.** The standing seam is matte, with **dust and pollen in the pan corners**, **a few bird droppings near the ridges and hips** (mynahs perch there), **leaf litter in the valleys and at gutter outlets**, and a **darker streak below each pipe boot**. Oil-canning reflections (§4.4).
- **Gutters and downspouts.** Dark drip stains under the gutter seams. Downspout straps with a rust-tinged screw head (one of them).
- **Exterior stainless.** Grill, outdoor shower, hose bibs: **tea-stain freckles** on 304. Brass fittings going **brown with green verdigris** at the joints.
- **Black window frames.** **Faint white chalk on the sun-facing sills and heads.** Salt-spray spotting on the south and west glass. **Sand and leaf grit in sliding tracks**, especially the lānai and primary.

### 13.2 Walls and trim
- **White siding.**
  - **Red-dirt splash** gradient at the base.
  - **Irrigation overspray marks**: dried mineral or red-dirt speckle arcs on the lower 2–3 ft where spray heads hit the wall. This is a very real, very common tell.
  - **Mildew grey-green speckle** on the shaded north and east faces, behind plants and especially on soffits and in corners.
  - **Cobwebs** in the eave corners and at light fixtures.
  - **Gecko droppings** (small black-and-white pellets) on the sills and floors under exterior lights.
  - Hairline caulk cracks at butt joints.
  - One paint touch-up patch with a slightly different sheen.
- **Trim.** Slight paint wear on sill noses. A ding in a corner board at mower height.

### 13.3 Wood
- **Cedar posts, beams, shutters, slat walls, garage door.**
  - **Silvering** on sun and rain faces (the tops of the louvres, the south faces of the posts, the street side of the garage door's bottom).
  - **Honey colour retained** in the shade.
  - **Dark water marks** at post bases and the bottom rails of shutters.
  - **Tannin bleed**: brown-orange streaks on the stone and paint below wood ends and fasteners.
  - **Black iron stains** around any non-stainless nail.
  - **Seasoning checks** opening and closing.
  - Mildew dots in the shaded north slats of the garden showers.
- **Teak furniture.** Silvering on the arm tops and seat slats. A **water-ring mark** on the coffee table. One chair a shade greyer (replaced or re-oiled).

### 13.4 Paving and stone
- Hairline cracks along the control joints of the curbs and apron. One **chipped paver corner**.
- **Efflorescence** at the coral-stone base. **Weep-hole streaks** (§6.5).
- **Algae** on the north-facing coping and in the catch basin corners. **Calcium streaks** on the spillway.
- **Rust-orange overspray stains** on the coral and limestone near sprinklers (iron in fertiliser and water).
- **Fallen plumeria flowers** and **bougainvillea bracts** on the pavers.
- **Grass growing into paver joints unevenly**, some joints bare.

### 13.5 Pool
- Water at **mid-tile**. A faint **scale line**.
- **A few leaves and 10–30 bougainvillea bracts** floating, and some on the bottom near the drain.
- **Wind ripples** (a 2–5 cm capillary chop plus a gentle long swell). The pool is never mirror-flat except at dawn.
- The skimmer lid slightly askew.
- The robotic cleaner present or its cable floating.

### 13.6 Lawn and beds
As §6.1 and §12:
- browner splash band
- greener head rings
- worn path
- chicken scratches
- **sprinkler heads not perfectly flush** (a few proud by ¼")
- string-trimmer scalps at the edges
- **mulch spilling onto the curbs**

### 13.7 Interiors
- **Fabric** never perfectly smooth: seat cushions creased, a **pillow crushed**, the duvet with **folds and a body-shaped dent**, curtains with uneven folds, tea towels hanging unevenly.
- **Rugs** off-square by 1–3° to the room, corners curling, **furniture-leg dimples** where chairs moved.
- **Hard surfaces:** dust motes in sunbeams, **fingerprints on matte black levers and the fridge pull**, a few **water spots on the island quartz near the sink**, a **sock-print sheen trail on the oak** in raking light.
- **Doors and switches:** doors at varied angles (not all fully open), one closet door ajar, a switch plate a degree off level, an outlet with a charger plugged in.
- **Shades:** **not all at the same height** (photographers usually level them; lived-in, they're uneven).
- **Small clutter, 3–7 items per room:** keys, sunglasses, a reusable water bottle, a sunscreen tube (mineral, since Hawaiʻi bans oxybenzone), a paperback, a phone, slippers.
- **Plants:** one browned leaf, soil on the saucer.
- **Glass:** **nose or hand smudge** on the lānai slider glass at 30–48" (a dog if you include one).

### 13.8 What to avoid (reads as fake)
- Perfect repetition (identical palms, ti, pavers, chairs at exact spacing).
- Pure white or pure black.
- Zero bevels.
- Floating objects with no contact shadow.
- Bedding hovering.
- Furniture all at 0°/90°.
- Spotless glass.
- Mirror-flat water.
- Grass touching siding.
- Uniform-brightness interiors with no falloff.

---

## 14. Light and photographic cues of real photos of homes like this

### 14.1 Camera and lens
- **Interiors.**
  - *Lens:* 16–20 mm full-frame equivalent (about 95–108° horizontal), at **48–60" camera height** (real-estate standard is chest height, not eye height). **Verticals corrected to parallel** with tilt-shift or in post, so there is a slight **stretch at the frame edges**.
  - *Composition:* shot from doorways and corners to show 2–3 walls.
  - *Model:* the viewpoints' `fov: 72` is right. Lower the eye to about 4.5–5 ft and use two-point perspective.
- **Exteriors.**
  - *Ground level:* 24–35 mm at **5–6 ft**, or from a **6–8 ft pole**.
  - *Drone:* **25–40 ft AGL** at 24 mm equivalent, pitched 10–20° down (the `front` reference is this). Drones show **slight lens-profile vignetting** and a **crisper, cooler** image.
- **Aperture and focus.** f/8–f/11, so **everything sharp**. Slight **corner softness** and **lateral chromatic aberration** (thin purple/green fringes on black window frames against bright sky or windows, 1–2 px).
- **Vignetting.** About **0.3–0.5 stop** in the corners (often only partly corrected).
- **Motion.** Shutter about 1/60–1/250 s:
  - **Palm frond tips slightly motion-blurred** in the trades.
  - **Pool water sheet** frozen or slightly silky.
  - **Ceiling fans**: real-estate photographers **turn fans off**. If one is on, blades are a soft disc.
- **Flare.** With the sun in or near the frame (backlit palms, as in the `front` reference), there are **veiling flare, a few ghost polygons along the sun-to-centre line, and lowered contrast** in that quadrant.

### 14.2 Exposure and dynamic range
- **Interiors with daylight.** Real photos are either:
  - (a) **bracketed and blended (HDR / flambient)**: windows held about **1.5–2.5 stops brighter than the walls**, the exterior view **visible but washed, lower contrast and slightly cooler/cyan**, with **halation bloom 5–20 px** around the frame mullions; or
  - (b) single exposure: windows **blown to white with soft roll-off**, the exterior invisible.
  - Never use the CG look where the outside view is as saturated and contrasty as the room.
  - Black frames against bright glass read **thinner** because of the bloom.
- **Interior falloff.** **Light falls off with distance from windows.** The back of the great room (kitchen side, x 40–48) is about **1–1.5 stops darker** than the zone near the lānai pocket door. The T&G vault is **brighter on the slope facing the doors**.
- **Exterior in sun.**
  - White siding in direct sun **just below clipping** (about 240–248 sRGB). The same siding in shade at about **150–175**, i.e. 2–3 stops down, **tinted blue** by the sky.
  - Roofs facing the camera dark, side hips bright (as in the reference).
  - **Eave shadow band** on the walls: hard-edged, 1–3 ft tall depending on sun altitude.
- **Night and twilight** (the classic listing "twilight" shot, 15–25 min after sunset).
  - Sky deep blue (about 7000–9000 K equivalent).
  - Interiors glowing **warm 2700 K amber**.
  - Down-only sconces making **scallops on the siding**.
  - The **pool lit cyan-blue** (or warm white) as the brightest exterior element.
  - Path lights as soft pools.
  - **No uplighting** (§0.2), so palms are silhouettes or faintly lit from the house.
  - **Gecko on the wall** by a sconce.

### 14.3 White balance and colour
- **Mixed white balance.** Interior shots are usually set to about **4500–5000 K**, so the **2700 K lamps and pendants look orange-gold** and the **window light reads slightly blue**. Shadows on the lānai and under the eaves go **cool blue** from the sky.
- **Colour bleeding / bounce that real cameras capture.**
  - **Green cast** on white soffits, the lānai ceiling and the lower exterior walls from the lawn and palms. It is strong in Hawaiʻi: soffits look pale mint.
  - **Warm cast** on the lower white interior walls and ceiling from the oak floor.
  - **Cyan caustic ripple** on the lānai ceiling and primary eave from the pool on sunny afternoons. This is the money detail; it only happens when the pool is in sun and the surface is directly in line.
  - **Pink-magenta bounce** near the bougainvillea.
- **Saturation.** Kauaʻi greens and sky are **genuinely saturated** (the brochure is about 99 on mean S, per the existing audit). Lawn reads yellow-green in sun and blue-green in shade.
  - The **sky gradient** runs from deep blue at the zenith to **pale cyan-white at the horizon** (marine haze).
  - The **ocean** is deep navy-blue near, fading into haze at the horizon with **no hard edge**.
  - **Distant ridges desaturate to blue-grey** (aerial perspective, humid air).
- **Clouds.** **Trade-wind cumulus**: flat bases at about 2,000–3,000 ft, scattered, drifting WSW, banking over the mountains to the north. Often **thin high cirrus streaks**. A **cloud shadow** dappling the golf course or the background canopy sells reality.

### 14.4 Post-processing artefacts of real listing photos
- Slight **HDR haloing** at roof-sky edges.
- **Clarity / sharpening** halos (1 px) on high-contrast edges.
- **Sky replacement** is common, but a real one shows a slight edge mismatch.
- **Lens-corrected barrel distortion** leaves curved frame edges cropped out.
- **Noise:** low ISO is clean; shadow lift shows faint chroma noise in the darkest corners (under the sofa, inside the cabinets).
- **JPEG:** mild compression and 8-bit banding in the smooth sky gradient (add a touch of grain to avoid banding).

---

## Top 40 details that most change whether a viewer believes it's a real photo (ranked)

1. **Physically correct sun and sky for Kukuiʻula at a real date and time** (§0.1 table), with the sun **in front of or beside the camera** for the hero shots (backlit fronds, shadows toward the lens, facades in open shade).
2. **Real exposure behaviour.** Windows 1.5–2.5 stops hot with bloom, interior falloff away from windows, shade faces 2–3 stops under sun faces. No evenly lit "CG flat."
3. **Correct albedos.** White paint 0.80–0.85, lawn about 0.10–0.13, black frames about 0.04. No pure white or pure black anywhere.
4. **Colour bleeding.** Green bounce on soffits and the lānai ceiling, warm oak bounce on interior walls, cyan pool caustics on the lānai ceiling.
5. **Edge bevels and contact shadows** at every junction: 1–3 mm rounds on trim, counters and furniture, plus AO where things meet the floor.
6. **The grade line.** 6–8" of slab and skirt board, a gravel or mow strip, red-dirt splash. Never lawn against siding.
7. **Palms that are the right species, size and age.** Ringed grey foxtail trunks with green crownshafts, fruit, 1–2 dead fronds, and a **WSW wind lean with motion-soft tips**.
8. **Lawn at blade level.** Mower stripes, colour variation, a browner pool-splash band, greener head rings, ragged edges at the mow curbs.
9. **Glass that behaves like glass.** Sky reflections, faint double reflections (insulated units), **half-screens on the lower sashes**, tempered bugs, a few spots and smudges.
10. **Standing-seam roof physics.** Seams running down every slope, **oil-canning wobble** in reflections, same-colour hip caps, hemmed eaves, debris in valleys.
11. **Gutters and corner downspouts**, slim and dark (reference), ending in pop-up emitters, plus rain chains at the courtyard valleys.
12. **Lap siding with butt joints, 6" shadow lines and plane waviness**, with corner boards and frieze in **white** (not black).
13. **Mounting blocks** behind every sconce, outlet and hose bib on the siding.
14. **Exterior utilities in the side views**: AC condensers with disconnects and line-hide, the meter-main and NID on the garage, a hose reel, the pool-equipment screen.
15. **Down-only black cylinder sconces at the right scale** (4½ × 14", centred 7 ft AFG) flanking the garage door and primary slider. Warm and shielded at night.
16. **Rough-sawn cedar with real texture**: saw marks, seasoning checks, mitred cladding joints, **black knife plates and bolt heads**, standoff post bases, tannin streaks.
17. **Shutters as hardware-real pairs**: strap hinges, **shutter dogs**, a ¼" standoff shadow, leaf-to-leaf tone variation.
18. **Fabric physics**: cushions with crowns and creases, pillows chopped, the duvet draping to the floor, curtains puddling, the throw half off.
19. **Water realism**: wind-rippled pool, waterline at mid-tile with a scale line, an **imperfect vanishing-edge sheet** breaking into strands, a foamy catch basin, floating bracts.
20. **Coral-stone variation**: stone-to-stone colour, pores and fossils, weep holes with streaks, algae under the coping.
21. **Interior wall-plate realism**: switches at 48" on latch sides, outlets at 16" between battens, thermostat, smoke alarms near the vault ridge, return grilles, speaker grilles.
22. **Board-and-batten at 16" on centre with caulk lines**, and T&G with staggered butt joints and mitred hip trims.
23. **White-oak floor realism**: 7½" random-length planks, ±10% tone variation, matte sheen variation in raking light.
24. **Zellige backsplash micro-relief** catching dozens of small highlights. Quartz with soft reflections.
25. **Correct object heights and scale**: 8-ft doors, 36" counters, 24–26" stool seats, pendants 30–34" over surfaces, 18" chair seats, lamps 26–28".
26. **Hawaiʻi lived-in cues**: slippers at every door, beach towels over the chair and slat wall, surfboards in the garage, a koa bowl, local fruit, an orchid, an ʻukulele.
27. **Red dirt** on low surfaces: siding base, curbs, grout, the bottom rail of the garage door.
28. **Irrigation hardware visible**: pop-up heads at the lawn edges, valve-box lids, brown drip tubing at bed edges, overspray marks on the walls.
29. **Bougainvillea, ti and plumeria grown the way they really grow**: woody canes on walls, ti clusters of uneven canes with drooping old leaves, candelabra plumeria with fallen flowers and rust spots.
30. **Rug and furniture placement imperfection**: 1–3° off-square, chairs pulled out, a lifted rug corner.
31. **Pocket-door and slider details**: flush sill track lines in the floor, brush-sealed pocket jamb, retractable screen slots, sand in the tracks.
32. **Mixed white balance in interiors**: orange lamps against cool windows, blue lānai shadows.
33. **Atmospheric depth**: haze on the ocean horizon, blue-grey distant ridges, cloud shadows on the golf course.
34. **Lens character**: mild vignetting, 1–2 px CA fringes on black frames, edge stretch from vertical correction, flare when backlit.
35. **Fauna**: chickens on the lawn, nēnē on the fairway, a mynah on the ridge, a gecko by a light.
36. **Mildew and cobwebs** in shaded soffits and corners, and gecko droppings under lights.
37. **Pool and safety furniture**: door alarms at 54", MagnaLatch gates, the barrier fence line glimpsed in the hedges, the skimmer lid and cleaner.
38. **Bathroom truth**: water spots on shower glass, a towel slightly askew, toilet seat down, amber soap pumps, bath mat edges not square.
39. **Neighbourhood truth**: no curb mailbox, no overhead wires, a green transformer and handholes in the shoulder, a shared-design neighbour roof glimpsed through palms. No cloned houses in plain view.
40. **Post-process residue of a real listing photo**: slight HDR haloing, 1-px sharpening, faint shadow noise, a touch of grain to break up sky banding.

---

## Consolidated plan checks (things a real builder would change)

1. **Front viewpoint sun** (58°, 320°) is impossible at 21.9° N. Use June about 3 pm (58°/280°) or about 4 pm (44°/282°). §0.1.
2. **Hall openings to the outdoor Entry** (y 16.09 and y 28.52 at x 50.2–52.3) must be **exterior doors**, not cased openings. §3.2.
3. **Courtyard beds and arecas block both bedroom sliders.** Add 4-ft paved landings and move the planting to the corners. §3.1.
4. **Garage man door has no path** across the ti bed. Add 3 pads. §1.4.
5. **Range run overlaps the pantry cased opening** by about 2.6 ft. Kitchen aisles are 35½"/39" (NKBA 42"). §9.1.
6. **Powder room has no door and is the only route to the Laundry.** The vanity and toilet overlap. §11.4.
7. **Baths 2/3 and the ʻohana bath have high windows directly behind the sinks.** Mirrors need ceiling rods or the windows move. §11.2, §2.2.
8. **ʻOhana bath has no shower** in the furniture list. §2.2.
9. **ʻOhana lānai is 2.66 ft deep.** The chairs don't fit. §2.1.
10. **Nightstands sit in front of 18"-sill windows** (primary, Bedroom 3, ʻohana). §10.1, §11.1.
11. **Bedroom 3 art is hung on the courtyard slider.** §11.1.
12. **Laundry exterior door is 24"**. Make it 2'-8". §4.7.
13. **Lānai beam spans 25'-2"**, so it is a steel or glulam core clad in cedar (mitred), not a solid timber. §7.1.
14. **Brochure seam directions on hip faces are wrong.** Seams always run down the slope. §4.4.
15. **Palms at 30–38 ft** are 15–20 years old. For 12–18 months after completion, use 18–24 ft foxtails. §12.1.

## Where the current renders depart most from real life (from `shots/cycles/*.png`, `shots/lot25/great-room.png`)

- **Exterior.**
  - Roofs read blue-specular and uniform: no oil-canning, hips outlined dark, no gutters or downspouts.
  - **Black corner trims** on the pavilions (real: white corner boards plus one dark downspout).
  - The lawn is a flat plane running into the walls.
  - **Ti planted as rows of identical lollipops.**
  - **Bougainvillea as free-standing mounds** on the lawn.
  - Palms with royal-palm trunks.
  - The vanishing-edge catch basin shows **striped shading artifacts** across the lawn.
  - No utilities, fixtures, mounting blocks, hose bibs or screens.
- **Interior (realtime).**
  - Uniform lighting with no window falloff or bloom.
  - Battens at about 24" and very bright.
  - Planks too wide and uniform.
  - No switches, outlets, vents, alarms or speakers.
  - Pendants floating without canopies or sloped adapters.
  - Upholstery without creases.
  - Rugs perfectly square.
  - No lived-in objects.
