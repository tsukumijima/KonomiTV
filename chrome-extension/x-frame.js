(() => {
  const STYLE_ID = 'konomitv-twitter-frame-poc-style';

  // 通常の x.com タブへ iframe 用 CSS を適用しないよう、KonomiTV 配下のフレームだけに限定する
  const hasKonomiTVAncestor = [...location.ancestorOrigins].some((ancestorOrigin) => {
    const ancestorHostname = new URL(ancestorOrigin).hostname;
    return ancestorHostname === 'local.konomi.tv' || ancestorHostname.endsWith('.local.konomi.tv');
  });
  if (hasKonomiTVAncestor === false) {
    return;
  }

  // x.com 側フレームへ直接注入される content script なので、公式 Web App の DOM に CSS を当てられる
  if (document.getElementById(STYLE_ID) === null) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      html {
        scrollbar-width: thin !important;
      }

      header[role='banner'] {
        display: none !important;
      }
    `;
    document.documentElement.append(style);
  }
})();
