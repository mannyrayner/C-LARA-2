/* Human microphone capture only. No audio leaves the browser here. */
(() => {
  'use strict';
  window.CommunityRecorder = function (root, onFile) {
    const record = root.querySelector('[data-record]');
    const check = root.querySelector('[data-check-mic]');
    const devices = root.querySelector('[data-microphone]');
    const state = root.querySelector('[data-record-state]');
    const notice = root.querySelector('[data-record-notice]');
    const using = root.querySelector('[data-microphone-name]');
    const meter = root.querySelector('[data-mic-level]');
    const level = root.querySelector('[data-mic-level-text]');
    const preferenceKey = 'clara-community-microphone';
    let mode = 'idle', stream, context, source, analyser, mute, recorder;
    let tick, deadline, started = 0, heardSound = false, readings = 0, abandoned = false;
    let preferred = '';
    try { preferred = localStorage.getItem(preferenceKey) || ''; } catch (_) { /* Optional preference. */ }

    function message(text, warning = true) {
      notice.textContent = text;
      notice.hidden = !text;
      notice.classList.toggle('error', warning);
    }
    function controls() {
      record.disabled = !['idle', 'checking', 'recording'].includes(mode);
      record.textContent = mode === 'recording' ? '■ Stop recording' : '● Record';
      record.classList.toggle('recording-now', mode === 'recording');
      check.disabled = !['idle', 'checking'].includes(mode);
      check.textContent = mode === 'checking' ? 'Stop microphone check' : 'Check microphone';
      devices.disabled = mode !== 'idle';
    }
    async function listDevices(activeId = '') {
      if (!navigator.mediaDevices?.enumerateDevices) return;
      try {
        const inputs = (await navigator.mediaDevices.enumerateDevices()).filter(item => item.kind === 'audioinput');
        const selected = activeId || devices.value || preferred;
        devices.replaceChildren(new Option('Browser default microphone', ''));
        inputs.forEach((item, i) => {
          if (item.deviceId) devices.add(new Option(item.label || `Microphone ${i + 1}`, item.deviceId));
        });
        if (inputs.some(item => item.deviceId === selected)) devices.value = selected;
      } catch (_) { /* Recording can still work when enumeration is unavailable. */ }
    }
    devices.addEventListener('change', () => {
      preferred = devices.value;
      try { localStorage.setItem(preferenceKey, preferred); } catch (_) { /* Optional preference. */ }
      using.textContent = 'Use Check microphone to test this input.';
    });
    function explanation(error) {
      if (['NotAllowedError', 'SecurityError'].includes(error.name)) return 'Microphone access was not allowed. Check microphone permissions in the browser site settings and on your device, then try again.';
      if (['NotFoundError', 'OverconstrainedError'].includes(error.name)) return 'The selected microphone is unavailable. Choose another input or reconnect it, then check again.';
      if (error.name === 'NotReadableError') return 'The microphone could not be opened. Close other recording or calling apps, then try again or choose another microphone.';
      return 'Recording could not start. Check the selected microphone, or choose an existing audio file.';
    }
    async function release() {
      clearInterval(tick); clearTimeout(deadline);
      if (stream) stream.getTracks().forEach(track => track.stop());
      stream = null;
      if (source) source.disconnect();
      if (analyser) analyser.disconnect();
      if (mute) mute.disconnect();
      const oldContext = context;
      context = source = analyser = mute = null;
      if (oldContext && oldContext.state !== 'closed') {
        try { await oldContext.close(); } catch (_) { /* Tracks are already stopped. */ }
      }
      meter.value = 0;
    }
    function sample() {
      if (!analyser || context.state !== 'running') {
        level.textContent = 'Input meter unavailable; listen to the finished recording.';
        return;
      }
      const data = new Float32Array(analyser.fftSize);
      analyser.getFloatTimeDomainData(data);
      const rms = Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length);
      readings += 1;
      if (rms > 0.00005) heardSound = true;
      meter.value = rms ? Math.max(0, Math.min(1, (20 * Math.log10(rms) + 60) / 60)) : 0;
      level.textContent = rms > 0.00005 ? 'Sound detected' : 'No sound detected — speak into the microphone.';
    }
    function watch() {
      clearInterval(tick);
      tick = setInterval(() => {
        sample();
        if (mode === 'recording') state.textContent = `Recording… ${Math.floor((Date.now() - started) / 1000)} s`;
      }, 100);
    }
    async function openMicrophone() {
      // Create/resume within the button gesture; an unavailable meter must not block capture.
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        context = new AudioContext();
        context.resume().catch(() => {});
      } catch (_) { /* Recording can work without Web Audio. */ }
      const audio = {echoCancellation: false, noiseSuppression: false, autoGainControl: false};
      if (devices.value) audio.deviceId = {exact: devices.value};
      stream = await navigator.mediaDevices.getUserMedia({audio});
      if (abandoned) { await release(); return false; }
      const track = stream.getAudioTracks()[0];
      using.textContent = `Using: ${track.label || 'browser default microphone'}`;
      await listDevices(track.getSettings().deviceId);
      if (abandoned) { await release(); return false; }
      track.addEventListener('ended', () => {
        message('The microphone disconnected. Reconnect it or choose another input.');
        if (mode === 'recording') stopRecording();
        else if (mode === 'checking') stopCheck();
      });
      try {
        source = context.createMediaStreamSource(stream);
        analyser = context.createAnalyser();
        analyser.fftSize = 2048;
        mute = context.createGain();
        mute.gain.value = 0; // Process the meter without playing the microphone through speakers.
        source.connect(analyser); analyser.connect(mute); mute.connect(context.destination);
      } catch (_) {
        level.textContent = 'Input meter unavailable; listen before sharing.';
      }
      heardSound = false; readings = 0;
      watch();
      return true;
    }
    function supported() {
      if (navigator.mediaDevices?.getUserMedia && window.MediaRecorder) return true;
      message('Recording needs a supported browser and HTTPS (or localhost). You can choose an existing audio file instead.');
      return false;
    }
    async function stopCheck() {
      mode = 'finishing'; controls();
      const heard = heardSound;
      const measured = readings > 0;
      await release();
      mode = 'idle'; controls();
      state.textContent = 'Microphone check finished';
      if (measured) message(heard ? 'Sound reached the microphone. Choose Record when ready.' : 'No sound reached this input. Choose another microphone and check again. Check any mute switch and your device’s microphone settings.', !heard);
    }
    check.addEventListener('click', async () => {
      if (mode === 'checking') { await stopCheck(); return; }
      if (mode !== 'idle' || !supported()) return;
      mode = 'opening'; controls(); message('');
      state.textContent = 'Waiting for microphone permission…';
      try {
        if (!await openMicrophone()) return;
        mode = 'checking'; controls();
        state.textContent = 'Microphone check — speak normally';
        deadline = setTimeout(stopCheck, 30000);
      } catch (error) {
        await release(); mode = 'idle'; controls();
        state.textContent = 'Microphone check could not start'; message(explanation(error));
      }
    });
    function newRecorder() {
      // Prefer an explicit codec. Bare MP4 selected Opus-in-MP4 on one Windows browser.
      const formats = ['audio/mp4;codecs=mp4a.40.2', 'audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm', 'audio/mp4'];
      for (const mimeType of formats) {
        if (!MediaRecorder.isTypeSupported(mimeType)) continue;
        try { return new MediaRecorder(stream, {mimeType}); } catch (_) { /* Try the next supported format. */ }
      }
      return new MediaRecorder(stream);
    }
    function stopRecording() {
      if (mode !== 'recording') return;
      sample(); mode = 'finishing'; controls();
      state.textContent = 'Checking your recording…';
      clearTimeout(deadline);
      if (recorder.state !== 'inactive') recorder.stop();
    }
    async function finish(parts, mimeType, failed) {
      const measured = readings > 0, inputWasHeard = heardSound;
      clearInterval(tick);
      stream?.getTracks().forEach(track => track.stop());
      let decoded = false, peak = 0;
      try {
        if (abandoned) return;
        if (failed || !parts.length) {
          message('The recorder produced no usable audio. Your previous recording, if any, is unchanged. Try another microphone or choose a file.');
          state.textContent = 'Recording not saved';
          return;
        }
        const blob = new Blob(parts, {type: mimeType});
        if (context) {
          try {
            const buffer = await context.decodeAudioData(await blob.arrayBuffer());
            for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
              for (const value of buffer.getChannelData(channel)) peak = Math.max(peak, Math.abs(value));
            }
            decoded = true;
          } catch (_) { /* Not every playable browser container supports decodeAudioData. */ }
        }
        const silent = decoded ? peak < 0.0000001 : measured && !inputWasHeard;
        if (silent) {
          state.textContent = 'Silent recording — not saved';
          message('No sound was detected. Choose another microphone and use Check microphone. This take has not replaced any earlier recording.');
          return;
        }
        const suffix = mimeType.includes('mp4') ? 'm4a' : mimeType.includes('ogg') ? 'ogg' : mimeType.includes('wav') ? 'wav' : 'webm';
        await onFile(new File([blob], `recording.${suffix}`, {type: mimeType}));
        state.textContent = 'Recording ready — listen before sharing';
        if (decoded && peak < 0.00005) message('This recording is very quiet. Listen and consider recording again with a higher microphone input level.');
        else if (!decoded && !inputWasHeard) message('Sound could not be verified automatically. Listen to this recording before sharing.');
      } catch (_) {
        state.textContent = 'Recording could not be prepared';
        message('Please try recording again, or choose an existing audio file.');
      } finally {
        await release(); mode = 'idle'; controls();
      }
    }
    record.addEventListener('click', async () => {
      if (mode === 'recording') { stopRecording(); return; }
      if (!['idle', 'checking'].includes(mode) || !supported()) return;
      const alreadyOpen = mode === 'checking';
      mode = 'opening'; controls(); message('');
      state.textContent = 'Starting microphone…';
      clearTimeout(deadline);
      try {
        if (!alreadyOpen && !await openMicrophone()) return;
        recorder = newRecorder();
        const parts = [];
        let failed = false;
        recorder.ondataavailable = event => { if (event.data.size) parts.push(event.data); };
        recorder.onerror = () => { failed = true; stopRecording(); };
        recorder.onstop = () => finish(parts, recorder.mimeType || parts[0]?.type || 'audio/webm', failed);
        heardSound = false; readings = 0;
        recorder.start(); mode = 'recording'; started = Date.now(); controls();
        state.textContent = 'Recording… 0 s';
        deadline = setTimeout(stopRecording, 90000);
      } catch (error) {
        await release(); mode = 'idle'; controls();
        state.textContent = 'Recording could not start'; message(explanation(error));
      }
    });
    window.addEventListener('pagehide', () => {
      abandoned = true;
      if (recorder?.state === 'recording') recorder.stop();
      release(); mode = 'idle';
    });
    window.addEventListener('pageshow', () => { abandoned = false; controls(); });
    navigator.mediaDevices?.addEventListener('devicechange', () => { if (mode === 'idle') listDevices(); });
    listDevices();
    return {get busy() { return mode !== 'idle'; }};
  };
})();
