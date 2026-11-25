/* Closer Tech — Joy call button. Stays at the bottom-left of every page. */
(function () {
  "use strict";
  if (document.getElementById("joy-vw-btn")) return;
  const script = document.currentScript;
  const source = new URL(script.src);
  const agent = source.searchParams.get("agent") || "";
  const wsProto = source.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = wsProto + "//" + source.host + "/voice/gemini/live" + (agent ? "?agent=" + encodeURIComponent(agent) : "");
  const INPUT_RATE = 16000;
  const OUTPUT_RATE = 24000;
  const BARGE_RMS = 0.07;

  const css = document.createElement("style");
  css.textContent = `
    #joy-vw-btn{position:fixed;left:20px;bottom:20px;z-index:99999;width:64px;height:64px;border:0;border-radius:50%;
      background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;cursor:pointer;
      box-shadow:0 10px 30px rgba(59,130,246,.45);display:flex;align-items:center;justify-content:center}
    #joy-vw-btn svg{width:28px;height:28px}
    #joy-vw-panel{position:fixed;inset:0;z-index:99998;display:none;
      background:radial-gradient(900px 500px at 50% 20%, rgba(139,92,246,.22), transparent 60%),
        radial-gradient(700px 400px at 50% 100%, rgba(59,130,246,.16), transparent 55%), #07070b;
      color:#fafafa;font-family:Inter,-apple-system,sans-serif}
    #joy-vw-panel.open{display:flex;flex-direction:column}
    #joy-vw-bar{display:flex;align-items:center;justify-content:space-between;padding:22px 28px}
    #joy-vw-bar strong{font-weight:700;letter-spacing:-.03em}
    #joy-vw-x{background:none;border:0;color:#fafafa;font-size:1.2rem;cursor:pointer}
    #joy-vw-stage{flex:1;display:grid;place-items:center;text-align:center}
    #joy-vw-orbwrap{width:320px;height:320px;position:relative;margin:0 auto}
    #joy-vw-wave{width:320px;height:320px}
    #joy-vw-mic{position:absolute;inset:78px;border:0;border-radius:50%;cursor:pointer;
      background:radial-gradient(circle at 35% 30%, #fff, #ddd6fe 16%, #8b5cf6 42%, #1e1b4b 78%);
      box-shadow:0 0 60px rgba(139,92,246,.45)}
    #joy-vw-mic.live{box-shadow:0 0 80px rgba(59,130,246,.7)}
    #joy-vw-name{font-size:28px;letter-spacing:-.03em;margin:18px 0 6px}
    #joy-vw-status{margin:0;color:#a1a1aa}
  `;
  document.head.appendChild(css);

  const btn = document.createElement("button");
  btn.id = "joy-vw-btn";
  btn.type = "button";
  btn.title = "Talk to Joy";
  btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 4h4l2 4-2.5 1.5a12 12 0 0 0 5 5L16 12l4 2v4a2 2 0 0 1-2 2A16 16 0 0 1 2 6a2 2 0 0 1 2-2z"/></svg>';
  document.body.appendChild(btn);

  const panel = document.createElement("div");
  panel.id = "joy-vw-panel";
  panel.innerHTML = `
    <div id="joy-vw-bar"><strong>CLOSER</strong><button id="joy-vw-x" type="button" aria-label="Close">✕</button></div>
    <div id="joy-vw-stage">
      <div>
        <div id="joy-vw-orbwrap">
          <canvas id="joy-vw-wave" width="640" height="640"></canvas>
          <button id="joy-vw-mic" type="button" aria-label="Talk to Joy"></button>
        </div>
        <h1 id="joy-vw-name">Joy</h1>
        <p id="joy-vw-status">Tap the circle to talk</p>
      </div>
    </div>
  `;
  document.body.appendChild(panel);

  let open = false;
  let ws = null;
  let audioContext = null;
  let processor = null;
  let player = null;
  let mediaStream = null;
  let live = false;
  let ring = null;
  let ringRead = 0;
  let ringWrite = 0;
  let ringSamples = 0;
  let primed = false;
  let silentPulls = 0;
  let speaking = false;
  let bargeFrames = 0;
  let level = 0;
  let spin = 0;

  function setStatus(text) {
    document.getElementById("joy-vw-status").textContent = text;
  }
  function bump(amount) { level = Math.min(1, Math.max(level, amount)); }
  const wave = document.getElementById("joy-vw-wave");
  const waveCtx = wave.getContext("2d");
  function drawWave() {
    spin += 0.008;
    const w = wave.width, h = wave.height, cx = w / 2, cy = h / 2;
    waveCtx.clearRect(0, 0, w, h);
    const bars = 72;
    for (let i = 0; i < bars; i++) {
      const angle = (i / bars) * Math.PI * 2 + spin;
      const pulse = 0.45 + 0.55 * Math.abs(Math.sin(i * 0.55 + spin * 4));
      const len = 18 + level * 90 * pulse;
      const inner = 168;
      waveCtx.strokeStyle = "rgba(" + (160 + i) + "," + (140 + (i % 20)) + ",255," + (0.35 + level * 0.55) + ")";
      waveCtx.lineWidth = 4;
      waveCtx.lineCap = "round";
      waveCtx.beginPath();
      waveCtx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
      waveCtx.lineTo(cx + Math.cos(angle) * (inner + len), cy + Math.sin(angle) * (inner + len));
      waveCtx.stroke();
    }
    level *= 0.92;
    requestAnimationFrame(drawWave);
  }
  drawWave();
  function resample(input, inRate, outRate) {
    if (inRate === outRate) return input;
    const ratio = inRate / outRate;
    const length = Math.floor(input.length / ratio);
    const output = new Float32Array(length);
    for (let i = 0; i < length; i++) {
      const position = i * ratio;
      const left = Math.floor(position);
      const right = Math.min(left + 1, input.length - 1);
      const mix = position - left;
      output[i] = input[left] * (1 - mix) + input[right] * mix;
    }
    return output;
  }
  function floatToPcm16(samples) {
    const buffer = new ArrayBuffer(samples.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < samples.length; i++) {
      const value = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(i * 2, value < 0 ? value * 0x8000 : value * 0x7fff, true);
    }
    return buffer;
  }
  function stopPlayback() {
    primed = false;
    speaking = false;
    silentPulls = 0;
    bargeFrames = 0;
    ringRead = 0;
    ringWrite = 0;
    ringSamples = 0;
    if (ring) ring.fill(0);
  }
  function playPcm16(arrayBuffer) {
    if (!audioContext || !ring) return;
    speaking = true;
    if (audioContext.state === "suspended") audioContext.resume();
    const view = new DataView(arrayBuffer);
    const input = new Float32Array(Math.floor(arrayBuffer.byteLength / 2));
    let energy = 0;
    for (let i = 0; i < input.length; i++) {
      input[i] = view.getInt16(i * 2, true) / 32768;
      energy += input[i] * input[i];
    }
    bump(Math.min(1, Math.sqrt(energy / Math.max(1, input.length)) * 8));
    const samples = resample(input, OUTPUT_RATE, audioContext.sampleRate);
    if (!samples.length) return;
    for (let i = 0; i < samples.length; i++) {
      ring[ringWrite] = samples[i];
      ringWrite = (ringWrite + 1) % ring.length;
      if (ringSamples < ring.length) ringSamples += 1;
      else ringRead = (ringRead + 1) % ring.length;
    }
    if (!primed && ringSamples >= Math.floor(audioContext.sampleRate * 0.06)) primed = true;
  }
  function startPlayer() {
    ring = new Float32Array(audioContext.sampleRate * 20);
    player = audioContext.createScriptProcessor(1024, 1, 1);
    player.onaudioprocess = (event) => {
      const output = event.outputBuffer.getChannelData(0);
      if (!primed) { output.fill(0); return; }
      let playedAny = false;
      for (let i = 0; i < output.length; i++) {
        if (ringSamples <= 0) { output[i] = 0; continue; }
        output[i] = ring[ringRead];
        ringRead = (ringRead + 1) % ring.length;
        ringSamples -= 1;
        playedAny = true;
      }
      if (playedAny) { silentPulls = 0; return; }
      silentPulls += 1;
      if (silentPulls < 6) return;
      primed = false;
      speaking = false;
      silentPulls = 0;
      setStatus("Your turn");
    };
    player.connect(audioContext.destination);
  }
  function stopCall() {
    live = false;
    stopPlayback();
    const mic = document.getElementById("joy-vw-mic");
    mic.classList.remove("live");
    setStatus("Tap the circle to talk");
    if (processor) processor.disconnect();
    processor = null;
    if (player) player.disconnect();
    player = null;
    ring = null;
    if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
    if (audioContext) audioContext.close();
    audioContext = null;
    if (ws) ws.close();
    ws = null;
  }
  function startCall() {
    const mic = document.getElementById("joy-vw-mic");
    setStatus("Connecting");
    ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";
    ws.onmessage = async (event) => {
      if (event.data instanceof ArrayBuffer) { playPcm16(event.data); return; }
      const data = JSON.parse(event.data);
      if (data.type === "status" && data.status === "ready" && !live) {
        try {
          mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
          });
          audioContext = new AudioContext();
          await audioContext.resume();
          const sourceNode = audioContext.createMediaStreamSource(mediaStream);
          processor = audioContext.createScriptProcessor(2048, 1, 1);
          processor.onaudioprocess = (audioEvent) => {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            const input = audioEvent.inputBuffer.getChannelData(0);
            let energy = 0;
            for (let i = 0; i < input.length; i++) energy += input[i] * input[i];
            const rms = Math.sqrt(energy / input.length);
            if (!speaking) bump(Math.min(1, rms * 12));
            if (speaking) {
              if (rms < BARGE_RMS) { bargeFrames = 0; return; }
              bargeFrames += 1;
              if (bargeFrames < 2) return;
              stopPlayback();
            }
            ws.send(floatToPcm16(resample(input, audioContext.sampleRate, INPUT_RATE)));
          };
          const mute = audioContext.createGain();
          mute.gain.value = 0;
          sourceNode.connect(processor);
          processor.connect(mute);
          mute.connect(audioContext.destination);
          startPlayer();
          live = true;
          mic.classList.add("live");
          setStatus("Listening");
          ws.send(JSON.stringify({ type: "ready" }));
        } catch (error) {
          setStatus("Microphone blocked");
          ws.close();
        }
      } else if (data.type === "interrupt") {
        stopPlayback();
      } else if (data.type === "error") {
        setStatus(data.message);
      }
    };
    ws.onerror = () => setStatus("Connection failed.");
    ws.onclose = () => { if (live) stopCall(); };
  }

  function showPanel() {
    open = true;
    panel.classList.add("open");
  }
  function hidePanel() {
    open = false;
    panel.classList.remove("open");
    if (live) stopCall();
  }
  window.CloserSpeak = showPanel;
  btn.onclick = () => { if (open) hidePanel(); else showPanel(); };
  document.getElementById("joy-vw-x").onclick = hidePanel;
  document.getElementById("joy-vw-mic").onclick = () => { if (live) stopCall(); else startCall(); };

  if (agent) {
    fetch(source.origin + "/voice/agents/" + encodeURIComponent(agent))
      .then((response) => response.ok ? response.json() : null)
      .then((card) => {
        if (!card) return;
        document.getElementById("joy-vw-name").textContent = card.name;
        btn.title = "Talk to " + card.name;
      })
      .catch(() => {});
  }
})();
