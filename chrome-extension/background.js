const TWITTER_EMBED_RULE_ID = 1;
const TWITTER_COOKIE_RULE_ID_START = 100;
const TWITTER_COOKIE_RULE_ID_END = 999;
const TWITTER_REQUEST_TARGETS = [
  {hostname: 'x.com'},
  {hostname: 'api.x.com'},
];
let twitterCookieRulesUpdatePromise = Promise.resolve();

const updateDnrRules = async () => {
  // KonomiTV から x.com を iframe 表示する検証に必要なレスポンスヘッダーだけを外す
  // initiatorDomains はサブドメインにも一致するため、192-168-1-xx.local.konomi.tv 系も対象になる
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: [TWITTER_EMBED_RULE_ID],
    addRules: [
      {
        id: TWITTER_EMBED_RULE_ID,
        priority: 1,
        action: {
          type: 'modifyHeaders',
          responseHeaders: [
            {
              header: 'Content-Security-Policy',
              operation: 'remove',
            },
            {
              header: 'X-Frame-Options',
              operation: 'remove',
            },
          ],
        },
        condition: {
          requestDomains: ['x.com', 'twitter.com'],
          initiatorDomains: ['local.konomi.tv'],
          resourceTypes: ['sub_frame'],
        },
      },
    ],
  });
};

const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const isCookiePathMatch = (requestPath, cookiePath) => {
  // RFC 6265 の境界条件に従い、単なる文字列前方一致で別名パスを巻き込まない
  if (requestPath === cookiePath) {
    return true;
  }
  if (requestPath.startsWith(cookiePath) === false) {
    return false;
  }
  return cookiePath.endsWith('/') || requestPath[cookiePath.length] === '/';
};

const isCookieDomainMatch = (hostname, cookie) => {
  const cookieDomain = cookie.domain.replace(/^\./, '');
  if (cookie.hostOnly === true) {
    return hostname === cookieDomain;
  }
  return hostname === cookieDomain || hostname.endsWith(`.${cookieDomain}`);
};

const updateTwitterCookieRules = async () => {
  // KonomiTV タブの有無で規則の寿命を管理し、Twitter の Service Worker が発行する tabId=-1 の要求も補完する
  const konomiTVTabs = await chrome.tabs.query({url: 'https://*.local.konomi.tv/*'});

  // Service Worker の再起動後も残るセッション規則を API から復元し、同じ ID の再追加を避ける
  const existingSessionRules = await chrome.declarativeNetRequest.getSessionRules();
  const existingTwitterCookieRuleIDs = existingSessionRules
    .map((sessionRule) => sessionRule.id)
    .filter((ruleID) => ruleID >= TWITTER_COOKIE_RULE_ID_START && ruleID <= TWITTER_COOKIE_RULE_ID_END);

  // 対象タブがない間は認証情報をセッション規則へ保持する必要がない
  if (konomiTVTabs.length === 0) {
    await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: existingTwitterCookieRuleIDs});
    return;
  }

  // 非分割 Cookie と KonomiTV をトップレベルサイトに持つ分割 Cookie の両方を取得する
  const [unpartitionedCookies, partitionedCookies] = await Promise.all([
    chrome.cookies.getAll({domain: 'x.com'}),
    chrome.cookies.getAll({
      domain: 'x.com',
      partitionKey: {topLevelSite: 'https://konomi.tv'},
    }),
  ]);
  const unpartitionedCookieIdentities = new Set(
    unpartitionedCookies.map((cookie) => `${cookie.name}\n${cookie.domain}\n${cookie.path}`),
  );
  const uniquePartitionedCookies = partitionedCookies.filter((cookie) => {
    // 通常の x.com と同じ非分割 Cookie を優先し、同名の分割 Cookie で CSRF 値を曖昧にしない
    const cookieIdentity = `${cookie.name}\n${cookie.domain}\n${cookie.path}`;
    return unpartitionedCookieIdentities.has(cookieIdentity) === false;
  });
  const allCookies = [...unpartitionedCookies, ...uniquePartitionedCookies];

  const cookieRules = [];
  for (const requestTarget of TWITTER_REQUEST_TARGETS) {
    // ホスト限定と Domain Cookie を分け、対象ホストへ送信できる Cookie だけを残す
    const hostnameCookies = allCookies.filter((cookie) => isCookieDomainMatch(requestTarget.hostname, cookie));
    const csrfCookie = hostnameCookies.find((cookie) => cookie.name === 'ct0');
    if (csrfCookie === undefined) {
      continue;
    }

    // Cookie Path ごとに優先度の異なる規則を作り、実際の要求パスに最も近いヘッダーを選ばせる
    const cookiePaths = [...new Set(hostnameCookies.map((cookie) => cookie.path))]
      .sort((firstPath, secondPath) => firstPath.length - secondPath.length);
    for (const cookiePath of cookiePaths) {
      const representativeRequestPath = cookiePath.endsWith('/') ? cookiePath : `${cookiePath}/`;
      const requestCookies = hostnameCookies
        .filter((cookie) => isCookiePathMatch(representativeRequestPath, cookie.path))
        .sort((firstCookie, secondCookie) => secondCookie.path.length - firstCookie.path.length);
      const ruleID = TWITTER_COOKIE_RULE_ID_START + cookieRules.length;
      const escapedCookiePath = escapeRegex(cookiePath);
      const pathSuffix = cookiePath.endsWith('/') ? '' : '(?:/|$)';
      cookieRules.push({
        id: ruleID,
        priority: 1000 + cookiePath.length,
        action: {
          type: 'modifyHeaders',
          requestHeaders: [
            {
              header: 'cookie',
              operation: 'set',
              value: requestCookies.map((cookie) => `${cookie.name}=${cookie.value}`).join('; '),
            },
            {
              header: 'x-csrf-token',
              operation: 'set',
              value: csrfCookie.value,
            },
          ],
        },
        condition: {
          regexFilter: `^https://${escapeRegex(requestTarget.hostname)}(?::\\d+)?${escapedCookiePath}${pathSuffix}`,
          resourceTypes: ['xmlhttprequest', 'ping', 'other'],
        },
      });
    }
  }

  // Cookie 値はブラウザ終了時に破棄されるセッション規則だけへ保持する
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: existingTwitterCookieRuleIDs,
    addRules: cookieRules,
  });
};

const scheduleTwitterCookieRulesUpdate = () => {
  // Cookie 更新が連続しても DNR 更新を直列化し、同じ規則 ID の追加処理を競合させない
  twitterCookieRulesUpdatePromise = twitterCookieRulesUpdatePromise.then(updateTwitterCookieRules, updateTwitterCookieRules);
  return twitterCookieRulesUpdatePromise;
};

chrome.runtime.onInstalled.addListener(() => {
  updateDnrRules().catch((error) => {
    console.error('Failed to install DNR rules:', error);
  });
  scheduleTwitterCookieRulesUpdate().catch((error) => {
    console.error('Failed to install Twitter cookie rules:', error);
  });
});

chrome.runtime.onStartup.addListener(() => {
  updateDnrRules().catch((error) => {
    console.error('Failed to restore DNR rules:', error);
  });
  scheduleTwitterCookieRulesUpdate().catch((error) => {
    console.error('Failed to restore Twitter cookie rules:', error);
  });
});

chrome.webNavigation.onCommitted.addListener((details) => {
  // 最上位ページの遷移後に対象タブを取り直し、KonomiTV から離れたタブへ規則を残さない
  if (details.frameId === 0) {
    scheduleTwitterCookieRulesUpdate().catch((error) => {
      console.error('Failed to update Twitter cookie rules after navigation:', error);
    });
  }
});

chrome.tabs.onRemoved.addListener(() => {
  // KonomiTV のタブを閉じた場合は残った対象タブだけで規則を作り直す
  scheduleTwitterCookieRulesUpdate().catch((error) => {
    console.error('Failed to update Twitter cookie rules after closing a tab:', error);
  });
});

chrome.cookies.onChanged.addListener((changeInfo) => {
  // Twitter の Cookie が変化した直後から、次の要求で使うヘッダー全体を最新状態へ更新する
  const cookieDomain = changeInfo.cookie.domain;
  if (cookieDomain === 'x.com' || cookieDomain.endsWith('.x.com')) {
    scheduleTwitterCookieRulesUpdate().catch((error) => {
      console.error('Failed to update Twitter cookie rules after a cookie change:', error);
    });
  }
});
