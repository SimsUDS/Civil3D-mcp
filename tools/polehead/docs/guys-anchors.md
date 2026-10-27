# Guys and anchors

Read whenever a pole has down guys, span guys or anchors (most jobs). The generator places them from the spec; these rules decide what goes in the spec and what to check afterwards.

## Pairing (write it down per guy before the spec)

- Trace each guy line on a -r 200 zoom from its attach point to the anchor it ends at. The PDF does not draw anchors to scale and its anchor callouts often sit beside a different anchor: identify each anchor by the callout whose leader or arrow points at it (or the lead written right at it), never by the nearest text. Lines that cross near the bottom are easy to swap: compute each line's x at two heights. (TD2536034 pole 1296855E was drafted with the 7' and 12' anchors swapped this way.)
- Pair guys to anchors exactly as drawn, even when it looks odd. One lead and one anchor: all guys share it.
- Spec `guys[].an` = index into `anchors` AS LISTED (the generator never reorders).
- After the apply, check each guy's end x against its anchor in the verify query (QC item 6).

- Guys on both sides of one pole (QPs left and right, TD2524712 4032107E): anchors on the other side get `gs` in the spec; DG callouts stack per side.
- QUEENS POST `via` indexes the spec's `qp` items AS LISTED.

## Attach rows

- A DG attaches at the row of the equipment in its whole foot (DG @ 37' with a dead end at 37'6" attaches at the dead end row; DG @ 23' at the 23' COMM row); otherwise at its own scale position.
- Two DGs with the same height both attach at that row, even when the PDF draws one lower (planner error; draft as labeled).
- A guy through equipment (XFMR, arm): land DG leader arrows on a clear stretch of the guy, never inside a box.

## Anchors

- Distance from the anchor scale using the SHORTEST lead (drop inches); every other anchor = shortest + 4 units per foot of difference. Two different leads never share an anchor.
- Base line: 2 past the far side of the farthest anchor to 17.5 past the pole on the other side. No anchors: P - 17.5 to P + 17.5.
- Lead dims: horizontal, xLine1 (anchor x, G), xLine2 (P, G), dim lines G - 12, G - 24 (shortest closest); text = true lead.
- Labels: `IN: 1 1/4" 3EYE` (color 90) for new; `EX:` for existing, including anchors the PDF does not prefix (`EX: 1" 3EYE`, `EX: COMM ANCHOR`). Drop `ANCHOR` and the `@ lead` from the label (`EX: 3/4" 2 EYE ANCHOR @ 1'4"` becomes `EX: 3/4" 2EYE`). An anchor the PDF does not label gets NO callout.
- Bearings go after the name: `EX: CATV ANC @ 12' 122°` becomes `EX: CATV ANC 122%%D`.
- Label stack: just above ground, 6 past the farthest anchor: far anchor at G + 1.6, the others from farthest to nearest each at least 8 higher, with leaders (no crossing). Each leader's arrow segment at least 15.1 long (raise 4 at a time until it is). Watch for a low DG callout landing on these labels.

## DG callouts

- Carry their height (`IN: 3/8" DG @ 36'6"`), on the guy side even when the PDF draws them elsewhere, beyond all guys at their height, about 20 clear of the outermost guy.
- Stack top down: first baseline = its attach y - 28, each next at least 30 lower; if the lowest ends below G + 20, lift the whole stack.
- Existing DGs, including unprefixed comm DGs, get `EX:` (`EX: COMM DG @ 19'`). A guy-side callout aimed at a guy without `DG` (`CATV @ 19'1"`) is that guy's DG callout: `EX: CATV DG @ 19'1"`. Fix an obvious missing inch mark (`9/32 DG` becomes `9/32" DG`).
- Leader: arrow on its guy at baseline + 11 (never above attach y - 4), end 2.8 from the text edge facing the guys at baseline + 3, elbow 3 further toward the guys; visible diagonal; leaders never cross. Re-measure the text after any text change (EX to IN changes the width) and re-point end and elbow.

## Span guys

- SG halves only (2E3466 left, 2E3954 right), never mirrored or edited, never the GUY linetype guy. A span guy does not decide the callout side. `share: 1` puts it on the row of the other item at that whole foot.

## SOIL TYPE

- `SOIL TYPE = B` written near the anchors: copy the template SOIL TYPE box (closed DECAL LWPOLYLINE about 53.15 x 11.85 plus SIMPLEX 4.8 text; in the TD2536034 copy box 399C9C top-left 1346.8139, -807.5353, text 399C9D at 1349.6896, -815.5629) under the anchor lead dims: top 8 below the lowest anchor dim line, centered on the pole to farthest anchor span. Edit the text. Not placed by the generator: add it in the fix job.
