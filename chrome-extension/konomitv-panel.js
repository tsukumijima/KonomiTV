(() => {
  const PANEL_ID = 'konomitv-twitter-embed-poc';

  // 拡張の再読み込みや KonomiTV の画面遷移後に二重表示されないよう、既存パネルがあれば再作成しない
  if (document.getElementById(PANEL_ID) !== null) {
    return;
  }

  // KonomiTV 本体の UI を変更せず、画面右側に検証用の独立パネルとして x.com を重ねる
  const panel = document.createElement('div');
  panel.id = PANEL_ID;
  panel.style.cssText = [
    'position: fixed',
    'right: 16px',
    'bottom: 16px',
    'z-index: 2147483647',
    'width: min(480px, calc(100vw - 32px))',
    'height: min(760px, calc(100vh - 32px))',
    'overflow: hidden',
    'background: #000000',
    'border: 1px solid rgba(255, 255, 255, 0.25)',
    'border-radius: 8px',
    'box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45)',
  ].join(';');

  const iframe = document.createElement('iframe');
  iframe.src = 'https://x.com/home';
  iframe.allow = 'fullscreen; clipboard-write';
  // ローカルの KonomiTV オリジンを Twitter の onboarding/referrer へ送らず、直接アクセスと同じ状態にする
  iframe.referrerPolicy = 'no-referrer';
  iframe.style.cssText = [
    'display: block',
    'width: 100%',
    'height: 100%',
    'border: 0',
    'background: #000000',
  ].join(';');

  panel.append(iframe);
  document.documentElement.append(panel);
})();
