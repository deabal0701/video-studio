// 모션 템플릿 공용 초기화 — 질의 문자열로 받은 값을 DOM과 CSS 변수에 꽂는다.
// 같은 템플릿을 문구만 바꿔 여러 번 쓰기 위한 장치다 (lib/motion.js가 params를 붙여 준다).
//
// 주의: 여기서 하는 일은 "레이아웃 준비"까지다. 애니메이션은 건드리지 않는다.
// 렌더러가 currentTime을 직접 밀며 프레임을 찍으므로 재생 제어는 필요 없다.
(() => {
  const q = new URLSearchParams(location.search);
  const root = document.documentElement;

  const setVar = (name, value) => value && root.style.setProperty(name, value);
  setVar('--brand', q.get('brand'));
  setVar('--brand-soft', q.get('brandSoft'));
  setVar('--bg', q.get('bg'));
  setVar('--fg', q.get('fg'));

  // 프로젝트 글꼴을 쓰고 싶으면 fontUrl에 woff2/ttf 경로(절대 또는 file 기준 상대)를 준다.
  const fontUrl = q.get('fontUrl');
  if (fontUrl) {
    const style = document.createElement('style');
    style.textContent =
      `@font-face{font-family:'ProjectFont';src:url('${fontUrl}');` +
      `font-weight:1 1000;font-display:block}`;
    document.head.appendChild(style);
    root.style.setProperty('--font', "'ProjectFont', system-ui, sans-serif");
  } else if (q.get('font')) {
    root.style.setProperty('--font', q.get('font'));
  }

  // data-p="키" 요소에 값을 채운다. 값이 없으면 그 요소는 지운다 — 빈 줄이 자리를 차지하면
  // 가운데 정렬이 어긋난다.
  for (const el of document.querySelectorAll('[data-p]')) {
    const value = q.get(el.dataset.p);
    if (value) el.textContent = value;
    else el.remove();
  }

  // 마무리 흰 면(다음 화면이 밝을 때)을 끌 수 있다.
  const wipe = document.querySelector('.wipe');
  if (q.get('wipe') === 'off') wipe?.remove();
  // wipeAt(초)은 렌더러가 클립 길이에서 계산해 넘긴다. 템플릿의 고정 지연을 쓰면 구간이
  // 늘어났을 때 와이프가 먼저 끝나 남은 시간이 흰 화면으로 남는다.
  else if (wipe && q.get('wipeAt')) wipe.style.animationDelay = `${q.get('wipeAt')}s`;
  const wipeColor = q.get('wipeColor');
  if (wipeColor) root.style.setProperty('--wipe', wipeColor);
})();
