(function () {
    // Which element gets the effect.
    const SELECTOR = ".welcome-heading";

    // Only these words get the focus effect; the rest of the heading stays plain.
    // Set to "" to apply it to every word.
    const FOCUS_TEXT = "Trail Sense";

    // Same props as the React Bits component.
    const OPTIONS = {
        separator: " ",
        manualMode: false,              // true = focus follows the mouse instead of auto-cycling
        blurAmount: 5,                  // px of blur on non-active words
        borderColor: "#7dd3fc",
        glowColor: "rgba(125, 211, 252, 0.6)",
        animationDuration: 0.5,         // seconds
        pauseBetweenAnimations: 1       // seconds
    };

    const el = document.querySelector(SELECTOR);
    if (!el) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const words = el.textContent.trim().split(OPTIONS.separator).filter(Boolean);
    if (!words.length) return;

    // Work out which words take part in the effect
    let focusIndexes = words.map(function (_, i) { return i; });
    if (FOCUS_TEXT) {
        const target = FOCUS_TEXT.split(OPTIONS.separator).filter(Boolean);
        for (let start = 0; start + target.length <= words.length; start++) {
            if (target.every(function (t, k) { return words[start + k] === t; })) {
                focusIndexes = target.map(function (_, k) { return start + k; });
                break;
            }
        }
    }

    // Build the markup
    el.textContent = "";
    el.classList.add("true-focus");
    el.style.setProperty("--tf-duration", OPTIONS.animationDuration + "s");
    el.style.setProperty("--tf-border", OPTIONS.borderColor);
    el.style.setProperty("--tf-glow", OPTIONS.glowColor);

    const wordEls = words.map(function (word) {
        const span = document.createElement("span");
        span.className = "tf-word";
        span.textContent = word;
        el.appendChild(span);
        return span;
    });

    const frame = document.createElement("div");
    frame.className = "tf-frame";
    frame.setAttribute("aria-hidden", "true");
    ["top-left", "top-right", "bottom-left", "bottom-right"].forEach(function (pos) {
        const corner = document.createElement("span");
        corner.className = "tf-corner " + pos;
        frame.appendChild(corner);
    });
    el.appendChild(frame);

    let pos = 0;                         // position inside focusIndexes
    let current = focusIndexes[0];       // index into wordEls
    let lastActive = current;

    function update() {
        wordEls.forEach(function (w, i) {
            const inFocusGroup = focusIndexes.indexOf(i) !== -1;
            const blur = reduceMotion || !inFocusGroup || i === current ? 0 : OPTIONS.blurAmount;
            w.style.filter = "blur(" + blur + "px)";
        });

        const parent = el.getBoundingClientRect();
        const active = wordEls[current].getBoundingClientRect();
        frame.style.transform =
            "translate(" + (active.left - parent.left) + "px, " + (active.top - parent.top) + "px)";
        frame.style.width = active.width + "px";
        frame.style.height = active.height + "px";
    }

    update();
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            frame.classList.add("is-ready");
        });
    });

    // Keep the frame aligned when the font loads or the window resizes
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(update);
    window.addEventListener("resize", update);

    if (OPTIONS.manualMode) {
        focusIndexes.forEach(function (i) {
            const w = wordEls[i];
            w.addEventListener("mouseenter", function () {
                lastActive = i;
                current = i;
                update();
            });
            w.addEventListener("mouseleave", function () {
                current = lastActive;
                update();
            });
        });
    } else if (!reduceMotion && focusIndexes.length > 1) {
        setInterval(function () {
            pos = (pos + 1) % focusIndexes.length;
            current = focusIndexes[pos];
            update();
        }, (OPTIONS.animationDuration + OPTIONS.pauseBetweenAnimations) * 1000);
    }
})();