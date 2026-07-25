# Jivo Capability Vocabulary — v1.0-RC (Release Candidate)
## Clusters: precision_metal + polymer_elastomer + shared facets

**Status:** All review decisions from `vocabulary_review_precision_metal_polymer_elastomer.md` implemented. Freeze to v1.0 after the 10-company acceptance test (Part 7).

**Term counts:** precision_metal 71 · polymer_elastomer 39 · shared 10 · search aliases 3 (non-claimable) · watchlist 3. Total claimable: 120.

---

## PART 0 — Schema additions required by this version

Two review recommendations require small `capabilities` table changes (hand to Claude Code with the seed):

```sql
ALTER TABLE capabilities ADD COLUMN is_claimable BOOLEAN DEFAULT TRUE;
ALTER TABLE capabilities ADD COLUMN expands_to TEXT[];  -- for search aliases
-- cluster column now also accepts the value 'shared' (cross-cluster facets)
```

- `is_claimable = FALSE` → term exists for query expansion only; enrichment worker must NEVER assign it; suppliers cannot claim it. `expands_to` lists the canonical child terms a search fans out to.
- `cluster = 'shared'` → facet applies across clusters (volume bands, cleanroom, DFM, core certs). Search UI shows shared facets in every cluster.

---

## PART 1 — Synonym generation rules (applied at seed time)

Systematic rules — apply mechanically when generating INSERTs; per-term synonym lists below carry only the non-derivable ones:

1. **UK/US pairs** for every term: mould/mold, moulding/molding, centre/center, aluminium/aluminum, fibre/fiber, grey/gray. UK spelling is the SEA supplier default.
2. **JIS material grades** on all metal materials: SUS304/SUS316, S45C, SS400, SKD11/SKD61, ADC12, C3604, FC/FCD.
3. **Process/parts noun pairs**: "-ing" ↔ "-ed parts" (deep drawing ↔ deep drawn parts; turning ↔ turned parts; stamping ↔ stamped parts).
4. **Umbrella terms map at cluster/alias level only** — "precision engineering", "CNC machining", "tooling & fabrication" must never be synonyms of a single process term.

---

## PART 2 — Enrichment worker contract (updated)

1. Assign ONLY claimable terms (`is_claimable = TRUE`) from the vocabulary. Never assign search aliases. Never invent terms.
2. Every assignment requires a verbatim evidence quote from the source. No quote → no assignment.
3. Unclassifiable claims → `unmatched[]` array with the raw phrase. Never silently drop.
4. Confidence per assignment: 0.9 explicit + specific (machine list, tonnage) · 0.7 explicit claim · 0.5 strong implication · <0.5 → `unmatched[]`.
5. Generic marketing language ("precision engineering solutions", "one-stop manufacturing") = no assignment.
6. Category discipline: **processes = things a buyer can put on a PO; attributes = things that qualify how the supplier does them.**
7. Cross-cluster boundaries (assign per these rules, note in reasoning):
   - SMC/BMC compression molding → composites_frp, NOT polymer compression molding
   - Plastic machining → precision_metal (cross-listed), not a molding claim
   - Merchant mould/die making → precision_metal tooling terms; a molder's own toolroom → polymer attribute "In-house tooling capability"
   - Dipped latex goods (gloves, balloons) → out of scope entirely
   - Plate rolling (vessels) → process_mechanical, NOT roll forming
8. JSONB parameters only when explicitly stated (Part 6). Never estimate.
9. primary_output per Part 7 decision rules.

---

## PART 3 — CLUSTER: precision_metal (71 terms)

### 3a. Machining (18)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| CNC milling — 3-axis | process | Vertical/horizontal machining of prismatic parts in 3 axes. Baseline milling capability. | machining centre, VMC, vertical machining |
| CNC milling — 4-axis | process | Milling with a rotary 4th axis for multi-face access in one setup (shafts, manifolds). | 4th axis machining, rotary axis milling, HMC |
| CNC milling — 5-axis | process | Simultaneous or 3+2 five-axis milling of complex geometry (impellers, aerospace structures, medtech). | 5ax, five axis machining, simultaneous 5-axis, 3+2 machining |
| CNC turning | process | CNC lathe turning of cylindrical parts, incl. live-tooling lathes. Do NOT assign for Swiss-type sliding-head work. | CNC lathe, turned parts, turning centre |
| Swiss-type turning | process | Sliding-headstock lathes for small-diameter high-precision turned parts, typically Ø ≤ 32 mm. | sliding head lathe, Swiss screw machining, sliding headstock, Citizen/Star machining |
| Mill-turn machining | process | Combined turning + milling in one machine (done-in-one) for complex turned parts. | turn-mill, multitasking machine, Y-axis lathe, done-in-one |
| Wire EDM | process | Wire electrical-discharge cutting. Do NOT assign for sinker EDM. | wire cut, WEDM, wire erosion |
| Sinker EDM | process | Die-sinking/ram EDM with shaped electrodes; common in mold cavity work. | die-sink EDM, ram EDM, spark erosion |
| Surface grinding | process | Precision flat grinding for size, parallelism, finish. | precision grinding, flat grinding |
| Cylindrical grinding | process | OD/ID grinding of shafts, rolls, sleeves. | OD/ID grinding, universal grinding |
| Centerless grinding | process | Thrufeed/infeed centerless grinding of cylindrical parts. | centreless grinding, thrufeed grinding |
| Honing | process | Precision bore finishing for size, roundness, and surface finish (hydraulics, cylinders). Do NOT assign for flat lapping. | bore honing, cylinder honing |
| Lapping & superfinishing | process | Flat/spherical lapping and superfinishing for flatness and sub-micron finish (seals, valve plates, optics). | flat lapping, superfinishing, mirror finishing |
| Deep hole drilling (gundrill / BTA) | process | Drilling of high length-to-diameter holes (>10:1) via gundrilling or BTA. | gun drilling, BTA drilling, deep bore drilling |
| Broaching | process | Keyway, spline, and internal-form broaching. | keyway broaching, spline broaching |
| Gear cutting (hobbing / shaping) | process | Manufacture of gear teeth by hobbing or shaping; typically AGMA 8–10 quality. Do NOT assign for ground gears. | gear hobbing, gear shaping, spline cutting |
| Gear grinding | process | Finish grinding of gear teeth to high AGMA/DIN classes after hardening. Few SEA shops — high discovery value. | ground gears, profile grinding, gear finishing |
| Micromachining | process | Machining of features <0.5 mm or parts <5 mm with micron-level tolerances (medtech, semicon, optics). | micro-milling, miniature parts machining |

### 3b. Sheet metal (11)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Laser cutting (sheet & plate) | process | CO2/fiber laser cutting of sheet and plate; max thickness as parameter. | fiber laser, laser profiling, tube laser cutting |
| Waterjet cutting | process | Abrasive waterjet profiling — thick, heat-sensitive, or non-metal materials. | abrasive waterjet, water jet profiling |
| Plasma cutting | process | HD plasma profiling, mostly heavy plate. Cross-list note: heavy fabricators (process_mechanical) own most plasma tables. | HD plasma, plasma profiling |
| CNC turret punching | process | Turret punching/nibbling of sheet metal; distinguishes high-volume sheet shops from laser-only shops. | turret punch, punch press, punch-laser combo |
| Press brake bending | process | CNC press-brake forming of sheet metal. | CNC bending, sheet metal folding, brake forming |
| Roll forming (profiles) | process | Continuous cold forming of long profiles from coil stock; high-volume linear parts (channels, rails). Do NOT assign for plate rolling (process_mechanical). | cold roll forming, profile forming |
| Tube bending & fabrication | process | CNC/mandrel tube and pipe bending; frames, handrails, fluid lines. Do NOT assign for process piping spools (process_mechanical). | CNC tube bending, mandrel bending, tube fabrication |
| Sheet metal welding | process | TIG/MIG/spot/laser welding of sheet-metal fabrications, incl. cosmetic welds and finishing. | TIG welding, MIG welding, spot welding, GTAW, GMAW, argon welding, laser welding |
| Sheet metal fabrications & assemblies | process | Complete fabricated assemblies: cut, formed, welded, hardware-inserted, finished, assembled to drawing. | fabricated assemblies, weldments, chassis fabrication |
| Hardware insertion (PEM / self-clinching) | process | Automated insertion of self-clinching nuts, studs, standoffs into sheet-metal parts. | PEM insertion, self-clinching hardware, insert pressing |
| Enclosure & cabinet fabrication | process | Build-to-print electrical/electronic enclosures, server chassis, kiosks, cabinets incl. finishing and assembly. Bridge term to electrical_electronic_assembly (box build). | sheet metal enclosures, electrical enclosure fabrication, 19" rack fabrication |

### 3c. Forming (8)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Metal stamping — progressive die | process | Progressive-die stamping for high-volume parts. | progressive stamping, prog die, high-speed stamping |
| Metal stamping — transfer press | process | Transfer-press stamping of larger/complex parts moved between stations. | transfer stamping |
| Deep drawn stampings | process | Deep drawing of cup/shell/enclosure geometries, incl. multi-stage draws. | deep drawing, drawn parts, drawn shells, eyelet drawing |
| Fine blanking | process | Fineblanked parts with sheared-clean edges and flatness. | fineblanking, precision blanking |
| Metal spinning | process | CNC spinning of round hollow parts; low tooling cost. Flow forming is adjacent — note if claimed. | spun metal parts, CNC spinning, flow forming |
| Cold heading & fastener forming | process | Multi-station cold forming of fasteners and net-shape small parts from wire. Do NOT assign for slug-fed cold forging. | cold forming, bolt former, parts former, custom fasteners |
| Thread rolling | process | Cold-forming of external threads by rolling; stronger threads than cutting, high volume. (Moved from Machining — lives in fastener/cold-forming shops.) | rolled threads, thread forming |
| Spring manufacturing & wire forming | process | Compression, extension, torsion springs plus custom wire forms from CNC coilers and formers. | custom springs, wire forms, coiling, flat springs |

### 3d. Casting (6)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| High-pressure die casting (Al / Zn / Mg) | process | HPDC of aluminum, zinc, or magnesium alloys; machine tonnage as parameter, alloy as material facet. | HPDC, pressure die casting, zinc die casting, hot chamber, cold chamber, ADC12 |
| Gravity & low-pressure die casting | process | Permanent-mold casting (gravity or LPDC), typically aluminum; better integrity than HPDC, lower volumes. | permanent mold casting, GDC, LPDC, chill casting |
| Sand casting — iron (grey / ductile) | process | Grey and ductile (SG) iron sand casting; weight range as parameter. | grey iron casting, ductile iron casting, SG iron, FC/FCD, cast iron foundry |
| Sand casting — steel | process | Carbon/alloy/stainless steel sand castings. | steel castings, cast steel foundry |
| Sand casting — non-ferrous (Al / Cu) | process | Aluminum and copper-alloy sand castings, incl. gravity sand. | aluminium sand casting, bronze casting, non-ferrous foundry |
| Investment casting | process | Lost-wax precision casting. | lost wax casting, precision casting |

### 3e. Forging (3)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Closed-die forging (hot) | process | Impression-die hot forging. | drop forging, hot forging |
| Cold forging | process | Cold net-shape forging of components from slugs/billets (gear blanks, races, hubs). Do NOT assign for wire-fed fastener forming (cold heading). | cold extrusion, net-shape forging |
| Open-die forging / ring rolling | process | Free forging, forged bars/blocks, seamless rolled rings (O&G, marine). | seamless rolled rings, free forging |

### 3f. Powder & additive (2)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Metal injection molding (MIM) | process | MIM of small complex high-volume steel/stainless parts: feedstock molding, debinding, sintering. | MIM, powder injection molding |
| Metal additive manufacturing (DMLS / SLM) | process | Laser powder-bed fusion of metal parts (Al, Ti, SS, tool steel), incl. conformal-cooled tooling inserts. | metal 3D printing, DMLS, SLM, LPBF |

### 3g. Tooling (6)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Injection mould design & build | process | Design and manufacture of plastic injection molds as a MERCHANT toolmaker (incl. export tooling). Do NOT assign for a molder's internal toolroom (polymer attribute). | mold making, mould maker, plastic injection tooling, export tooling |
| Stamping die design & build | process | Design and build of stamping/press dies. | press tool making, progressive die build, tool & die maker |
| Die casting die design & build | process | Design and build of HPDC dies (H13/SKD61), incl. thermal design and trim tools. | die casting tooling, die cast mold, casting die maker |
| Jigs, fixtures & gauges | process | Custom workholding, assembly jigs, checking fixtures, gauges built to spec. | checking fixtures, workholding, JF, gauge making |
| Mould & die maintenance, repair & modification | process | Refurbishment, repair, engineering changes, hot-runner service for existing molds/dies incl. transferred tooling. | tooling repair, mold refurbishment, tool transfer support, EC work |
| Mould polishing & finishing | process | High-finish polishing of mould surfaces (mirror/optical, texturing prep). *(Carried from v0.9 — confirm at acceptance test.)* | mirror polishing, mold polishing |

### 3h. Capability attributes (7)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Tight tolerance machining (±0.01 mm) | capability_attribute | Holds ±0.010 mm (approx. IT6) on critical features, with metrology to prove it. | ±10 micron, high precision machining, tight tolerance, ±0.0005 in |
| Ultra-precision machining (≤ ±0.005 mm) | capability_attribute | Sub-5-micron tolerances and/or sub-0.2 µm Ra finishes on critical features. | ±5 micron, sub-micron finishing, ultra precision |
| Max part envelope (parameter) | capability_attribute | Largest workpiece dimensions/weight per process (mm/kg). Powers derived "large part machining" facet. | — |
| Hardened material machining (>45 HRC) | capability_attribute | Milling/turning of hardened steels >45 HRC. | hard turning, hard milling, hardened steel machining |
| In-house metrology (CMM) | capability_attribute | CMM plus supporting metrology (vision, surface, roundness) in-house, reports to drawing. | CMM inspection, coordinate measuring, GD&T inspection |
| PPAP / FAI documentation capability | capability_attribute | PPAP packages (automotive) and FAI/AS9102 reports (aerospace/general) to customer requirements. | AS9102, first article report, ISIR, production part approval |
| Machined assemblies & kitting | capability_attribute | Supplies assembled/kitted machined components (bearings pressed, hardware installed, tested). | sub-assembly, value-added assembly, kitting |

### 3i. Materials (10)

| Term | Key synonyms (JIS rule applies) |
|---|---|
| Carbon & alloy steel | mild steel, S45C, SS400, 4140 |
| Stainless steel | SUS304, SUS316, 17-4PH, duplex (cross-ref process_mechanical) |
| Tool steel | D2, H13, SKD11, SKD61 |
| Cast iron | grey iron, ductile iron, FC250, FCD450 |
| Aluminum alloys | 6061, 7075, ADC12 |
| Copper / brass | bronze, C3604, copper alloys |
| Titanium | Ti-6Al-4V, Grade 5 |
| Nickel superalloys | Inconel 718/625, Hastelloy, Monel, exotic alloy machining |
| Magnesium | AZ91, magnesium die casting |
| Engineering plastics (machining) | plastic machining, Delrin/POM machining, PEEK machining, PTFE/Teflon parts — cross-listed with polymer_elastomer |

---

## PART 4 — CLUSTER: polymer_elastomer (39 terms)

### 4a. Thermoplastic & silicone molding (6)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Plastic injection molding | process | Thermoplastic injection molding of custom parts; tonnage/shot weight as parameters. | injection moulding, plastic molding, custom molder, IM |
| Insert molding | process | Molding around pre-placed metal/plastic inserts (threaded inserts, terminals, stampings). Do NOT assign for post-mold insert pressing. | metal insert molding |
| Overmolding | process | Molding a second material over a previously molded or purchased substrate (soft-touch grips, seals over housings). Sequential process — do NOT assign for one-cycle 2K. | 2-material molding, soft-touch molding |
| Two-shot (2K) molding | process | Multi-material molding in ONE cycle on multi-barrel machines with rotating/core-back tooling. Do NOT assign for sequential overmolding. | 2K molding, dual shot, multi-component molding, bi-injection |
| LSR molding | process | Liquid silicone rubber injection molding, incl. LSR 2K over thermoplastics. Do NOT assign for HCR gum-stock compression work. | liquid silicone molding, silicone injection molding, LSR 2K |
| Micro molding | process | Miniature/micro parts (shot weight <1 g or micro features). *(Carried from v0.9 — confirm at acceptance test.)* | micro moulding, miniature parts |

### 4b. Rubber & elastomer processes (7)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Rubber injection molding | process | Injection molding of elastomer compounds (NR, NBR, EPDM, FKM, HCR silicone) for high-volume flash-minimized precision rubber parts. | rubber injection moulding, injection molded rubber, custom rubber molding |
| Compression molding (rubber / thermoset) | process | Compression molding of rubber compounds and thermosets (phenolic, epoxy). EXCLUDES SMC/BMC (composites_frp). | rubber compression molding, thermoset molding, Bakelite molding, molded rubber parts |
| Transfer molding (rubber / thermoset) | process | Transfer molding of rubber/thermosets for bonded and precision parts. | rubber transfer molding, rubber components |
| Rubber-to-metal bonding | process | Molding rubber chemically bonded to metal inserts — anti-vibration mounts, bushings, bonded seals, rollers. | rubber bonded parts, anti-vibration mounts, bonded rubber bushings |
| Rubber extrusion | process | Extruded rubber profiles, cords, tubing, hoses (EPDM/NBR/silicone), incl. continuous vulcanization and splicing. | extruded rubber profiles, rubber seals extrusion, silicone extrusion, sponge rubber profiles |
| Rubber compounding & material development | process | In-house mixing and custom compound development to spec (hardness, chemical resistance, FDA/UL grades). | custom compounds, internal mixer, banbury, compound development |
| Polyurethane casting (cast PU parts) | process | Cast PU rollers, wheels, wear pads, custom parts incl. PU-to-metal bonding and re-covering. | cast urethane, PU rollers, urethane molding, roller re-lining |

### 4c. Other polymer processes (6)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Plastic profile & tube extrusion | process | Extrusion of thermoplastic profiles, tubes, hoses; co-extrusion as variant. Do NOT assign for rubber extrusion. | plastic extrusion, co-extrusion, PVC profile, tubing extrusion |
| Blow molding | process | Extrusion and injection blow molding of hollow parts (tanks, bottles, ducts). | EBM, ISBM, stretch blow molding |
| Rotational molding | process | Rotomolded large hollow parts (tanks, bins). | rotomolding, roto-molded tanks |
| Thermoforming & vacuum forming | process | Heavy- and thin-gauge thermoforming, vacuum and pressure forming incl. trimming. | vacuum forming, pressure forming, plastic trays, blister/clamshell |
| Vacuum casting (prototyping) | process | Silicone-tool vacuum casting of PU resins for prototype/bridge quantities (1–100 pcs) replicating production plastics. | urethane casting, RTV tooling, bridge production |
| Polymer additive manufacturing (SLA / SLS / FDM / MJF) | process | 3D printing of polymer prototypes and low-volume parts. | plastic 3D printing, SLS nylon, MJF, rapid prototyping |

### 4d. Secondary & assembly (4)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Gasket cutting & fabrication | process | Die-cut, kiss-cut, CNC knife-cut, waterjet-cut gaskets/seals from elastomer, foam, cork, PTFE sheet. | die cutting, gasket fabrication, kiss cutting, waterjet gaskets |
| Plastic welding & joining | process | Ultrasonic, vibration, hot-plate welding, heat staking, solvent/adhesive bonding of molded parts. | ultrasonic welding, hot plate welding, heat staking |
| Printing & decoration (pad / screen / hot stamp / laser) | process | Part decoration: pad printing, silkscreen, hot stamping, laser marking, spray painting. | silk screen, tampo printing, laser marking, spray painting |
| Molded part assembly & value-add | process | Sub- and final assembly of molded parts: inserts, welding, decoration, packing, simple electromechanical assembly. | value-added assembly, pack-out, kitting |

### 4e. Capability attributes (5)

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| In-house tooling capability | capability_attribute | Designs and builds/maintains its own injection molds in-house — faster ECs, single-point accountability. (Moved from processes. Merchant toolmaking = precision_metal.) | in-house tool room, own mold making, tooling in-house |
| Scientific molding & process validation | capability_attribute | DOE-based process development, decoupled molding, IQ/OQ/PQ validation documentation. | IQ OQ PQ, RJG, decoupled molding |
| High-cavitation / multi-cavity molding | capability_attribute | Runs high-cavity tools (16–128+) incl. hot-runner balancing. | multi-cavity, 64-cavity, hot runner molding |
| Prototype / bridge tooling | capability_attribute | Soft/aluminum tooling and low-volume bridge production. *(Carried from v0.9 — confirm at acceptance test.)* | soft tooling, rapid tooling |
| Machine capacity (parameter: tonnage & shot weight) | capability_attribute | Clamping-force range (tonnes) and max shot weight across the fleet. Absorbs former "part size range". Derived facet: large-tonnage molding (≥800T). | — |

### 4f. Materials (7)

| Term | Key synonyms |
|---|---|
| Commodity resins (PP / PE / ABS / PVC / PS) | polypropylene, HDPE, HIPS, rigid PVC |
| Engineering resins (PA / PC / POM / PBT) | nylon, PA6/PA66, glass-filled nylon (GF30), Delrin/acetal, polycarbonate |
| High-performance resins (PEEK / PPS / LCP) | PEI/Ultem, PSU, high-temp plastics |
| TPE / TPU | thermoplastic elastomer, TPV/Santoprene, soft-touch |
| Silicone (LSR / HCR) | HCR silicone (gum stock — distinct from LSR, note in matching), medical grade silicone |
| Synthetic elastomers (NBR / EPDM / FKM / CR) | Viton, Buna-N/nitrile, neoprene, HNBR |
| Natural rubber (NR) | NR, para rubber. Dipped latex goods (gloves, balloons) = different industry, OUT OF SCOPE. |

### 4g. Compliance (cluster-specific, 4)

| Term | Description | Key synonyms |
|---|---|---|
| Food-contact compliance (FDA / EU) | Materials/processes compliant with FDA 21 CFR and EU 10/2011. | food grade, FDA compliant, EU 10/2011 |
| UL-listed materials (UL 94 / yellow card) | Molds UL-recognized flame-rated materials with yellow-card traceability. | UL94 V-0, flame retardant molding |
| Medical biocompatibility (USP Class VI / ISO 10993) | Molds materials with biocompatibility data and lot traceability. | USP Class VI, ISO 10993, medical grade |
| RoHS / REACH compliance | Materials and processes compliant for E&E supply chains. *(Carried from v0.9 — confirm at acceptance test.)* | RoHS compliant, REACH |

---

## PART 5 — SHARED FACETS (cluster = 'shared', 10 terms)

Defined once, attached to every cluster's search UI. Prevents cross-cluster drift.

| Term | Category | Description | Key synonyms |
|---|---|---|---|
| Prototype & one-off capability | capability_attribute | One-offs and prototype quantities. | rapid prototyping, R&D parts, one-off |
| Low-volume production (10–1,000 pcs) | capability_attribute | Series production 10–1,000. | small batch, low volume |
| Mid-volume production (1,000–10,000 pcs) | capability_attribute | Series production 1k–10k — the modal SEA RFQ band. | medium volume, batch production |
| High-volume production (10,000+ pcs/yr) | capability_attribute | Sustained 10k+ annual volumes. | mass production, series production |
| Cleanroom manufacturing & packaging (parameter: ISO class) | capability_attribute | Machining/molding/assembly/cleaning/packing under certified cleanroom (ISO 14644 class as parameter). | cleanroom machining, white room molding, Class 7/Class 8, particle-free packaging |
| DFM & engineering support | capability_attribute | Design-for-manufacture feedback, drawing conversion, tolerance review, cost-down proposals. | DFM feedback, VA/VE, co-engineering |
| ISO 9001 | certification | QMS certification. | — |
| IATF 16949 | certification | Automotive QMS. | TS16949 |
| AS9100 | certification | Aerospace QMS. | AS9100D |
| ISO 13485 | certification | Medical device QMS. | — |

---

## PART 6 — SEARCH ALIASES (is_claimable = FALSE, 3 rows)

Query-side expansion only. The worker NEVER assigns these; suppliers cannot claim them.

| Alias | expands_to |
|---|---|
| CNC machining | CNC milling — 3-axis, CNC milling — 4-axis, CNC milling — 5-axis, CNC turning, Swiss-type turning, Mill-turn machining |
| Precision engineering | (cluster-level: all precision_metal machining terms) |
| Custom rubber molding | Rubber injection molding, Compression molding (rubber / thermoset), Transfer molding (rubber / thermoset), Rubber-to-metal bonding |

---

## PART 7 — Parameter dictionaries (updated)

### precision_metal
| Key | Type | Example | Attach to |
|---|---|---|---|
| max_envelope_mm | int | 500 | milling/grinding |
| max_turning_dia_mm | int | 300 | turning |
| tolerance_mm | decimal | 0.005 | any machining |
| machine_brands / machine_count | string[] / int | ["DMG MORI"] / 12 | any |
| casting_process | string | "HPDC cold chamber" | casting terms |
| press_capacity_tonnes | int | 400 | stamping/forging/HPDC |
| max_sheet_thickness_mm | decimal | 12 | laser/plasma |
| cleanroom_class | string | "ISO 8" | shared cleanroom |

### polymer_elastomer
| Key | Type | Example | Attach to |
|---|---|---|---|
| press_tonnage_min / press_tonnage_max | int | 50 / 1300 | molding terms |
| press_count | int | 24 | molding |
| max_shot_weight_g | int | 3500 | injection molding |
| cavitation_max | int | 64 | high-cavitation |
| cleanroom_class | string | "ISO 7" | shared cleanroom |
| materials_listed | string[] | ["PA66-GF30"] | any |
| tooling_inhouse | bool | true | in-house tooling |

*(primary_output decision rules unchanged from v0.9 Part 6 — moldmaker tiebreak included.)*

---

## PART 8 — WATCHLIST (seeded into unmatched-terms review; demand data decides)

| Candidate term | Trigger to promote |
|---|---|
| Powder metallurgy (press & sinter) | 3+ unmatched supplier claims or buyer searches |
| In-mold labeling / decoration (IML / IMD) | Consumer/appliance OEM buyer segment activates |
| Foam molding & fabrication (EPS / EPP / PU) | Decision that protective packaging is in platform scope |

---

## PART 9 — Acceptance test (final gate before v1.0 freeze)

Unchanged protocol: 10 companies from staging_factlink (5 plastic injection, 5 machining), hand-classified against THIS version. Pass = ≥90% claims classifiable, no repeated hesitation between the same term pair, no missing term needed 3+ times. Specifically confirm the four *carried* items (mould polishing, micro molding, prototype/bridge tooling, RoHS/REACH) earn their place.

### Change log
| Date | Version | Change | By |
|---|---|---|---|
| — | v0.9 | Initial draft, 2 clusters | Claude |
| — | v1.0-RC | Full review implemented: 14 ADDs + restructure (C1), 9 ADDs + rubber rebuild (C4), shared facets, search aliases, synonym rules, watchlist, schema additions (is_claimable, expands_to, cluster='shared') | Liang review + Claude |
| — | v1.0 | FREEZE (pending acceptance test) | — |
