// A graphic the model wrote itself (reel_engine/motion_code.py): its HTML and CSS, already cleaned to an allowlist
// on the server, mounted in a closed shadow root so its styles cannot leak onto the page or the next graphic.
// Motion is CSS animations only; seek(t) pauses every one of them at t, so each frame is exact and repeatable.
(() => {
  const { T } = window.BeatsKit;

  T.code = (s, root) => {
    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;inset:0;';
    root.appendChild(host);
    const shadow = host.attachShadow({ mode: 'closed' });
    shadow.innerHTML = `<style>:host{all:initial;position:absolute;inset:0;overflow:hidden;}${s.data.css || ''}</style>${s.data.html || ''}`;
    return {
      seek(t) {
        // Reading styles makes Chrome create the CSS animations before they are listed.
        getComputedStyle(host).opacity;
        shadow.getAnimations().forEach((a) => {
          a.pause();
          a.currentTime = t * 1000;
        });
      },
    };
  };
})();
