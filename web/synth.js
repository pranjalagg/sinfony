// Web Audio port of sinfony's additive instruments: each note is a few decaying sines.

export const MAX_VOICES = 48;

export function midiToHz(pitch) {
  return 440 * 2 ** ((pitch - 69) / 12);
}

/** One entry per oscillator. Stiff strings sound sharp: f_n = n f0 sqrt(1 + B n^2). */
export function partialList(inst, pitch, sampleRate = 44100) {
  const f0 = midiToHz(pitch);
  const B = inst.inharmonicity || 0;
  const detunes = inst.detune_cents ? [-inst.detune_cents, inst.detune_cents] : [0];
  const out = [];
  for (const [ratio, amp, decay] of inst.partials) {
    const f = f0 * ratio * Math.sqrt(1 + B * ratio * ratio);
    for (const cents of detunes) {
      const freq = f * 2 ** (cents / 1200);
      if (freq < sampleRate / 2) out.push({ freq, amp: amp / detunes.length, decay });
    }
  }
  return out;
}

export function noteLevel(inst, vel) {
  return (inst.gain ?? 1) * vel ** 1.5;
}

/** Exponentially decaying noise (-60 dB at the end), normalized to unit energy. */
export function impulseData(sampleRate, seconds, seed = 1) {
  const n = Math.max(1, Math.floor(seconds * sampleRate));
  const data = new Float32Array(n);
  let s = seed >>> 0 || 1;
  let energy = 0;
  for (let i = 0; i < n; i++) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0; // linear congruential generator
    data[i] = (s / 2 ** 31 - 1) * Math.exp((-6.91 * i) / n);
    energy += data[i] * data[i];
  }
  const norm = 1 / Math.sqrt(energy || 1);
  for (let i = 0; i < n; i++) data[i] *= norm;
  return data;
}

/** At the voice cap, the oldest voice still sounding at `when`; otherwise null. */
export function voiceToSteal(voices, when, max = MAX_VOICES) {
  const sounding = voices.filter((v) => v.start <= when && v.end > when);
  if (sounding.length < max) return null;
  return sounding.reduce((a, b) => (b.start < a.start ? b : a));
}

export class Synth {
  constructor(ctx) {
    this.ctx = ctx;
    this.input = ctx.createGain();
    this.dry = ctx.createGain();
    this.wet = ctx.createGain();
    this.convolver = ctx.createConvolver();
    this.convolver.normalize = false;
    this.limiter = ctx.createDynamicsCompressor();
    this.limiter.threshold.value = -6;
    this.limiter.knee.value = 0;
    this.limiter.ratio.value = 20;
    this.limiter.attack.value = 0.003;
    this.limiter.release.value = 0.1;
    this.master = ctx.createGain();
    this.master.gain.value = 0.5;
    this.input.connect(this.dry).connect(this.limiter);
    this.input.connect(this.convolver).connect(this.wet).connect(this.limiter);
    this.limiter.connect(this.master).connect(ctx.destination);
    this.noise = this._noiseBuffer();
    this.voices = [];
    this.setReverb({ seconds: 1.5, mix: 0.25 });
  }

  _noiseBuffer() {
    const data = impulseData(this.ctx.sampleRate, 0.1, 7).map((v, i, a) => v / Math.exp((-6.91 * i) / a.length));
    const buf = this.ctx.createBuffer(1, data.length, this.ctx.sampleRate);
    buf.getChannelData(0).set(data);
    return buf;
  }

  setReverb({ seconds, mix }) {
    const on = seconds > 0;
    if (on) {
      const data = impulseData(this.ctx.sampleRate, seconds);
      const buf = this.ctx.createBuffer(1, data.length, this.ctx.sampleRate);
      buf.getChannelData(0).set(data);
      this.convolver.buffer = buf;
    }
    this.wet.gain.value = on ? mix : 0;
    this.dry.gain.value = on ? 1 - mix : 1;
  }

  noteOn(inst, pitch, vel, when, dur) {
    const ctx = this.ctx;
    this.voices = this.voices.filter((v) => !v.stopped && v.end > ctx.currentTime);
    voiceToSteal(this.voices, when)?.stop(when);

    const level = noteLevel(inst, vel);
    const end = when + dur;
    const out = ctx.createGain();
    out.gain.setValueAtTime(level, when);
    out.gain.setValueAtTime(level, end);
    out.gain.linearRampToValueAtTime(0, end + inst.release);
    out.connect(this.input);

    const sources = [];
    const attack = Math.max(inst.attack, 0.001);
    for (const p of partialList(inst, pitch, ctx.sampleRate)) {
      const osc = ctx.createOscillator();
      osc.frequency.value = p.freq;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0, when);
      g.gain.linearRampToValueAtTime(p.amp, when + attack);
      if (p.decay > 0) g.gain.setTargetAtTime(0, when + attack, 1 / p.decay);
      osc.connect(g).connect(out);
      osc.start(when);
      osc.stop(end + inst.release + 0.05);
      sources.push(osc);
    }
    if (inst.hammer > 0) {
      const src = ctx.createBufferSource();
      src.buffer = this.noise;
      const lp = ctx.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 3000;
      const g = ctx.createGain();
      g.gain.setValueAtTime(inst.hammer, when);
      g.gain.setTargetAtTime(0, when, 0.004);
      src.connect(lp).connect(g).connect(out);
      src.start(when);
      src.stop(when + 0.1);
      sources.push(src);
    }
    const handle = { start: when, end: end + inst.release, out, sources, stopped: false };
    handle.stop = (at) => this._stop(handle, at);
    this.voices.push(handle);
    return handle;
  }

  _stop(h, at) {
    if (h.stopped) return;
    h.stopped = true;
    const t = Math.max(at, this.ctx.currentTime);
    if (h.start >= t) {
      for (const s of h.sources) {
        try { s.stop(); } catch { /* already stopped */ }
      }
      h.out.disconnect();
      return;
    }
    h.out.gain.cancelScheduledValues(t);
    h.out.gain.setValueAtTime(h.out.gain.value, t);
    h.out.gain.linearRampToValueAtTime(0, t + 0.05);
    for (const s of h.sources) {
      try { s.stop(t + 0.06); } catch { /* already stopped */ }
    }
  }

  cancelAfter(t) {
    for (const v of this.voices) if (v.start > t) v.stop(t);
  }

  stopAll(at) {
    for (const v of this.voices) v.stop(at);
    this.voices = [];
  }
}
