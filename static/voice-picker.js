(function () {
  const root = document.getElementById("voice-picker");
  if (!root) return;

  const style = document.createElement("style");
  style.textContent = `
    .vp-label { display:block; font-size:12px; color:#71717a; margin:18px 0 8px; }
    .vp-filters, .vp-voices { display:flex; flex-wrap:wrap; gap:8px; }
    .vp-filters button, .vp-voices button, .vp-hear {
      border:1px solid #27272a; background:#0c0c0f; color:#fafafa;
      border-radius:999px; padding:8px 12px; font:inherit; font-size:13px; cursor:pointer;
    }
    .vp-filters button.on, .vp-voices button.on {
      border-color:transparent;
      background:linear-gradient(#16161a,#16161a) padding-box,
        linear-gradient(90deg,#3b82f6,#8b5cf6) border-box;
      color:#fff;
    }
    .vp-voices { max-height:220px; overflow:auto; padding-right:4px; }
    .vp-voices button { border-radius:12px; text-align:left; }
    .vp-voices small { display:block; color:#a1a1aa; font-size:11px; margin-top:2px; }
    .vp-row { display:flex; gap:10px; align-items:center; margin-top:12px; flex-wrap:wrap; }
    .vp-row select {
      background:#0c0c0f; color:#fafafa; border:1px solid #27272a; border-radius:12px;
      padding:10px 12px; font:inherit; font-size:14px;
    }
    .vp-note { color:#a1a1aa; font-size:13px; margin:8px 0 0; }
    .vp-error { color:#fca5a5; font-size:13px; margin:8px 0 0; }
  `;
  document.head.appendChild(style);

  let voices = [];
  let gender = "all";
  let selected = root.dataset.voice || "Kore";

  root.innerHTML = `
    <div class="vp-label">Voice</div>
    <div class="vp-filters" id="vp-filters"></div>
    <p class="vp-note" id="vp-selected"></p>
    <div class="vp-voices" id="vp-voices" style="margin-top:10px"></div>
    <div class="vp-row">
      <button class="vp-hear" type="button" id="vp-hear">Hear this voice</button>
      <label class="vp-label" style="margin:0">Tone
        <select name="tone" id="vp-tone"></select>
      </label>
      <label class="vp-label" style="margin:0">How they speak
        <select name="manner" id="vp-manner"></select>
      </label>
    </div>
    <p class="vp-error" id="vp-error" hidden></p>
    <input type="hidden" name="voice" id="vp-voice" value="${selected}">
  `;

  const filters = root.querySelector("#vp-filters");
  const list = root.querySelector("#vp-voices");
  const selectedLine = root.querySelector("#vp-selected");
  const error = root.querySelector("#vp-error");
  ["all", "female", "male"].forEach((value) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.gender = value;
    button.textContent = value === "all" ? "All voices" : value === "female" ? "Women" : "Men";
    button.addEventListener("click", () => {
      gender = value;
      paint();
    });
    filters.appendChild(button);
  });

  function paint() {
    filters.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("on", button.dataset.gender === gender);
    });
    const shown = voices.filter((item) => gender === "all" || item.gender === gender);
    list.innerHTML = "";
    shown.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.classList.toggle("on", item.name === selected);
      button.innerHTML = `${item.name}<small>${item.gender === "female" ? "Woman" : "Man"} · ${item.style}</small>`;
      button.addEventListener("click", () => {
        selected = item.name;
        root.querySelector("#vp-voice").value = selected;
        paint();
      });
      list.appendChild(button);
    });
    const current = voices.find((item) => item.name === selected);
    selectedLine.textContent = current
      ? `Selected: ${current.name}, ${current.gender === "female" ? "woman" : "man"}, ${current.style.toLowerCase()}.`
      : "";
  }

  function fillSelect(id, options, current) {
    const select = root.querySelector(id);
    options.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.label;
      option.selected = item.id === current;
      select.appendChild(option);
    });
  }

  root.querySelector("#vp-hear").addEventListener("click", async () => {
    const button = root.querySelector("#vp-hear");
    button.disabled = true;
    error.hidden = true;
    button.textContent = "Playing...";
    try {
      const response = await fetch("/studio/voices/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: selected }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "That voice sample could not be played.");
      }
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      await audio.play();
    } catch (err) {
      error.hidden = false;
      error.textContent = err.message || "That voice sample could not be played.";
    } finally {
      button.disabled = false;
      button.textContent = "Hear this voice";
    }
  });

  fetch("/studio/voices")
    .then((response) => response.json())
    .then((data) => {
      voices = data.voices || [];
      if (!voices.some((item) => item.name === selected)) selected = "Kore";
      const current = voices.find((item) => item.name === selected);
      if (current) gender = current.gender;
      fillSelect("#vp-tone", data.tones || [], root.dataset.tone || "warm");
      fillSelect("#vp-manner", data.manners || [], root.dataset.manner || "brief");
      root.querySelector("#vp-voice").value = selected;
      paint();
    })
    .catch(() => {
      error.hidden = false;
      error.textContent = "The Gemini voices could not be loaded.";
    });
})();
