// Reused read-only EKS viewport pattern; official Archify originals remain immutable.
// Presentation-only adapter for the five SHA-pinned Archify 3.1.0 exports.
// Exact anchors fail closed on an upstream renderer change. The SVG stays intact.
function replaceOnce(html, before, after) {
  if (html.split(before).length !== 2)
    throw new Error("Archify viewport anchor changed: " + before.slice(0, 70));
  return html.replace(before, after);
}
export function adaptViewport(html) {
  html = replaceOnce(
    html,
    "if (action === 'present') return Archify.presentation.enter();",
    "if (action === 'present') return Archify.view.fitWidth();",
  );
  html = replaceOnce(html, "f: 'present',", "w: 'present',");
  html = replaceOnce(
    html,
    "function setActive(next, options) {\n        options = options || {};\n        next = Boolean(next);",
    "function setActive(next, options) {\n        options = options || {};\n        next = true; // Embedded stage is owned by the ECS portfolio host.",
  );
  html = replaceOnce(
    html,
    "target.closest('[data-node-id], [data-relationship-hit-key], .overview-map, #btn-export, #export-menu')",
    'target.closest(\'[data-node-id], [data-relationship-hit-key], .overview-map, .toolbar, [data-view="in"], [data-view="out"], .fit-width, #btn-export, #export-menu\')',
  );
  html = replaceOnce(
    html,
    "reset: reset,\n        reveal: reveal,",
    `fitWidth: function () {
          stopCameraMotion('fit-width', false);
          var width = svg.clientWidth, height = svg.clientHeight;
          if (!viewBox || width <= 0 || height <= 0) return;
          var base = Math.min(width / viewBox.width, height / viewBox.height);
          var scale = Math.max(1, Math.min(maximumZoom, width * 0.96 / (viewBox.width * base)));
          state = { scale: scale, x: width * (1 - scale) / 2, y: 0, mode: 'width' };
          apply();
        },
        reset: reset,
        reveal: reveal,`,
  );
  html = replaceOnce(
    html,
    "if (state.mode === 'semantic') syncSemantic();\n          else apply();",
    "if (state.mode === 'semantic') syncSemantic();\n          else if (state.mode === 'width') Archify.view.fitWidth();\n          else apply();",
  );
  // Only the host owns focus/fullscreen. Keep the inner presentation layout fixed;
  // otherwise Escape/F would introduce a second, conflicting expansion mode.
  html = replaceOnce(
    html,
    "} else if (e.key === 'f' || e.key === 'F') {\n        e.preventDefault();\n        Archify.presentation.toggle();",
    "} else if (e.key === 'w' || e.key === 'W') {\n        e.preventDefault();\n        Archify.view.fitWidth();",
  );
  html = replaceOnce(
    html,
    "} else if (e.key === 'Escape' && Archify.presentation.active()) {\n        e.preventDefault();\n        Archify.presentation.exit();",
    "",
  );
  // The original camera readout remains the single Ajustar todo / reset control.
  html = replaceOnce(
    html,
    "resetBtn.setAttribute('aria-label', readout + ' · '",
    "resetBtn.setAttribute('aria-label', 'Ajustar todo · ' + readout + ' · '",
  );
  return html;
}

export const viewportStyle = `
/* Embedded diagram stage: native tools, one camera, no nested page scrolling. */
html[data-present="true"]:not([data-embed="true"]) body {
  padding: 0; height: 100dvh; overflow: hidden;
}
html[data-present="true"]:not([data-embed="true"]) .container {
  width: 100%; height: 100dvh; max-width: none; gap: 0;
}
html[data-present="true"]:not([data-embed="true"]) .header { display: none; }
html[data-present="true"]:not([data-embed="true"]) .toolbar {
  top: 8px; right: 10px; left: auto; max-width: calc(100% - 20px);
}
#btn-present { display: none !important; }
html[data-present="true"]:not([data-embed="true"]) .diagram-container {
  margin: 0; border: 0; border-radius: 0; overflow: hidden;
  padding: 58px 16px 76px; min-width: 0; min-height: 0;
}
html[data-present="true"]:not([data-embed="true"]) .diagram-container > svg {
  width: 100% !important; height: 100% !important; min-width: 0 !important;
  max-width: none !important; flex: 1 1 auto;
}
.diagram-nav [data-view="reset"]::before { content: "Ajustar todo"; font-size: 11px; margin-right: 5px; }
.fit-width { font: inherit; white-space: nowrap; }
.diagram-container.is-pannable { touch-action: none; }
@media (max-width: 720px) {
  html[data-present="true"]:not([data-embed="true"]) .diagram-container { padding: 58px 12px 122px; }
  .diagram-nav { flex-wrap: wrap; justify-content: center; overflow: visible; max-width: calc(100% - 16px); }
  .diagram-nav button { flex-shrink: 0; white-space: nowrap; }
  .diagram-nav [data-view="reset"] { min-width: 104px; }
}
`;

export const viewportScript = `
// No host commands, storage or network. Resize stays inside Archify's native
// rAF camera handler: overview refits, width refits, manual scale is preserved.
var fitWidthButton = document.createElement('button');
fitWidthButton.type = 'button';
fitWidthButton.className = 'fit-width';
fitWidthButton.textContent = 'Ajustar ancho';
fitWidthButton.title = 'Ajustar ancho (W) · vertical content may need pan/zoom';
fitWidthButton.setAttribute('aria-label', 'Ajustar ancho del diagrama');
fitWidthButton.addEventListener('click', function () { Archify.view.fitWidth(); });
document.querySelector('.diagram-nav').appendChild(fitWidthButton);
var widthGuide = document.querySelector('[data-guide-action="present"]');
widthGuide.setAttribute('aria-label', 'Ajustar ancho del diagrama');
widthGuide.querySelector('strong').textContent = 'Ajustar ancho';
widthGuide.querySelector('small').textContent = 'Amplía el diagrama y desplázalo. Ajustar todo restaura la vista.';
widthGuide.querySelector('kbd').textContent = 'W';
`;
