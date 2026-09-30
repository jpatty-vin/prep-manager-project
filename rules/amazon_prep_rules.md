# Prep rules used by this agent (frozen for the evaluation)

Primary source: Amazon Seller Central Help, "Packaging and Prep Requirements" (Amazon India page,
shows MRP labels and metric units).
URL: https://sellercentral.amazon.in/help/hub/reference/external/200141500
Retrieved on: 30 Sep 2026
Marketplace assumption: India. The problem statement does not name a marketplace; a finding has been
raised with the organisers (link the Issue here). If they answer differently, this file is updated BEFORE labeling.
Text below is paraphrased. Rows marked PENDING need a subpage that has not been retrieved yet.
# Prep rules used by this agent (frozen for the evaluation)

Source status: DRAFT from a third-party FBA prep article (not Amazon's own text).
TODO: open Amazon Seller Central "Packaging and prep requirements" and "Barcode requirements",
verify every line below, correct differences, and paste the page URLs here.
Amazon page URLs: TODO
Retrieved on: TODO (date)

## Checks the agent makes (visual only)

| check_key | Applies when | PASS | FAIL | UNCERTAIN |
|---|---|---|---|---|
| polybag_presence | packaging = polybag | unit is inside a bag | no bag | bag not clearly visible |
| polybag_sealing | packaging = polybag | bag fully closed, no open edge | open edge or gap | closure not visible |
| suffocation_warning_presence | polybag AND operator says opening >= 5 in | warning text or icon on the bag | no warning anywhere visible | bag side not shown or photo unclear |
| warning_visibility | a warning is present | fully legible, not hidden by a fold | cut off, folded away or unreadable | too small or blurry to tell |
| fnsku_present | FNSKU (Amazon barcode) is used | an FNSKU label is visible | no FNSKU label visible | label area not shown |
| fnsku_placement | FNSKU used | label on a flat surface, not over a seam, fold, edge, corner or curve | label over a seam, fold, edge, corner or curve | no label visible (absence is judged by fnsku_present) or geometry unclear |
| original_barcode_covered | FNSKU used AND product has an original manufacturer barcode | original barcode covered or not visible | original barcode still visible | cannot tell |
| expiry_date_visible | category = expiry goods | date printed, legible, not covered | date missing, covered or illegible | date area not shown or blurry |
| handling_marks_present | category or client instructions require a mark (fragile, liquid, this way up) | required mark visible and legible | required mark missing | cannot tell |
| box_intact | packaging = glass_box | closed, undamaged, no crushed corners or open flaps | damage or open flaps | not enough of the box visible |
| fragile_marking | packaging = glass_box or category = fragile | fragile mark visible | no fragile mark | cannot tell |

Checks that do not apply are not asked and are not scored.

## Rules from the draft source that the agent does NOT check (not visible in a photo)
- Bag thickness (draft says at least 1.5 mil)
- Bag protrusion beyond the product (draft says no more than 3 in)
- Warning print size by bag dimensions
- Drop-test results for perforated boxes
- Remaining shelf life of more than 90 days (needs the receiving date)
State these limits in the README.

## Labeling rules (both human labelers use exactly this file)
- Label only what is visible in the photos. If you cannot tell, label UNCERTAIN.
- Do not label a check that does not apply. Mark it NA.
- Do not discuss labels with the other labeler until both sheets are committed.