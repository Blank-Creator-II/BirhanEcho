(() => {
  const canvas = document.getElementById("visualizer");
  const ctx = canvas.getContext("2d", { alpha: true });
  const subtitle = document.getElementById("subtitle");
  const TAU = Math.PI * 2;
  const HISTORY_SIZE = 64;
  const history = new Float32Array(HISTORY_SIZE);
  const bassHistory = new Float32Array(HISTORY_SIZE);
  const midHistory = new Float32Array(HISTORY_SIZE);
  const trebleHistory = new Float32Array(HISTORY_SIZE);
  const particles = [];
  const coreParticles = [];
  const stars = [];
  const rays = [];
  let width = 0;
  let height = 0;
  let pixelRatio = 1;
  let historyIndex = 0;
  let targetLevel = 0;
  let level = 0;
  let targetBass = 0;
  let targetMid = 0;
  let targetTreble = 0;
  let bass = 0;
  let mid = 0;
  let treble = 0;
  let previousFrame = 0;

  function makeSphere() {
    const count = 2400;
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i += 1) {
      const y = 1 - 2 * (i + 0.5) / count;
      const radius = Math.sqrt(1 - y * y);
      const angle = goldenAngle * i;
      particles.push({
        x: Math.cos(angle) * radius,
        y,
        z: Math.sin(angle) * radius,
        phase: Math.random() * TAU,
        size: 0.32 + Math.random() * 0.68,
      });
    }

    for (let i = 0; i < 2600; i += 1) {
      const z = Math.random() * 2 - 1;
      const angle = Math.random() * TAU;
      const radius = Math.pow(Math.random(), 0.62) * 0.9;
      const flat = Math.sqrt(1 - z * z) * radius;
      coreParticles.push({
        x: Math.cos(angle) * flat,
        y: z * radius,
        z: Math.sin(angle) * flat,
        phase: Math.random() * TAU,
        speed: 0.55 + Math.random() * 1.4,
        size: 0.35 + Math.random() * 0.85,
        tint: Math.random(),
      });
    }

    for (let i = 0; i < 118; i += 1) {
      rays.push({
        angle: Math.random() * TAU,
        phase: Math.random() * TAU,
        length: 0.035 + Math.random() * 0.11,
        tint: Math.random(),
      });
    }
  }

  function makeStars() {
    stars.length = 0;
    const count = Math.min(180, Math.round(width * height / 8500));
    for (let i = 0; i < count; i += 1) {
      stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        size: 0.35 + Math.random() * 1.15,
        phase: Math.random() * TAU,
        depth: 0.25 + Math.random() * 0.75,
      });
    }
  }

  function resize() {
    pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    makeStars();
  }

  function project(x, y, z, centerX, centerY, radius) {
    const perspective = 1 / (1.65 - z * 0.32);
    return {
      x: centerX + x * radius * perspective,
      y: centerY + y * radius * perspective,
      depth: (z + 1) * 0.5,
    };
  }

  function drawStars(time) {
    ctx.save();
    for (const star of stars) {
      const shimmer = 0.25 + (0.5 + 0.5 * Math.sin(time * 0.0007 + star.phase)) * 0.55;
      ctx.fillStyle = `rgba(174, 218, 255, ${shimmer * star.depth})`;
      ctx.fillRect(star.x, star.y, star.size, star.size);
    }
    ctx.restore();
  }

  function drawAura(centerX, centerY, radius, time, intensity) {
    const auraRadius = radius * (2.05 + intensity * 0.5);
    const aura = ctx.createRadialGradient(centerX, centerY, radius * 0.12, centerX, centerY, auraRadius);
    aura.addColorStop(0, `rgba(102, 202, 255, ${0.08 + intensity * 0.09})`);
    aura.addColorStop(0.38, `rgba(72, 131, 255, ${0.035 + intensity * 0.045})`);
    aura.addColorStop(0.72, "rgba(107, 90, 255, 0.018)");
    aura.addColorStop(1, "rgba(3, 7, 17, 0)");
    ctx.fillStyle = aura;
    ctx.fillRect(centerX - auraRadius, centerY - auraRadius, auraRadius * 2, auraRadius * 2);

    const pulse = 1 + bass * 0.12 + Math.sin(time * 0.0011) * 0.006;
    const shell = ctx.createRadialGradient(
      centerX - radius * 0.35, centerY - radius * 0.42, radius * 0.04,
      centerX, centerY, radius * pulse,
    );
    shell.addColorStop(0, "rgba(177, 235, 255, 0.14)");
    shell.addColorStop(0.34, "rgba(79, 156, 255, 0.055)");
    shell.addColorStop(0.78, "rgba(55, 121, 255, 0.018)");
    shell.addColorStop(0.96, "rgba(177, 228, 255, 0.07)");
    shell.addColorStop(1, "rgba(114, 198, 255, 0)");
    ctx.fillStyle = shell;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * pulse, 0, TAU);
    ctx.fill();

    const heartRadius = radius * (0.48 + bass * 0.32 + intensity * 0.08);
    const heart = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, heartRadius);
    heart.addColorStop(0, `rgba(225, 251, 255, ${0.1 + intensity * 0.21})`);
    heart.addColorStop(0.18, `rgba(113, 214, 255, ${0.045 + intensity * 0.12})`);
    heart.addColorStop(0.58, "rgba(111, 130, 255, 0.025)");
    heart.addColorStop(1, "rgba(91, 124, 255, 0)");
    ctx.fillStyle = heart;
    ctx.beginPath();
    ctx.arc(centerX, centerY, heartRadius, 0, TAU);
    ctx.fill();
  }

  function drawOuterShell(centerX, centerY, radius, time, rotation, intensity) {
    const cosY = Math.cos(rotation * 0.72);
    const sinY = Math.sin(rotation * 0.72);
    const tilt = 0.46;
    const cosX = Math.cos(tilt);
    const sinX = Math.sin(tilt);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const particle of coreParticles) {
      const orbitX = particle.x * 1.25;
      const orbitY = particle.y * 1.25;
      const orbitZ = particle.z * 1.25;
      const curl = time * (0.00072 + particle.speed * 0.00018) + particle.phase;
      const cosCurl = Math.cos(curl);
      const sinCurl = Math.sin(curl);
      const driftX = orbitX * cosCurl - orbitZ * sinCurl;
      const driftZ = orbitX * sinCurl + orbitZ * cosCurl;
      const x = driftX * (1.04 + bass * 0.2);
      const y = orbitY * (1.04 + mid * 0.18);
      const z = driftZ * (1.04 + bass * 0.2);
      const rotatedX = x * cosY + z * sinY;
      const rotatedZ = -x * sinY + z * cosY;
      const rotatedY = y * cosX - rotatedZ * sinX;
      const depthZ = y * sinX + rotatedZ * cosX;
      const point = project(rotatedX, rotatedY, depthZ, centerX, centerY, radius * 1.12);
      const twinkle = 0.5 + 0.5 * Math.sin(time * 0.0016 + particle.phase * 2.4);
      const alpha = (0.2 + treble * 0.36 + intensity * 0.14) * (0.36 + point.depth * 0.66) * twinkle;
      const glow = 0.7 + particle.size * 0.8 + treble * 1.2;
      ctx.fillStyle = `rgba(150, 222, 255, ${Math.min(alpha, 0.96)})`;
      ctx.beginPath();
      ctx.arc(point.x, point.y, glow * 0.62, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawCore(centerX, centerY, radius, time, rotation, intensity) {
    const cosY = Math.cos(rotation * 1.2);
    const sinY = Math.sin(rotation * 1.2);
    const cosX = Math.cos(0.5 + Math.sin(time * 0.00023) * 0.12);
    const sinX = Math.sqrt(1 - cosX * cosX);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const particle of particles) {
      const ripple = Math.sin(time * 0.0017 + particle.phase + particle.y * 8) * 0.09;
      const pulse = 1 + ripple + bass * 0.08 + mid * 0.04;
      const x = particle.x * pulse;
      const y = particle.y * pulse;
      const z = particle.z * pulse;
      const rotatedX = x * cosY + z * sinY;
      const rotatedZ = -x * sinY + z * cosY;
      const rotatedY = y * cosX - rotatedZ * sinX;
      const depthZ = y * sinX + rotatedZ * cosX;
      const point = project(rotatedX, rotatedY, depthZ, centerX, centerY, radius * 0.72);
      const flicker = 0.5 + 0.5 * Math.sin(time * 0.0023 + particle.phase * 4.2);
      const localEnergy = particle.size > 0.78 ? treble : particle.size > 0.52 ? mid : bass;
      const alpha = (0.13 + flicker * 0.25 + localEnergy * 0.6) * (0.52 + point.depth * 0.48);
      const dotSize = (0.3 + flicker * 0.7 + localEnergy * 1.1) * particle.size * 0.84;
      const color = particle.size > 0.8 ? "216, 238, 255"
        : particle.size > 0.52 ? "142, 208, 255" : "104, 169, 255";
      ctx.fillStyle = `rgba(${color}, ${Math.min(alpha, 0.9)})`;
      ctx.beginPath();
      ctx.arc(point.x, point.y, dotSize, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawEnergyRays(centerX, centerY, radius, time, intensity) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const ray of rays) {
      const phase = (time * 0.00016 + ray.phase) % 1;
      const inner = radius * (0.92 + phase * 0.12);
      const localEnergy = ray.tint > 0.9 ? treble : mid;
      const outer = inner + radius * ray.length * (0.18 + localEnergy * 2.2);
      const x1 = centerX + Math.cos(ray.angle) * inner;
      const y1 = centerY + Math.sin(ray.angle) * inner;
      const x2 = centerX + Math.cos(ray.angle) * outer;
      const y2 = centerY + Math.sin(ray.angle) * outer;
      const alpha = (0.035 + localEnergy * 0.42) * (1 - phase * 0.6);
      const color = ray.tint > 0.9 ? "255, 112, 190" : "108, 205, 255";
      const beam = ctx.createLinearGradient(x1, y1, x2, y2);
      beam.addColorStop(0, `rgba(${color}, 0)`);
      beam.addColorStop(0.72, `rgba(${color}, ${alpha})`);
      beam.addColorStop(1, `rgba(221, 248, 255, ${alpha * 0.65})`);
      ctx.strokeStyle = beam;
      ctx.lineWidth = 0.5 + intensity * (ray.tint > 0.9 ? 1.1 : 0.7);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawParticles(centerX, centerY, radius, time, rotation, intensity) {
    const cosY = Math.cos(rotation);
    const sinY = Math.sin(rotation);
    const tilt = 0.27 + Math.sin(time * 0.00018) * 0.08;
    const cosX = Math.cos(tilt);
    const sinX = Math.sin(tilt);
    const projected = [];

    for (const particle of particles) {
      const lag = Math.floor(Math.abs(particle.y) * (HISTORY_SIZE - 1));
      const historyPosition = (historyIndex - lag + HISTORY_SIZE) % HISTORY_SIZE;
      const wave = history[historyPosition];
      const localEnergy = particle.size > 0.78
        ? bassHistory[historyPosition]
        : particle.size > 0.52 ? midHistory[historyPosition] : trebleHistory[historyPosition];
      const ripple = Math.sin(time * 0.0024 + particle.phase + particle.y * 10)
        * (0.012 + mid * 0.025 + treble * 0.018);
      const bassBounce = bass * (0.14 + particle.size * 0.14);
      const waveBounce = wave * (0.08 + particle.size * 0.1);
      const localBounce = localEnergy * (particle.size > 0.78 ? 0.16 : 0.08);
      const displacement = 1 + ripple + bassBounce + waveBounce + localBounce;
      const x = particle.x * displacement;
      const y = particle.y * displacement;
      const z = particle.z * displacement;
      const rotatedX = x * cosY + z * sinY;
      const rotatedZ = -x * sinY + z * cosY;
      const rotatedY = y * cosX - rotatedZ * sinX;
      const depthZ = y * sinX + rotatedZ * cosX;
      const point = project(
        rotatedX,
        rotatedY,
        depthZ,
        centerX,
        centerY,
        radius * (1 + bass * 0.09 + level * 0.035),
      );
      point.depthZ = depthZ;
      point.wave = localEnergy;
      point.size = particle.size;
      projected.push(point);
    }

    projected.sort((a, b) => a.depthZ - b.depthZ);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const point of projected) {
      const alpha = (0.14 + point.depth * 0.48 + point.wave * 0.52) * (0.62 + point.size * 0.38);
      const size = (0.45 + point.depth * 0.9 + point.wave * 1.9) * point.size;
      ctx.fillStyle = `rgba(${point.depth > 0.6 ? "191, 244, 255" : "101, 182, 255"}, ${Math.min(alpha, 0.96)})`;
      ctx.beginPath();
      ctx.arc(point.x, point.y, size, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function draw(time) {
    const elapsed = previousFrame ? Math.min(time - previousFrame, 50) : 16;
    previousFrame = time;
    const smooth = (current, target, attack, release) => current
      + (target - current) * (1 - Math.exp(-elapsed / (target > current ? attack : release)));
    level = smooth(level, targetLevel, 58, 310);
    bass = smooth(bass, targetBass, 38, 290);
    mid = smooth(mid, targetMid, 52, 230);
    treble = smooth(treble, targetTreble, 22, 145);
    historyIndex = (historyIndex + 1) % HISTORY_SIZE;
    history[historyIndex] = level;
    bassHistory[historyIndex] = bass;
    midHistory[historyIndex] = mid;
    trebleHistory[historyIndex] = treble;

    const centerX = width * 0.5;
    const centerY = height * 0.43;
    const radius = Math.min(width, height * 1.15) * 0.23;
    const rotation = time * 0.00018;
    ctx.clearRect(0, 0, width, height);
    drawStars(time);
    ctx.globalCompositeOperation = "lighter";
    drawAura(centerX, centerY, radius, time, level);
    drawOuterShell(centerX, centerY, radius, time, rotation, level);
    drawEnergyRays(centerX, centerY, radius, time, level);
    drawCore(centerX, centerY, radius, time, rotation, level);
    drawParticles(centerX, centerY, radius, time, rotation, level);
    ctx.globalCompositeOperation = "source-over";
    requestAnimationFrame(draw);
  }

  function setSubtitle(text) {
    for (const leaving of subtitle.querySelectorAll(".caption.leaving")) {
      leaving.remove();
    }

    const current = subtitle.querySelector(".caption:not(.leaving)");
    if (current) {
      current.classList.add("leaving");
      window.setTimeout(() => current.remove(), 700);
    }
    if (!text || !text.trim()) return;

    const caption = document.createElement("div");
    caption.className = "caption";
    for (const [index, word] of text.trim().split(/\s+/).entries()) {
      const span = document.createElement("span");
      span.textContent = word;
      span.style.animationDelay = `${Math.min(index * 38, 800)}ms`;
      caption.appendChild(span);
    }
    subtitle.appendChild(caption);
  }

  window.viz = {
    setAudioLevels(overall, low, medium, high) {
      const clamp = (value) => Number.isFinite(Number(value))
        ? Math.max(0, Math.min(1, Number(value))) : 0;
      targetLevel = clamp(overall);
      targetBass = clamp(low);
      targetMid = clamp(medium);
      targetTreble = clamp(high);
    },
    setLevel(value) {
      const next = Number(value);
      targetLevel = Number.isFinite(next) ? Math.max(0, Math.min(1, next)) : 0;
      targetBass = targetMid = targetTreble = targetLevel * 0.65;
    },
    setSubtitle,
  };

  makeSphere();
  resize();
  window.addEventListener("resize", resize, { passive: true });
  requestAnimationFrame(draw);
})();
