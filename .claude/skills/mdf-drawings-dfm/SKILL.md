---
name: mdf-drawings-dfm
description: Produce machinist drawings and review parts for manufacturability - GD&T, tolerances, materials, process choice (mill, laser, brake, turn), cost drivers. Use in MDF phase 3-4 before anything is sent to a machine shop.
---
# Drawings and DFM  [TIER-B to draw, TIER-A gate review]

## For every custom part
- Choose process: laser + brake (sheet), 3-axis mill (plate/blocks), lathe (shafts/pins), or catalog alternative.
- Datum scheme from function: datums are the surfaces that locate the part in the assembly.
- Tolerance only what the stack-up needs. Default general tolerance ISO 2768-mK. Anything tighter than +/-0.05 mm needs a reason.
- Materials: 6061-T6 / 5083 aluminium, 1018/A36 steel, 17-4/303 stainless where wear or corrosion matters, Delrin/UHMW for product contact where marking is a concern.
- Finish: anodize/black oxide/zinc; product-contact surfaces specified for friction and marking.
- Flag cost drivers: deep pockets, tight internal radii, thin walls, tolerance on non-functional faces, multiple setups.

## Drawing content
Title block, part number matching `part:` in layout/BOM, material, finish, qty, general tolerance, GD&T on functional features, revision.

## Release
Drawings are not released until the chief engineer signs off at G4. Mark every generated drawing DRAFT until then.
