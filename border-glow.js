(function () {
    // Which elements get the glow. Add more selectors here if you want.
    const SELECTOR = ".signin-content";

    // Same props as the React Bits component.
    const OPTIONS = {
        edgeSensitivity: 30,        // 0-100: how close to the edge the pointer must be
        glowColor: "40 80 80",      // "H S L"
        glowRadius: 40,             // px the glow extends beyond the box
        glowIntensity: 2.0,         // 0.1-3.0
        coneSpread: 25,             // 5-45
        fillOpacity: 0.5,
        colors: ["#c084fc", "#f472b6", "#38bdf8"]
    };

    const GRADIENT_POSITIONS = ["80% 55%", "69% 34%", "8% 6%", "41% 38%", "86% 85%", "82% 18%", "51% 4%"];
    const GRADIENT_KEYS = ["--gradient-one", "--gradient-two", "--gradient-three", "--gradient-four", "--gradient-five", "--gradient-six", "--gradient-seven"];
    const COLOR_MAP = [0, 1, 2, 0, 1, 2, 1];

    function parseHSL(str) {
        const m = str.match(/([\d.]+)\s*([\d.]+)%?\s*([\d.]+)%?/);
        if (!m) return { h: 40, s: 80, l: 80 };
        return { h: parseFloat(m[1]), s: parseFloat(m[2]), l: parseFloat(m[3]) };
    }

    function applyVars(card) {
        const o = OPTIONS;
        const { h, s, l } = parseHSL(o.glowColor);
        const base = h + "deg " + s + "% " + l + "%";
        const opacities = [100, 60, 50, 40, 30, 20, 10];
        const keys = ["", "-60", "-50", "-40", "-30", "-20", "-10"];

        opacities.forEach(function (op, i) {
            card.style.setProperty(
                "--glow-color" + keys[i],
                "hsl(" + base + " / " + Math.min(op * o.glowIntensity, 100) + "%)"
            );
        });

        for (let i = 0; i < 7; i++) {
            const c = o.colors[Math.min(COLOR_MAP[i], o.colors.length - 1)];
            card.style.setProperty(
                GRADIENT_KEYS[i],
                "radial-gradient(at " + GRADIENT_POSITIONS[i] + ", " + c + " 0px, transparent 50%)"
            );
        }
        card.style.setProperty("--gradient-base", "linear-gradient(" + o.colors[0] + " 0 100%)");

        card.style.setProperty("--edge-sensitivity", o.edgeSensitivity);
        card.style.setProperty("--glow-padding", o.glowRadius + "px");
        card.style.setProperty("--cone-spread", o.coneSpread);
        card.style.setProperty("--fill-opacity", o.fillOpacity);
    }

    function edgeProximity(w, h, x, y) {
        const cx = w / 2;
        const cy = h / 2;
        const dx = x - cx;
        const dy = y - cy;
        const kx = dx !== 0 ? cx / Math.abs(dx) : Infinity;
        const ky = dy !== 0 ? cy / Math.abs(dy) : Infinity;
        return Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
    }

    function cursorAngle(w, h, x, y) {
        const dx = x - w / 2;
        const dy = y - h / 2;
        if (dx === 0 && dy === 0) return 0;
        let deg = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
        if (deg < 0) deg += 360;
        return deg;
    }

    function setup(card) {
        if (card.classList.contains("border-glow-card")) return;
        card.classList.add("border-glow-card");

        // Wrap existing children (moves them, so existing JS references and listeners keep working)
        const inner = document.createElement("div");
        inner.className = "border-glow-inner";
        while (card.firstChild) inner.appendChild(card.firstChild);

        const edge = document.createElement("span");
        edge.className = "edge-light";

        card.appendChild(edge);
        card.appendChild(inner);

        applyVars(card);

        card.addEventListener("pointermove", function (e) {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const edgeValue = edgeProximity(rect.width, rect.height, x, y);
            const angle = cursorAngle(rect.width, rect.height, x, y);
            card.style.setProperty("--edge-proximity", (edgeValue * 100).toFixed(3));
            card.style.setProperty("--cursor-angle", angle.toFixed(3) + "deg");
        });
    }

    document.querySelectorAll(SELECTOR).forEach(setup);
})();
