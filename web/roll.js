// Result piano roll: notes coloured by voice, chord labels, sections, playhead.

import { fitCanvas } from "./canvas.js";
import { beatAtSeconds } from "./player.js";

/** Which palette color each harmonic function gets (T home, S away, D tension). */
export const FN_COLOR = { T: "fnHome", S: "fnAway", D: "fnTension", other: "chordNeutral" };
export const MIN_LABEL_PX = 22;

/** One pill per chord span: pixel extent, label, palette key, and whether the label fits. */
export function chordPills(chords, x) {
  return chords.map((ch) => {
    const x0 = x(ch.onset);
    const x1 = x(ch.onset + ch.dur);
    return {
      x0,
      x1,
      label: ch.label,
      colorKey: FN_COLOR[ch.function] ?? FN_COLOR.other,
      showLabel: x1 - x0 >= MIN_LABEL_PX,
    };
  });
}

/** The key under the chord strip: what each color means for this style. */
export function legendItems(style) {
  if (style === "tonal") {
    return [
      { colorKey: "fnHome", text: "Home (I, iii, vi): feels settled" },
      { colorKey: "fnAway", text: "Away (ii, IV, V/V): moving off" },
      { colorKey: "fnTension", text: "Tension (V, V7, vii°): wants to resolve" },
    ];
  }
  return [{ colorKey: "chordNeutral", text: "Each chord moves to a close neighbor on the Tonnetz (P, L, or R)." }];
}

export function drawRoll(canvas, piece, positionS, colors) {
  const ctx = fitCanvas(canvas);
  const W = canvas.clientWidth;
  const H = canvas.clientHeight;
  const c = colors();
  ctx.clearRect(0, 0, W, H);
  if (!piece || !piece.notes.length) return;

  const T = piece.total_beats;
  let lo = Infinity;
  let hi = -Infinity;
  for (const n of piece.notes) {
    lo = Math.min(lo, n.pitch);
    hi = Math.max(hi, n.pitch);
  }
  lo -= 1;
  hi += 1;
  const top = 26;
  const rowH = (H - top) / (hi - lo + 1);
  const x = (beat) => (beat / T) * W;
  const y = (pitch) => top + (hi - pitch) * rowH;

  piece.sections.forEach((s, i) => {
    ctx.fillStyle = i % 2 ? c.band : c.bandAlt;
    ctx.fillRect(x(s.start), 0, x(s.end) - x(s.start), H);
  });

  ctx.font = "10px Roboto, system-ui, sans-serif";
  ctx.textBaseline = "middle";
  for (const pill of chordPills(piece.chords, x)) {
    ctx.globalAlpha = 0.4;
    ctx.fillStyle = c[pill.colorKey];
    ctx.fillRect(pill.x0 + 0.5, 4, Math.max(1, pill.x1 - pill.x0 - 1), 18);
    ctx.globalAlpha = 1;
    if (pill.showLabel) {
      ctx.fillStyle = c.ink;
      ctx.fillText(pill.label, pill.x0 + 4, 13);
    }
  }
  ctx.textBaseline = "alphabetic";

  const voiceColor = Object.fromEntries(piece.voices.map((v, i) => [v.name, c.voices[i % c.voices.length]]));
  for (const n of piece.notes) {
    const sounding = positionS !== null && n.onset_s <= positionS && positionS < n.onset_s + n.dur_s;
    const nx = x(n.onset);
    const nw = Math.max(1.5, x(n.onset + n.dur) - nx);
    const nh = Math.max(1.5, rowH * 0.8);
    ctx.globalAlpha = sounding ? 1 : 0.35 + 0.55 * n.vel;
    ctx.fillStyle = voiceColor[n.voice];
    ctx.fillRect(nx, y(n.pitch), nw, nh);
    if (sounding) {
      ctx.strokeStyle = c.ink;
      ctx.lineWidth = 1;
      ctx.strokeRect(nx, y(n.pitch), nw, nh);
    }
  }
  ctx.globalAlpha = 1;

  if (positionS !== null) {
    const px = x(beatAtSeconds(piece.beat_s, positionS));
    ctx.strokeStyle = c.playhead;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px, 0);
    ctx.lineTo(px, H);
    ctx.stroke();
  }
}
