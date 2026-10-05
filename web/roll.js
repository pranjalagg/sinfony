// Result piano roll: notes coloured by voice, chord labels, sections, playhead.

import { fitCanvas } from "./canvas.js";
import { beatAtSeconds } from "./player.js";

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
  const top = 22;
  const rowH = (H - top) / (hi - lo + 1);
  const x = (beat) => (beat / T) * W;
  const y = (pitch) => top + (hi - pitch) * rowH;

  piece.sections.forEach((s, i) => {
    ctx.fillStyle = i % 2 ? c.band : c.bandAlt;
    ctx.fillRect(x(s.start), 0, x(s.end) - x(s.start), H);
  });

  ctx.font = "10px system-ui, sans-serif";
  ctx.fillStyle = c.muted;
  let lastLabel = -Infinity;
  for (const ch of piece.chords) {
    const cx = x(ch.onset) + 3;
    if (cx - lastLabel < 34) continue; // skip labels that would overlap
    ctx.fillText(ch.label, cx, 14);
    lastLabel = cx;
  }

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
