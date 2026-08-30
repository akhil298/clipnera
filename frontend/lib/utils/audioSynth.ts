// Web Audio API Synthesizer for high-performance zero-latency UI & Video Sound Effects

class SoundEffectsEngine {
  private ctx: AudioContext | null = null;

  private getContext(): AudioContext {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  // Play Whoosh SFX (frequency sweep filtered noise)
  playWhoosh(volume = 0.5) {
    try {
      const ctx = this.getContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const filter = ctx.createBiquadFilter();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(150, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.12);
      osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.28);

      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(400, ctx.currentTime);
      filter.frequency.exponentialRampToValueAtTime(2500, ctx.currentTime + 0.12);
      filter.frequency.exponentialRampToValueAtTime(300, ctx.currentTime + 0.28);

      gain.gain.setValueAtTime(0.01, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(volume * 0.4, ctx.currentTime + 0.1);
      gain.gain.linearRampToValueAtTime(0.001, ctx.currentTime + 0.28);

      osc.connect(filter);
      filter.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  // Play Ding / Cash Bell SFX (harmonic high chime)
  playDing(volume = 0.6) {
    try {
      const ctx = this.getContext();
      const now = ctx.currentTime;
      [1760, 2637, 3520].forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now);

        const decay = 0.45 - idx * 0.1;
        gain.gain.setValueAtTime(volume * (0.3 / (idx + 1)), now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + decay);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + decay);
      });
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  // Play Pop SFX (quick bubble blip)
  playPop(volume = 0.5) {
    try {
      const ctx = this.getContext();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(320, now);
      osc.frequency.exponentialRampToValueAtTime(980, now + 0.06);

      gain.gain.setValueAtTime(volume * 0.5, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.09);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  // Play Sub Drop (deep 808 bass impact)
  playSubDrop(volume = 0.6) {
    try {
      const ctx = this.getContext();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(140, now);
      osc.frequency.exponentialRampToValueAtTime(38, now + 0.45);

      gain.gain.setValueAtTime(volume * 0.7, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.6);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  // Play Glitch SFX
  playGlitch(volume = 0.5) {
    try {
      const ctx = this.getContext();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(800, now);
      osc.frequency.setValueAtTime(220, now + 0.03);
      osc.frequency.setValueAtTime(1200, now + 0.06);
      osc.frequency.setValueAtTime(150, now + 0.09);

      gain.gain.setValueAtTime(volume * 0.4, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.15);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  playEffect(type: 'whoosh' | 'pop' | 'ding' | 'camera_shutter' | 'sub_drop' | 'glitch', volume = 0.6) {
    switch (type) {
      case 'whoosh':
        this.playWhoosh(volume);
        break;
      case 'ding':
      case 'camera_shutter':
        this.playDing(volume);
        break;
      case 'pop':
        this.playPop(volume);
        break;
      case 'sub_drop':
        this.playSubDrop(volume);
        break;
      case 'glitch':
        this.playGlitch(volume);
        break;
    }
  }
}

export const sfxEngine = new SoundEffectsEngine();
