Use your image generation tool to create ONE new image and save it as a PNG at `./out/result.png` (create `out` if needed). Do nothing else.

Attached images:
1. character_reference.png — THE canonical character model. Match its body proportions exactly.
2. original.png — a {GRID} sprite sheet ({ACTION}). Redraw it.
{EXTRA_REFS}
GOAL: The same animation as #2 — keep every frame's pose, body angle, motion, gesture, expression, effects and order EXACTLY as in #2 (do not simplify the motion, do not turn frames into a neutral standing pose). ONLY change the character's proportions/design so the character is the same model as #1.

Proportion corrections measured against #1 (fix these):
{FIXES}
Always:
- Same head-to-body ratio as #1: top of hair to chin = {HEAD_PCT}% of the standing height.
- Hair: same color, volume and silhouette as #1 (not bigger).
- Same outfit as #1 with the same hem length, same boots exactly the same size as #1 (not bigger, not smaller), same weapon.
- Colors: keep the exact colors of #1 for hair, outfit, skin, boots and weapon (same hue, saturation and brightness). No color grading, no tinting, no glow, no rim light or lighting effects.
- Same art style, line weight and shading as #1.
{REQUIRED}

Sheet layout (critical):
- Landscape canvas, exactly {COLS} columns x {ROWS} rows, {FRAMES} frames, evenly spaced.
- Fully transparent background. No floor, shadow, glow, text, numbers or grid lines.
- Each figure stays fully inside its own cell with a transparent gap; nothing (hair, weapon, feet, effects) crosses into a neighboring cell or touches the canvas edge.
- All figures are the same scale; standing frames share one baseline near the bottom of the cell.
