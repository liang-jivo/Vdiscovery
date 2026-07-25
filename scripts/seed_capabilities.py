# -*- coding: utf-8 -*-
"""
Seeds the capabilities table from vocabulary_v1_0_RC.md (Parts 3-6).

v2 addition (post-RC): three mould-tooling terms added to precision_metal 3g
(Mould flow simulation, Rubber / compression mould design & build, Mould trial
& sampling). They sit in precision_metal, not polymer_elastomer -- a mould is
machined steel and the tooling group already lives in C1.

Synonym expansion applied mechanically per vocabulary Part 1:
  Rule 1 (UK/US pairs)   -- applied to every term's name + given synonyms.
  Rule 2 (JIS grades)    -- verified already-present in Part 3i; only gap
                             (bare "FC"/"FCD" on Cast iron) added explicitly.
  Rule 3 (-ing / -ed parts noun pairs) -- applied by hand, conservatively:
                             only where grammatically unambiguous and where
                             the derived phrase doesn't collide with a
                             DIFFERENT term's synonym (e.g. skipped the 3
                             grinding sub-types' bare "ground parts", skipped
                             tooling "design & build" service terms, kept
                             sheet-metal vs plastic welding qualified
                             separately as "welded metal parts" / "welded
                             plastic parts" to avoid a cross-cluster collision
                             on bare "welded parts").
"""

import os
import re

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Rule 1: UK/US spelling pairs (bidirectional, whole-word, case-preserving)
# ---------------------------------------------------------------------------
UK_US_PAIRS = [
    ("moulding", "molding"),   # longer pair first so "mould" doesn't need
    ("mould", "mold"),         # special-case handling; \b boundaries already
    ("centre", "center"),      # prevent "mould" from matching inside
    ("aluminium", "aluminum"), # "moulding" (no boundary between d/i).
    ("fibre", "fiber"),
    ("grey", "gray"),
]


def _match_case(source_word, replacement):
    if source_word[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def uk_us_variants(phrase):
    """Return a list of UK/US-swapped variants of `phrase` (possibly empty)."""
    variants = []
    for uk, us in UK_US_PAIRS:
        for pat, repl in ((uk, us), (us, uk)):
            regex = re.compile(r"\b" + re.escape(pat) + r"\b", re.IGNORECASE)
            if regex.search(phrase):
                new_phrase = regex.sub(lambda m: _match_case(m.group(0), repl), phrase)
                if new_phrase.lower() != phrase.lower():
                    variants.append(new_phrase)
    return variants


def expand_synonyms(name, base_synonyms, extra=None):
    """Build the final synonyms string: base list + UK/US variants (of name
    and each base synonym) + any hand-picked `extra` (Rule 3) additions."""
    pool = []

    def add(s):
        s = s.strip()
        if s and s.lower() not in [p.lower() for p in pool]:
            pool.append(s)

    for s in base_synonyms:
        add(s)
    for extra_syn in (extra or []):
        add(extra_syn)

    # UK/US expansion over base synonyms + the canonical name itself
    for s in list(base_synonyms) + [name]:
        for variant in uk_us_variants(s):
            add(variant)

    return ", ".join(pool)


# ---------------------------------------------------------------------------
# Term data: (name, category, description, [base synonyms], [rule-3 extras])
# ---------------------------------------------------------------------------

PRECISION_METAL = [
    # 3a. Machining (18)
    ("CNC milling — 3-axis", "process",
     "Vertical/horizontal machining of prismatic parts in 3 axes. Baseline milling capability.",
     ["machining centre", "VMC", "vertical machining"], []),
    ("CNC milling — 4-axis", "process",
     "Milling with a rotary 4th axis for multi-face access in one setup (shafts, manifolds).",
     ["4th axis machining", "rotary axis milling", "HMC"], []),
    ("CNC milling — 5-axis", "process",
     "Simultaneous or 3+2 five-axis milling of complex geometry (impellers, aerospace structures, medtech).",
     ["5ax", "five axis machining", "simultaneous 5-axis", "3+2 machining"], []),
    ("CNC turning", "process",
     "CNC lathe turning of cylindrical parts, incl. live-tooling lathes. Do NOT assign for Swiss-type sliding-head work.",
     ["CNC lathe", "turned parts", "turning centre"], []),
    ("Swiss-type turning", "process",
     "Sliding-headstock lathes for small-diameter high-precision turned parts, typically Ø ≤ 32 mm.",
     ["sliding head lathe", "Swiss screw machining", "sliding headstock", "Citizen/Star machining"], []),
    ("Mill-turn machining", "process",
     "Combined turning + milling in one machine (done-in-one) for complex turned parts.",
     ["turn-mill", "multitasking machine", "Y-axis lathe", "done-in-one"], []),
    ("Wire EDM", "process",
     "Wire electrical-discharge cutting. Do NOT assign for sinker EDM.",
     ["wire cut", "WEDM", "wire erosion"], []),
    ("Sinker EDM", "process",
     "Die-sinking/ram EDM with shaped electrodes; common in mold cavity work.",
     ["die-sink EDM", "ram EDM", "spark erosion"], []),
    ("Surface grinding", "process",
     "Precision flat grinding for size, parallelism, finish.",
     ["precision grinding", "flat grinding"], ["surface-ground parts"]),
    ("Cylindrical grinding", "process",
     "OD/ID grinding of shafts, rolls, sleeves.",
     ["OD/ID grinding", "universal grinding"], ["OD/ID ground parts"]),
    ("Centerless grinding", "process",
     "Thrufeed/infeed centerless grinding of cylindrical parts.",
     ["centreless grinding", "thrufeed grinding"], ["centerless ground parts"]),
    ("Honing", "process",
     "Precision bore finishing for size, roundness, and surface finish (hydraulics, cylinders). Do NOT assign for flat lapping.",
     ["bore honing", "cylinder honing"], ["honed parts"]),
    ("Lapping & superfinishing", "process",
     "Flat/spherical lapping and superfinishing for flatness and sub-micron finish (seals, valve plates, optics).",
     ["flat lapping", "superfinishing", "mirror finishing"], []),
    ("Deep hole drilling (gundrill / BTA)", "process",
     "Drilling of high length-to-diameter holes (>10:1) via gundrilling or BTA.",
     ["gun drilling", "BTA drilling", "deep bore drilling"], []),
    ("Broaching", "process",
     "Keyway, spline, and internal-form broaching.",
     ["keyway broaching", "spline broaching"], ["broached parts"]),
    ("Gear cutting (hobbing / shaping)", "process",
     "Manufacture of gear teeth by hobbing or shaping; typically AGMA 8–10 quality. Do NOT assign for ground gears.",
     ["gear hobbing", "gear shaping", "spline cutting"], []),
    ("Gear grinding", "process",
     "Finish grinding of gear teeth to high AGMA/DIN classes after hardening. Few SEA shops — high discovery value.",
     ["ground gears", "profile grinding", "gear finishing"], []),
    ("Micromachining", "process",
     "Machining of features <0.5 mm or parts <5 mm with micron-level tolerances (medtech, semicon, optics).",
     ["micro-milling", "miniature parts machining"], ["micromachined parts"]),

    # 3b. Sheet metal (11)
    ("Laser cutting (sheet & plate)", "process",
     "CO2/fiber laser cutting of sheet and plate; max thickness as parameter.",
     ["fiber laser", "laser profiling", "tube laser cutting"], ["laser-cut parts"]),
    ("Waterjet cutting", "process",
     "Abrasive waterjet profiling — thick, heat-sensitive, or non-metal materials.",
     ["abrasive waterjet", "water jet profiling"], ["waterjet-cut parts"]),
    ("Plasma cutting", "process",
     "HD plasma profiling, mostly heavy plate. Cross-list note: heavy fabricators (process_mechanical) own most plasma tables.",
     ["HD plasma", "plasma profiling"], ["plasma-cut parts"]),
    ("CNC turret punching", "process",
     "Turret punching/nibbling of sheet metal; distinguishes high-volume sheet shops from laser-only shops.",
     ["turret punch", "punch press", "punch-laser combo"], ["punched parts"]),
    ("Press brake bending", "process",
     "CNC press-brake forming of sheet metal.",
     ["CNC bending", "sheet metal folding", "brake forming"], ["bent parts"]),
    ("Roll forming (profiles)", "process",
     "Continuous cold forming of long profiles from coil stock; high-volume linear parts (channels, rails). Do NOT assign for plate rolling (process_mechanical).",
     ["cold roll forming", "profile forming"], ["roll-formed parts"]),
    ("Tube bending & fabrication", "process",
     "CNC/mandrel tube and pipe bending; frames, handrails, fluid lines. Do NOT assign for process piping spools (process_mechanical).",
     ["CNC tube bending", "mandrel bending", "tube fabrication"], ["bent tubes"]),
    ("Sheet metal welding", "process",
     "TIG/MIG/spot/laser welding of sheet-metal fabrications, incl. cosmetic welds and finishing.",
     ["TIG welding", "MIG welding", "spot welding", "GTAW", "GMAW", "argon welding", "laser welding"],
     ["welded metal parts"]),
    ("Sheet metal fabrications & assemblies", "process",
     "Complete fabricated assemblies: cut, formed, welded, hardware-inserted, finished, assembled to drawing.",
     ["fabricated assemblies", "weldments", "chassis fabrication"], []),
    ("Hardware insertion (PEM / self-clinching)", "process",
     "Automated insertion of self-clinching nuts, studs, standoffs into sheet-metal parts.",
     ["PEM insertion", "self-clinching hardware", "insert pressing"], []),
    ("Enclosure & cabinet fabrication", "process",
     "Build-to-print electrical/electronic enclosures, server chassis, kiosks, cabinets incl. finishing and assembly. Bridge term to electrical_electronic_assembly (box build).",
     ["sheet metal enclosures", "electrical enclosure fabrication", "19\" rack fabrication"], []),

    # 3c. Forming (8)
    ("Metal stamping — progressive die", "process",
     "Progressive-die stamping for high-volume parts.",
     ["progressive stamping", "prog die", "high-speed stamping"], ["progressive-die stamped parts"]),
    ("Metal stamping — transfer press", "process",
     "Transfer-press stamping of larger/complex parts moved between stations.",
     ["transfer stamping"], ["transfer-stamped parts"]),
    ("Deep drawn stampings", "process",
     "Deep drawing of cup/shell/enclosure geometries, incl. multi-stage draws.",
     ["deep drawing", "drawn parts", "drawn shells", "eyelet drawing"], []),
    ("Fine blanking", "process",
     "Fineblanked parts with sheared-clean edges and flatness.",
     ["fineblanking", "precision blanking"], ["fine-blanked parts"]),
    ("Metal spinning", "process",
     "CNC spinning of round hollow parts; low tooling cost. Flow forming is adjacent — note if claimed.",
     ["spun metal parts", "CNC spinning", "flow forming"], []),
    ("Cold heading & fastener forming", "process",
     "Multi-station cold forming of fasteners and net-shape small parts from wire. Do NOT assign for slug-fed cold forging.",
     ["cold forming", "bolt former", "parts former", "custom fasteners"], []),
    ("Thread rolling", "process",
     "Cold-forming of external threads by rolling; stronger threads than cutting, high volume. (Moved from Machining — lives in fastener/cold-forming shops.)",
     ["rolled threads", "thread forming"], []),
    ("Spring manufacturing & wire forming", "process",
     "Compression, extension, torsion springs plus custom wire forms from CNC coilers and formers.",
     ["custom springs", "wire forms", "coiling", "flat springs"], []),

    # 3d. Casting (6)
    ("High-pressure die casting (Al / Zn / Mg)", "process",
     "HPDC of aluminum, zinc, or magnesium alloys; machine tonnage as parameter, alloy as material facet.",
     ["HPDC", "pressure die casting", "zinc die casting", "hot chamber", "cold chamber", "ADC12"], []),
    ("Gravity & low-pressure die casting", "process",
     "Permanent-mold casting (gravity or LPDC), typically aluminum; better integrity than HPDC, lower volumes.",
     ["permanent mold casting", "GDC", "LPDC", "chill casting"], []),
    ("Sand casting — iron (grey / ductile)", "process",
     "Grey and ductile (SG) iron sand casting; weight range as parameter.",
     ["grey iron casting", "ductile iron casting", "SG iron", "FC/FCD", "cast iron foundry"], []),
    ("Sand casting — steel", "process",
     "Carbon/alloy/stainless steel sand castings.",
     ["steel castings", "cast steel foundry"], []),
    ("Sand casting — non-ferrous (Al / Cu)", "process",
     "Aluminum and copper-alloy sand castings, incl. gravity sand.",
     ["aluminium sand casting", "bronze casting", "non-ferrous foundry"], []),
    ("Investment casting", "process",
     "Lost-wax precision casting.",
     ["lost wax casting", "precision casting"], ["investment cast parts"]),

    # 3e. Forging (3)
    ("Closed-die forging (hot)", "process",
     "Impression-die hot forging.",
     ["drop forging", "hot forging"], ["drop forged parts"]),
    ("Cold forging", "process",
     "Cold net-shape forging of components from slugs/billets (gear blanks, races, hubs). Do NOT assign for wire-fed fastener forming (cold heading).",
     ["cold extrusion", "net-shape forging"], ["cold forged parts"]),
    ("Open-die forging / ring rolling", "process",
     "Free forging, forged bars/blocks, seamless rolled rings (O&G, marine).",
     ["seamless rolled rings", "free forging"], ["open-die forged parts"]),

    # 3f. Powder & additive (2)
    ("Metal injection molding (MIM)", "process",
     "MIM of small complex high-volume steel/stainless parts: feedstock molding, debinding, sintering.",
     ["MIM", "powder injection molding"], ["metal injection molded parts"]),
    ("Metal additive manufacturing (DMLS / SLM)", "process",
     "Laser powder-bed fusion of metal parts (Al, Ti, SS, tool steel), incl. conformal-cooled tooling inserts.",
     ["metal 3D printing", "DMLS", "SLM", "LPBF"], []),

    # 3g. Tooling (9)
    ("Injection mould design & build", "process",
     "Design and manufacture of plastic injection molds as a MERCHANT toolmaker (incl. export tooling). Do NOT assign for a molder's internal toolroom (polymer attribute).",
     ["mold making", "mould maker", "plastic injection tooling", "export tooling"], []),
    ("Stamping die design & build", "process",
     "Design and build of stamping/press dies.",
     ["press tool making", "progressive die build", "tool & die maker"], []),
    ("Die casting die design & build", "process",
     "Design and build of HPDC dies (H13/SKD61), incl. thermal design and trim tools.",
     ["die casting tooling", "die cast mold", "casting die maker"], []),
    ("Jigs, fixtures & gauges", "process",
     "Custom workholding, assembly jigs, checking fixtures, gauges built to spec.",
     ["checking fixtures", "workholding", "JF", "gauge making"], []),
    ("Mould & die maintenance, repair & modification", "process",
     "Refurbishment, repair, engineering changes, hot-runner service for existing molds/dies incl. transferred tooling.",
     ["tooling repair", "mold refurbishment", "tool transfer support", "EC work"], []),
    ("Mould polishing & finishing", "process",
     "High-finish polishing of mould surfaces (mirror/optical, texturing prep). (Carried from v0.9 — confirm at acceptance test.)",
     ["mirror polishing", "mold polishing"], ["polished moulds"]),
    # -- added in vocabulary v2 (a mould is machined steel; tooling lives in C1) --
    ("Mould flow simulation", "process",
     "Numerical simulation of mould filling, packing, warpage, or cooling prior to tool build. Do NOT assign for general structural FEA of the part.",
     ["mold flow analysis", "moldflow", "moldex3d", "filling analysis", "warpage analysis", "CAE mould analysis"], []),
    ("Rubber / compression mould design & build", "process",
     "Design and manufacture of compression, transfer, or rubber injection moulds for elastomer and thermoset parts. Do NOT assign for thermoplastic injection moulds (use Injection mould design & build).",
     ["rubber mould making", "compression tool", "transfer mould", "elastomer tooling", "rubber tooling", "silicone mould making"], []),
    ("Mould trial & sampling", "process",
     "Trial shots to validate a new or modified mould (T0/T1, first-article sampling). Do NOT treat trial capacity as evidence of production moulding.",
     ["T0 trial", "T1 trial", "trial shot", "mould tryout", "tryout", "sampling shots", "first article shots"], []),

    # 3h. Capability attributes (7)
    ("Tight tolerance machining (±0.01 mm)", "capability_attribute",
     "Holds ±0.010 mm (approx. IT6) on critical features, with metrology to prove it.",
     ["±10 micron", "high precision machining", "tight tolerance", "±0.0005 in"], []),
    ("Ultra-precision machining (≤ ±0.005 mm)", "capability_attribute",
     "Sub-5-micron tolerances and/or sub-0.2 µm Ra finishes on critical features.",
     ["±5 micron", "sub-micron finishing", "ultra precision"], []),
    ("Max part envelope (parameter)", "capability_attribute",
     "Largest workpiece dimensions/weight per process (mm/kg). Powers derived \"large part machining\" facet.",
     [], []),
    ("Hardened material machining (>45 HRC)", "capability_attribute",
     "Milling/turning of hardened steels >45 HRC.",
     ["hard turning", "hard milling", "hardened steel machining"], []),
    ("In-house metrology (CMM)", "capability_attribute",
     "CMM plus supporting metrology (vision, surface, roundness) in-house, reports to drawing.",
     ["CMM inspection", "coordinate measuring", "GD&T inspection"], []),
    ("PPAP / FAI documentation capability", "capability_attribute",
     "PPAP packages (automotive) and FAI/AS9102 reports (aerospace/general) to customer requirements.",
     ["AS9102", "first article report", "ISIR", "production part approval"], []),
    ("Machined assemblies & kitting", "capability_attribute",
     "Supplies assembled/kitted machined components (bearings pressed, hardware installed, tested).",
     ["sub-assembly", "value-added assembly", "kitting"], []),

    # 3i. Materials (10) -- category = material
    ("Carbon & alloy steel", "material", None,
     ["mild steel", "S45C", "SS400", "4140"], []),
    ("Stainless steel", "material", None,
     ["SUS304", "SUS316", "17-4PH", "duplex (cross-ref process_mechanical)"], []),
    ("Tool steel", "material", None,
     ["D2", "H13", "SKD11", "SKD61"], []),
    ("Cast iron", "material", None,
     ["grey iron", "ductile iron", "FC250", "FCD450"], ["FC", "FCD"]),
    ("Aluminum alloys", "material", None,
     ["6061", "7075", "ADC12"], []),
    ("Copper / brass", "material", None,
     ["bronze", "C3604", "copper alloys"], []),
    ("Titanium", "material", None,
     ["Ti-6Al-4V", "Grade 5"], []),
    ("Nickel superalloys", "material", None,
     ["Inconel 718/625", "Hastelloy", "Monel", "exotic alloy machining"], []),
    ("Magnesium", "material", None,
     ["AZ91", "magnesium die casting"], []),
    ("Engineering plastics (machining)", "material", None,
     ["plastic machining", "Delrin/POM machining", "PEEK machining", "PTFE/Teflon parts — cross-listed with polymer_elastomer"], []),
]

POLYMER_ELASTOMER = [
    # 4a. Thermoplastic & silicone molding (6)
    ("Plastic injection molding", "process",
     "Thermoplastic injection molding of custom parts; tonnage/shot weight as parameters.",
     ["injection moulding", "plastic molding", "custom molder", "IM"], ["injection molded parts"]),
    ("Insert molding", "process",
     "Molding around pre-placed metal/plastic inserts (threaded inserts, terminals, stampings). Do NOT assign for post-mold insert pressing.",
     ["metal insert molding"], ["insert molded parts"]),
    ("Overmolding", "process",
     "Molding a second material over a previously molded or purchased substrate (soft-touch grips, seals over housings). Sequential process — do NOT assign for one-cycle 2K.",
     ["2-material molding", "soft-touch molding"], ["overmolded parts"]),
    ("Two-shot (2K) molding", "process",
     "Multi-material molding in ONE cycle on multi-barrel machines with rotating/core-back tooling. Do NOT assign for sequential overmolding.",
     ["2K molding", "dual shot", "multi-component molding", "bi-injection"], ["2K molded parts"]),
    ("LSR molding", "process",
     "Liquid silicone rubber injection molding, incl. LSR 2K over thermoplastics. Do NOT assign for HCR gum-stock compression work.",
     ["liquid silicone molding", "silicone injection molding", "LSR 2K"], ["LSR molded parts"]),
    ("Micro molding", "process",
     "Miniature/micro parts (shot weight <1 g or micro features). (Carried from v0.9 — confirm at acceptance test.)",
     ["micro moulding", "miniature parts"], ["micro molded parts"]),

    # 4b. Rubber & elastomer processes (7)
    ("Rubber injection molding", "process",
     "Injection molding of elastomer compounds (NR, NBR, EPDM, FKM, HCR silicone) for high-volume flash-minimized precision rubber parts.",
     ["rubber injection moulding", "injection molded rubber", "custom rubber molding"], ["rubber injection molded parts"]),
    ("Compression molding (rubber / thermoset)", "process",
     "Compression molding of rubber compounds and thermosets (phenolic, epoxy). EXCLUDES SMC/BMC (composites_frp).",
     ["rubber compression molding", "thermoset molding", "Bakelite molding", "molded rubber parts"], []),
    ("Transfer molding (rubber / thermoset)", "process",
     "Transfer molding of rubber/thermosets for bonded and precision parts.",
     ["rubber transfer molding", "rubber components"], ["transfer molded parts"]),
    ("Rubber-to-metal bonding", "process",
     "Molding rubber chemically bonded to metal inserts — anti-vibration mounts, bushings, bonded seals, rollers.",
     ["rubber bonded parts", "anti-vibration mounts", "bonded rubber bushings"], ["rubber-to-metal bonded parts"]),
    ("Rubber extrusion", "process",
     "Extruded rubber profiles, cords, tubing, hoses (EPDM/NBR/silicone), incl. continuous vulcanization and splicing.",
     ["extruded rubber profiles", "rubber seals extrusion", "silicone extrusion", "sponge rubber profiles"], []),
    ("Rubber compounding & material development", "process",
     "In-house mixing and custom compound development to spec (hardness, chemical resistance, FDA/UL grades).",
     ["custom compounds", "internal mixer", "banbury", "compound development"], []),
    ("Polyurethane casting (cast PU parts)", "process",
     "Cast PU rollers, wheels, wear pads, custom parts incl. PU-to-metal bonding and re-covering.",
     ["cast urethane", "PU rollers", "urethane molding", "roller re-lining"], ["cast PU parts"]),

    # 4c. Other polymer processes (6)
    ("Plastic profile & tube extrusion", "process",
     "Extrusion of thermoplastic profiles, tubes, hoses; co-extrusion as variant. Do NOT assign for rubber extrusion.",
     ["plastic extrusion", "co-extrusion", "PVC profile", "tubing extrusion"], ["extruded plastic profiles"]),
    ("Blow molding", "process",
     "Extrusion and injection blow molding of hollow parts (tanks, bottles, ducts).",
     ["EBM", "ISBM", "stretch blow molding"], ["blow molded parts"]),
    ("Rotational molding", "process",
     "Rotomolded large hollow parts (tanks, bins).",
     ["rotomolding", "roto-molded tanks"], []),
    ("Thermoforming & vacuum forming", "process",
     "Heavy- and thin-gauge thermoforming, vacuum and pressure forming incl. trimming.",
     ["vacuum forming", "pressure forming", "plastic trays", "blister/clamshell"], ["thermoformed parts"]),
    ("Vacuum casting (prototyping)", "process",
     "Silicone-tool vacuum casting of PU resins for prototype/bridge quantities (1–100 pcs) replicating production plastics.",
     ["urethane casting", "RTV tooling", "bridge production"], ["vacuum cast parts"]),
    ("Polymer additive manufacturing (SLA / SLS / FDM / MJF)", "process",
     "3D printing of polymer prototypes and low-volume parts.",
     ["plastic 3D printing", "SLS nylon", "MJF", "rapid prototyping"], []),

    # 4d. Secondary & assembly (4)
    ("Gasket cutting & fabrication", "process",
     "Die-cut, kiss-cut, CNC knife-cut, waterjet-cut gaskets/seals from elastomer, foam, cork, PTFE sheet.",
     ["die cutting", "gasket fabrication", "kiss cutting", "waterjet gaskets"], []),
    ("Plastic welding & joining", "process",
     "Ultrasonic, vibration, hot-plate welding, heat staking, solvent/adhesive bonding of molded parts.",
     ["ultrasonic welding", "hot plate welding", "heat staking"], ["welded plastic parts"]),
    ("Printing & decoration (pad / screen / hot stamp / laser)", "process",
     "Part decoration: pad printing, silkscreen, hot stamping, laser marking, spray painting.",
     ["silk screen", "tampo printing", "laser marking", "spray painting"], []),
    ("Molded part assembly & value-add", "process",
     "Sub- and final assembly of molded parts: inserts, welding, decoration, packing, simple electromechanical assembly.",
     ["value-added assembly", "pack-out", "kitting"], []),

    # 4e. Capability attributes (5)
    ("In-house tooling capability", "capability_attribute",
     "Designs and builds/maintains its own injection molds in-house — faster ECs, single-point accountability. (Moved from processes. Merchant toolmaking = precision_metal.)",
     ["in-house tool room", "own mold making", "tooling in-house"], []),
    ("Scientific molding & process validation", "capability_attribute",
     "DOE-based process development, decoupled molding, IQ/OQ/PQ validation documentation.",
     ["IQ OQ PQ", "RJG", "decoupled molding"], []),
    ("High-cavitation / multi-cavity molding", "capability_attribute",
     "Runs high-cavity tools (16–128+) incl. hot-runner balancing.",
     ["multi-cavity", "64-cavity", "hot runner molding"], []),
    ("Prototype / bridge tooling", "capability_attribute",
     "Soft/aluminum tooling and low-volume bridge production. (Carried from v0.9 — confirm at acceptance test.)",
     ["soft tooling", "rapid tooling"], []),
    ("Machine capacity (parameter: tonnage & shot weight)", "capability_attribute",
     "Clamping-force range (tonnes) and max shot weight across the fleet. Absorbs former \"part size range\". Derived facet: large-tonnage molding (≥800T).",
     [], []),

    # 4f. Materials (7) -- category = material
    ("Commodity resins (PP / PE / ABS / PVC / PS)", "material", None,
     ["polypropylene", "HDPE", "HIPS", "rigid PVC"], []),
    ("Engineering resins (PA / PC / POM / PBT)", "material", None,
     ["nylon", "PA6/PA66", "glass-filled nylon (GF30)", "Delrin/acetal", "polycarbonate"], []),
    ("High-performance resins (PEEK / PPS / LCP)", "material", None,
     ["PEI/Ultem", "PSU", "high-temp plastics"], []),
    ("TPE / TPU", "material", None,
     ["thermoplastic elastomer", "TPV/Santoprene", "soft-touch"], []),
    ("Silicone (LSR / HCR)", "material", None,
     ["HCR silicone (gum stock — distinct from LSR, note in matching)", "medical grade silicone"], []),
    ("Synthetic elastomers (NBR / EPDM / FKM / CR)", "material", None,
     ["Viton", "Buna-N/nitrile", "neoprene", "HNBR"], []),
    ("Natural rubber (NR)", "material", None,
     ["NR", "para rubber. Dipped latex goods (gloves, balloons) = different industry, OUT OF SCOPE."], []),

    # 4g. Compliance (4)
    ("Food-contact compliance (FDA / EU)", "certification",
     "Materials/processes compliant with FDA 21 CFR and EU 10/2011.",
     ["food grade", "FDA compliant", "EU 10/2011"], []),
    ("UL-listed materials (UL 94 / yellow card)", "certification",
     "Molds UL-recognized flame-rated materials with yellow-card traceability.",
     ["UL94 V-0", "flame retardant molding"], []),
    ("Medical biocompatibility (USP Class VI / ISO 10993)", "certification",
     "Molds materials with biocompatibility data and lot traceability.",
     ["USP Class VI", "ISO 10993", "medical grade"], []),
    ("RoHS / REACH compliance", "certification",
     "Materials and processes compliant for E&E supply chains. (Carried from v0.9 — confirm at acceptance test.)",
     ["RoHS compliant", "REACH"], []),
]

SHARED = [
    ("Prototype & one-off capability", "capability_attribute",
     "One-offs and prototype quantities.",
     ["rapid prototyping", "R&D parts", "one-off"], []),
    ("Low-volume production (10–1,000 pcs)", "capability_attribute",
     "Series production 10–1,000.",
     ["small batch", "low volume"], []),
    ("Mid-volume production (1,000–10,000 pcs)", "capability_attribute",
     "Series production 1k–10k — the modal SEA RFQ band.",
     ["medium volume", "batch production"], []),
    ("High-volume production (10,000+ pcs/yr)", "capability_attribute",
     "Sustained 10k+ annual volumes.",
     ["mass production", "series production"], []),
    ("Cleanroom manufacturing & packaging (parameter: ISO class)", "capability_attribute",
     "Machining/molding/assembly/cleaning/packing under certified cleanroom (ISO 14644 class as parameter).",
     ["cleanroom machining", "white room molding", "Class 7/Class 8", "particle-free packaging"], []),
    ("DFM & engineering support", "capability_attribute",
     "Design-for-manufacture feedback, drawing conversion, tolerance review, cost-down proposals.",
     ["DFM feedback", "VA/VE", "co-engineering"], []),
    ("ISO 9001", "certification", "QMS certification.", [], []),
    ("IATF 16949", "certification", "Automotive QMS.", ["TS16949"], []),
    ("AS9100", "certification", "Aerospace QMS.", ["AS9100D"], []),
    ("ISO 13485", "certification", "Medical device QMS.", [], []),
]

# Part 6 -- search aliases (is_claimable = FALSE)
ALIASES = [
    ("CNC machining", "precision_metal",
     ["CNC milling — 3-axis", "CNC milling — 4-axis", "CNC milling — 5-axis",
      "CNC turning", "Swiss-type turning", "Mill-turn machining"]),
    ("Precision engineering", "precision_metal",
     [t[0] for t in PRECISION_METAL[:18]]),  # all of 3a Machining
    ("Custom rubber molding", "polymer_elastomer",
     ["Rubber injection molding", "Compression molding (rubber / thermoset)",
      "Transfer molding (rubber / thermoset)", "Rubber-to-metal bonding"]),
]


def build_rows():
    rows = []
    for cluster, terms in [("precision_metal", PRECISION_METAL), ("polymer_elastomer", POLYMER_ELASTOMER), ("shared", SHARED)]:
        for name, category, description, base_syn, extra_syn in terms:
            synonyms = expand_synonyms(name, base_syn, extra_syn)
            rows.append({
                "cluster": cluster,
                "name": name,
                "category": category,
                "description": description,
                "synonyms": synonyms or None,
                "is_claimable": True,
                "expands_to": None,
            })
    for name, cluster, expands_to in ALIASES:
        rows.append({
            "cluster": cluster,
            "name": name,
            "category": "process",
            "description": "Search alias — query-side expansion only, never assigned by the enrichment worker.",
            "synonyms": None,
            "is_claimable": False,
            "expands_to": expands_to,
        })
    return rows


# Idempotent: `name` carries a UNIQUE constraint (capabilities_name_key), so a
# re-run updates the existing row in place instead of inserting a duplicate.
# This makes THIS FILE the source of truth -- a manual edit to any of the
# updated columns in the DB will be reverted the next time the script runs.
INSERT_SQL = """
INSERT INTO capabilities (cluster, name, category, description, synonyms, is_claimable, expands_to)
VALUES (%(cluster)s, %(name)s, %(category)s, %(description)s, %(synonyms)s, %(is_claimable)s, %(expands_to)s)
ON CONFLICT (name) DO UPDATE SET
    cluster      = EXCLUDED.cluster,
    category     = EXCLUDED.category,
    description  = EXCLUDED.description,
    synonyms     = EXCLUDED.synonyms,
    is_claimable = EXCLUDED.is_claimable,
    expands_to   = EXCLUDED.expands_to,
    updated_at   = NOW()
"""


def main():
    load_dotenv()
    rows = build_rows()

    # Pre-flight validation: duplicate names, VARCHAR(1000) overflow
    names_seen = {}
    problems = []
    for r in rows:
        low = r["name"].lower()
        if low in names_seen:
            problems.append(f"DUPLICATE name: {r['name']!r}")
        names_seen[low] = True
        if r["synonyms"] and len(r["synonyms"]) > 1000:
            problems.append(f"synonyms too long ({len(r['synonyms'])} chars) for {r['name']!r}")
        if len(r["name"]) > 255:
            problems.append(f"name too long ({len(r['name'])} chars): {r['name']!r}")

    if problems:
        print("Pre-flight validation FAILED:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    print(f"Pre-flight validation OK: {len(rows)} rows, no duplicates, no length overflows.")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(INSERT_SQL, r)
    conn.close()
    print(f"Upserted {len(rows)} capability rows (insert-or-update on name).")


if __name__ == "__main__":
    main()
