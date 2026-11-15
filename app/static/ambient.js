// Moving effects drawn over the calendar. In "weather" mode they follow the current conditions:
// rain, snow, drifting clouds, fog, sun, moon and stars, and blown leaves, all pushed by the real wind.
// The older fixed effects (leaves, snow, petals, bubbles) are still here.
// The canvas ignores touches, so the calendar underneath keeps working.
'use strict';

const Ambient = (() => {
  const LEAF = ['#d9822b', '#c0392b', '#e0a526', '#a8501c', '#8c6b1f'];
  const PETAL = ['#f7b7cf', '#fbd3e0', '#f29bb8'];
  let canvas, ctx, parts = [], running = false, last = 0, signature = '', flash = 0, nextFlash = 0, thunder = false;
  let wind = { dir: 1, mph: 0 };        // dir: +1 blows left to right, -1 right to left
  const sprites = {};
  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = (list) => list[Math.floor(Math.random() * list.length)];
  const unit = () => canvas.height / 1080;   // scales sizes to the panel

  // Soft shapes are painted once onto a small hidden canvas and then stamped, which is easy on a Pi.
  function sprite(name) {
    if (sprites[name]) return sprites[name];
    const c = document.createElement('canvas'), g = c.getContext('2d');
    const blob = (x, y, r, rgb, a) => {
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, `rgba(${rgb},${a})`); grad.addColorStop(1, `rgba(${rgb},0)`);
      g.fillStyle = grad; g.beginPath(); g.arc(x, y, r, 0, 6.3); g.fill();
    };
    if (name === 'cloud' || name === 'storm') {
      c.width = 512; c.height = 256;
      const rgb = name === 'storm' ? '120,132,150' : '205,216,230';
      for (let i = 0; i < 9; i++) blob(110 + i * 36 + rnd(-12, 12), 140 + rnd(-34, 22), rnd(62, 100), rgb, 0.2);
    } else if (name === 'fog') {
      c.width = 512; c.height = 128;
      for (let i = 0; i < 7; i++) blob(70 + i * 62, 64 + rnd(-10, 10), 64, '200,208,216', 0.22);
    } else {
      c.width = c.height = 256;
      const moon = name === 'moon';
      blob(128, 128, 128, moon ? '190,205,235' : '255,205,110', moon ? 0.22 : 0.3);
      blob(128, 128, moon ? 34 : 44, moon ? '235,240,255' : '255,236,170', 0.95);
    }
    return (sprites[name] = c);
  }

  // What to draw for the conditions the server sent.
  function layersFor(effect, wx) {
    if (effect !== 'weather' || !wx) {
      return { leaves: { leaf: 22 }, snow: { snow: 70 }, petals: { petal: 26 }, bubbles: { bubble: 24 } }[effect] || {};
    }
    const sky = wx.sky, night = !wx.is_day, L = {};
    const orb = night ? 'moon' : 'sun';
    if (sky === 'clear') { L[orb] = 1; if (night) L.star = 70; else L.mote = 26; }
    else if (sky === 'partly_cloudy') { L[orb] = 1; L.cloud = 4; if (night) L.star = 35; else L.mote = 10; }
    else if (sky === 'cloudy') L.cloud = 9;
    else if (sky === 'fog') L.fog = 7;
    else if (sky === 'rain') { L.storm = 6; L.rain = Math.round(Math.min(260, 80 + wx.rain_rate * 400)); }
    else if (sky === 'snow') { L.cloud = 5; L.snow = 90; }
    else if (sky === 'thunder') { L.storm = 8; L.rain = 220; }
    if (wx.tags.includes('windy')) L.leaf = 14;
    if (wx.tags.includes('cold')) L.crystal = 40;
    return L;
  }

  function spawn(kind, start) {
    const w = canvas.width, hgt = canvas.height, u = unit();
    const p = { kind, x: rnd(0, w), y: rnd(0, hgt), phase: rnd(0, 6.28), rot: rnd(0, 6.28), vr: rnd(-1, 1), depth: rnd(0.5, 1.2) };
    if (kind === 'leaf') Object.assign(p, { size: rnd(11, 20) * u, color: pick(LEAF), fall: rnd(12, 40) * u, push: rnd(35, 90) * u });
    else if (kind === 'petal') Object.assign(p, { size: rnd(6, 11) * u, color: pick(PETAL), fall: rnd(20, 45) * u, push: rnd(10, 40) * u });
    else if (kind === 'snow') Object.assign(p, { size: rnd(1.5, 4.5) * u, fall: rnd(22, 60) * u });
    else if (kind === 'crystal') Object.assign(p, { size: rnd(1, 2.4) * u, fall: rnd(6, 18) * u });
    else if (kind === 'rain') Object.assign(p, { fall: rnd(850, 1250) * u, len: rnd(16, 30) * u });
    else if (kind === 'bubble') Object.assign(p, { size: rnd(5, 16) * u, fall: -rnd(15, 45) * u });
    else if (kind === 'mote') Object.assign(p, { size: rnd(1.2, 3) * u, fall: rnd(-6, 6) * u });
    else if (kind === 'star') Object.assign(p, { size: rnd(0.8, 2.2) * u });
    else if (kind === 'cloud' || kind === 'storm') Object.assign(p, { size: rnd(420, 760) * u, y: rnd(-0.05, 0.75) * hgt });
    else if (kind === 'fog') Object.assign(p, { size: rnd(900, 1500) * u, y: rnd(0.05, 0.95) * hgt });
    else if (kind === 'sun' || kind === 'moon') Object.assign(p, { size: 230 * u, x: start ? rnd(0.1, 0.9) * w : -230 * u });
    return p;
  }

  // Speed in pixels a second, sideways and downwards. Everything keeps moving even in still air.
  function velocity(p, u) {
    const mph = wind.mph, dir = wind.dir;
    switch (p.kind) {
      case 'rain': return [dir * Math.min(mph * 22, 520) * u, p.fall];
      case 'snow': return [(dir * mph * 7 + Math.sin(p.phase) * 18) * u, p.fall];
      case 'crystal': return [(dir * (4 + mph * 2) + Math.sin(p.phase) * 8) * u, p.fall];
      case 'leaf': return [dir * (p.push + mph * 9 * u) + Math.sin(p.phase) * 18 * u, p.fall];
      case 'petal': return [dir * (p.push + mph * 4 * u) + Math.sin(p.phase) * 18 * u, p.fall];
      case 'bubble': return [Math.sin(p.phase) * 18 * u, p.fall];
      case 'mote': return [dir * (7 + mph * 1.5) * p.depth * u, p.fall + Math.sin(p.phase) * 5 * u];
      case 'star': return [3 * u, 0];
      case 'cloud': case 'storm': return [dir * (9 + mph * 3.2) * p.depth * u, 0];
      case 'fog': return [dir * (6 + mph * 1.5) * p.depth * u, 0];
      default: return [canvas.width / 600, 0];          // sun and moon: across the screen in ten minutes
    }
  }

  function draw(p, u) {
    const k = p.kind;
    if (k === 'cloud' || k === 'storm' || k === 'fog') {
      ctx.globalAlpha = k === 'fog' ? 0.5 : 0.62;
      const img = sprite(k), wide = p.size, tall = wide * img.height / img.width * (k === 'fog' ? 0.9 : 1);
      ctx.drawImage(img, p.x - wide / 2, p.y - tall / 2, wide, tall);
    } else if (k === 'sun' || k === 'moon') {
      const lift = Math.sin(Math.PI * Math.min(1, Math.max(0, p.x / canvas.width)));   // a shallow arc
      ctx.globalAlpha = 0.55;
      ctx.drawImage(sprite(k), p.x - p.size / 2, canvas.height * (0.3 - 0.2 * lift) - p.size / 2, p.size, p.size);
    } else if (k === 'rain') {
      const [vx, vy] = velocity(p, u), n = Math.hypot(vx, vy);
      ctx.globalAlpha = 0.38; ctx.strokeStyle = '#a9d2ff'; ctx.lineWidth = Math.max(1, 1.6 * u);
      ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - vx / n * p.len, p.y - vy / n * p.len); ctx.stroke();
    } else if (k === 'snow') {
      ctx.globalAlpha = 0.85; ctx.fillStyle = '#fff';
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, 6.28); ctx.fill();
    } else if (k === 'star' || k === 'crystal' || k === 'mote') {
      ctx.globalAlpha = (k === 'mote' ? 0.25 : 0.35) + 0.4 * (0.5 + 0.5 * Math.sin(p.phase * (k === 'mote' ? 0.7 : 1.6)));
      ctx.fillStyle = k === 'mote' ? '#ffe2a0' : '#fff';
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, 6.28); ctx.fill();
    } else if (k === 'bubble') {
      ctx.globalAlpha = 0.5; ctx.strokeStyle = '#9fdcff'; ctx.lineWidth = Math.max(1, p.size / 8);
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, 6.28); ctx.stroke();
      ctx.globalAlpha = 0.35; ctx.fillStyle = '#fff';
      ctx.beginPath(); ctx.arc(p.x - p.size * 0.35, p.y - p.size * 0.35, p.size * 0.2, 0, 6.28); ctx.fill();
    } else {                                              // leaf or petal, tumbling
      const s = p.size;
      ctx.save();
      ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.scale(1, k === 'petal' ? 0.55 : 0.6 + 0.4 * Math.sin(p.phase));
      ctx.globalAlpha = 0.8; ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.moveTo(0, -s);
      ctx.bezierCurveTo(s * 0.9, -s * 0.5, s * 0.8, s * 0.6, 0, s);
      ctx.bezierCurveTo(-s * 0.8, s * 0.6, -s * 0.9, -s * 0.5, 0, -s);
      ctx.fill();
      if (k === 'leaf') {
        ctx.strokeStyle = 'rgba(60,30,10,.7)'; ctx.lineWidth = Math.max(1, s / 10);
        ctx.beginPath(); ctx.moveTo(0, -s * 0.8); ctx.lineTo(0, s * 1.35); ctx.stroke();
      }
      ctx.restore();
    }
  }

  function frame(t) {
    if (!running) return;
    requestAnimationFrame(frame);
    if (t - last < 33) return;                       // about 30 frames a second is plenty and is easy on a Pi
    const dt = Math.min(0.1, (t - last) / 1000), w = canvas.width, hgt = canvas.height, u = unit();
    last = t;
    ctx.clearRect(0, 0, w, hgt);
    for (const p of parts) {
      const [vx, vy] = velocity(p, u), edge = (p.size || 20 * u) * 0.6 + 30 * u;
      p.phase += dt * 1.6; p.rot += p.vr * dt;
      p.x += vx * dt; p.y += vy * dt;
      // Off one side: come back in on the other, somewhere new.
      if (p.x > w + edge) { p.x = -edge; if (vy === 0 && p.kind !== 'sun' && p.kind !== 'moon') p.y = spawn(p.kind).y; }
      else if (p.x < -edge) { p.x = w + edge; if (vy === 0) p.y = spawn(p.kind).y; }
      if (p.y > hgt + edge) { p.y = -edge; p.x = rnd(0, w); } else if (p.y < -edge) { p.y = hgt + edge; p.x = rnd(0, w); }
      draw(p, u);
    }
    if (thunder) {                                    // a soft, brief flash now and then
      if (t > nextFlash) { flash = 1; nextFlash = t + rnd(9000, 26000); }
      if (flash > 0.02) { ctx.globalAlpha = 0.16 * flash; ctx.fillStyle = '#dfe8ff'; ctx.fillRect(0, 0, w, hgt); flash *= 0.8; }
    }
    ctx.globalAlpha = 1;
  }

  function resize() { canvas.width = innerWidth; canvas.height = innerHeight; }

  // effect: 'weather', 'leaves', 'snow', 'petals', 'bubbles' or 'off'. wx: the weather from /api/ambient.
  function set(effect, wx) {
    if (!canvas) {
      canvas = document.getElementById('fx');
      ctx = canvas.getContext('2d');
      resize();
      addEventListener('resize', resize);
    }
    if (wx && effect === 'weather') {
      // Wind FROM the west (270) blows left to right. Dead-on north or south wind keeps its last side.
      const side = wx.wind_dir == null ? 0 : -Math.sin(wx.wind_dir * Math.PI / 180);
      wind = { dir: Math.abs(side) < 0.15 ? wind.dir : Math.sign(side), mph: Math.max(wx.wind_mph, wx.gust_mph * 0.6) * Math.max(0.35, Math.abs(side)) };
    } else wind = { dir: 1, mph: 0 };
    const layers = layersFor(effect, wx), next = JSON.stringify(layers);
    thunder = effect === 'weather' && !!wx && wx.sky === 'thunder';
    if (next === signature) return;                   // same scene: only the wind changed
    signature = next;
    const order = ['sun', 'moon', 'star', 'mote', 'cloud', 'storm', 'fog', 'crystal', 'snow', 'rain', 'bubble', 'petal', 'leaf'];
    parts = order.flatMap((kind) => Array.from({ length: layers[kind] || 0 }, () => spawn(kind, true)));
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!parts.length) running = false; else if (!running && !paused) start();
  }

  let paused = false;
  function start() { running = true; last = performance.now(); requestAnimationFrame(frame); }
  function pause() { paused = true; running = false; if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height); }
  function resume() { paused = false; if (parts.length && !running) start(); }

  return { set, pause, resume, layersFor };
})();
