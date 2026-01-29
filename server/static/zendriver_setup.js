window.__invokeGraphQLAPISetupPromise = (async () => {

    // 以下の実装を強く参考にした (thanks to @fa0311 !!)
    // ref: https://gist.github.com/fa0311/f36b00d36d6c4cf9e73c0dd5aefe3516

    // ===========================================
    // operationInfo と apiClient の収集
    // ===========================================
    // 従来の方式 (Function.prototype.call/apply のフック) は Twitter Web App の main.js の
    // 内部実装変更 (dispatch の arrow function 化) により壊れたため、
    // webpack のチャンクローディング API (webpackChunk.push) を直接フックし、
    // モジュールファクトリをラップする方式に移行した
    //
    // この方式のメリット:
    //   - Function.prototype を一切汚染しない (副作用リスクがない)
    //   - webpack がモジュールファクトリを .call() で呼ぶか直接呼ぶかに依存しない
    //   - operationInfo と apiClient の両方を単一のフックポイントで収集できる
    //
    // apiClient (GraphQL API クライアントクラスのインスタンス) の検出は2段階で行う:
    //   Stage 1: モジュールエクスポート時に「プロトタイプに dispatch メソッドを持つクラス」を検出
    //   Stage 2: クラスのインスタンス生成時に「graphQL と graphQLFullResponse メソッドを持つインスタンス」を確定
    // この組み合わせは Twitter Web App の GraphQL API クライアントクラス (class w) に一意であり、
    // 同クラスの設計が根本的に変わらない限り安定して動作する

    // operationInfo を収集する必要がある operationName のセット
    const requiredOperationNames = new Set([
        'Viewer',
        'CreateTweet',
        'CreateRetweet',
        'DeleteRetweet',
        'FavoriteTweet',
        'UnfavoriteTweet',
        'HomeLatestTimeline',
        'SearchTimeline',
    ]);

    // 収集結果を格納する変数
    const operationInfoMap = {};
    const collectedOperationNames = new Set();
    let apiClientInstance = null;

    // セットアップ完了を通知するための Promise のリゾルバ/リジェクタ
    let resolveSetup = null;
    let rejectSetup = null;
    const setupCompletePromise = new Promise((resolve, reject) => {
        resolveSetup = resolve;
        rejectSetup = reject;
    });

    // 必要な operationInfo と apiClient が全て揃ったかチェックし、揃っていればセットアップ完了を通知する
    const checkCollectionComplete = () => {
        const isAllOperationsCollected = Array.from(requiredOperationNames).every(
            name => collectedOperationNames.has(name)
        );
        if (isAllOperationsCollected && apiClientInstance !== null) {
            resolveSetup();
        }
    };

    // ===========================================
    // webpackChunk.push のフック
    // ===========================================
    // Twitter Web App は webpack 5 を使用しており、チャンク (main.js 等) は
    // self.webpackChunk_twitter_responsive_web.push() で登録される
    // vendor.js (webpack ランタイム) がロード済みの時点で push は webpackJsonpCallback に差し替えられているため、
    // ここではその webpackJsonpCallback をさらにラップして、モジュールファクトリを差し替える

    const chunkArray = self.webpackChunk_twitter_responsive_web;
    if (!chunkArray) {
        throw new Error('[zendriver_setup] webpackChunk_twitter_responsive_web not found');
    }

    // vendor.js によって差し替えられた push (= webpackJsonpCallback) を保存
    const originalPush = chunkArray.push;

    // push をラップして、チャンク登録前にモジュールファクトリを差し替える
    chunkArray.push = function(chunk) {
        // chunk のフォーマット: [chunkIds, modules, runtime?]
        // modules はモジュール ID をキー、ファクトリ関数を値とするオブジェクト
        const modules = chunk[1];
        if (modules && typeof modules === 'object') {
            for (const moduleId of Object.keys(modules)) {
                const originalFactory = modules[moduleId];
                // 各モジュールファクトリをラップして、実行後にエクスポートを検査する
                modules[moduleId] = function(module, exports, require) {

                    // --- require.d のオーバーライド ---
                    // webpack の require.d (ESM エクスポート定義ヘルパー) は Object.defineProperty で
                    // getter を定義するが、デフォルトでは configurable: false になっている
                    // apiClient クラスを Proxy で差し替えるために configurable: true にする必要がある
                    let originalDefineExports = null;
                    if (require && typeof require.d === 'function') {
                        originalDefineExports = require.d;
                        require.d = function(exp, definition) {
                            for (const key in definition) {
                                if (require.o(definition, key) && !require.o(exp, key)) {
                                    Object.defineProperty(exp, key, {
                                        enumerable: true,
                                        configurable: true,  // Proxy 差し替えのために configurable にする
                                        get: definition[key],
                                    });
                                }
                            }
                        };
                    }

                    // オリジナルのモジュールファクトリを実行
                    const result = originalFactory.apply(this, arguments);

                    // require.d を元に戻す
                    if (originalDefineExports !== null) {
                        require.d = originalDefineExports;
                    }

                    // --- operationInfo の収集 ---
                    // 各 operationInfo モジュールは CommonJS 形式 (e.exports = {...}) でエクスポートされる
                    // エクスポートされたオブジェクトに operationName プロパティがあれば operationInfo として収集する
                    try {
                        if (module.exports
                            && typeof module.exports === 'object'
                            && typeof module.exports.operationName === 'string') {
                            const operationName = module.exports.operationName;
                            operationInfoMap[operationName] = module.exports;
                            collectedOperationNames.add(operationName);
                            checkCollectionComplete();
                        }
                    } catch (_) {}

                    // --- apiClient クラスの検出と Proxy ラップ ---
                    // GraphQL API クライアントクラス (class w) は ESM 形式 (n.d(t, { ZP: () => w })) で
                    // エクスポートされる。エクスポートされたクラスのプロトタイプに dispatch メソッドがあれば、
                    // apiClient クラスの候補として Proxy でコンストラクタをラップする (Stage 1)
                    // Proxy の construct トラップでインスタンスに graphQL と graphQLFullResponse が
                    // 存在することを確認し、apiClient として確定する (Stage 2)
                    try {
                        // ESM エクスポート (n.d 経由の getter) を検査
                        const propertyDescriptors = Object.getOwnPropertyDescriptors(module.exports);
                        for (const [exportKey, descriptor] of Object.entries(propertyDescriptors)) {
                            // getter でないプロパティはスキップ
                            if (!descriptor.get) continue;
                            let classCandidate;
                            try {
                                classCandidate = module.exports[exportKey];
                            } catch (_) {
                                continue;
                            }
                            // 関数 (クラス) でなければスキップ
                            if (typeof classCandidate !== 'function') continue;
                            // プロトタイプに dispatch メソッドがなければスキップ (Stage 1)
                            if (!classCandidate.prototype
                                || typeof classCandidate.prototype.dispatch !== 'function') continue;

                            // Stage 1 通過: dispatch メソッドを持つクラスを発見
                            // Proxy でコンストラクタをラップし、インスタンス生成を監視する
                            const originalClass = classCandidate;
                            const constructionProxy = new Proxy(originalClass, {
                                construct(target, args, newTarget) {
                                    // オリジナルのコンストラクタでインスタンスを生成
                                    const instance = Reflect.construct(target, args, newTarget);
                                    try {
                                        // Stage 2: インスタンスに graphQL と graphQLFullResponse の両方が
                                        // 存在することを確認し、apiClient として確定する
                                        if (typeof instance.graphQL === 'function'
                                            && typeof instance.graphQLFullResponse === 'function'
                                            && apiClientInstance === null) {
                                            apiClientInstance = instance;
                                            console.log('[zendriver_setup] apiClient captured.');
                                            checkCollectionComplete();
                                        }
                                    } catch (_) {
                                        // Proxy 内のエラーでアプリケーションを壊さない
                                    }
                                    return instance;
                                },
                            });

                            // getter を Proxy 版に差し替える
                            // (require.d オーバーライドにより configurable: true になっているため可能)
                            Object.defineProperty(module.exports, exportKey, {
                                enumerable: true,
                                configurable: true,
                                get: () => constructionProxy,
                            });
                        }

                        // CommonJS エクスポート (e.exports = SomeClass) の場合も検査
                        // (現時点の Twitter Web App では class w は ESM エクスポートだが、将来の変更に備える)
                        if (typeof module.exports === 'function'
                            && module.exports.prototype
                            && typeof module.exports.prototype.dispatch === 'function') {
                            const originalClass = module.exports;
                            module.exports = new Proxy(originalClass, {
                                construct(target, args, newTarget) {
                                    const instance = Reflect.construct(target, args, newTarget);
                                    try {
                                        if (typeof instance.graphQL === 'function'
                                            && typeof instance.graphQLFullResponse === 'function'
                                            && apiClientInstance === null) {
                                            apiClientInstance = instance;
                                            console.log('[zendriver_setup] apiClient captured (CommonJS).');
                                            checkCollectionComplete();
                                        }
                                    } catch (_) {}
                                    return instance;
                                },
                            });
                            // Proxy は prototype を透過的に扱うが、明示的にコピーしておく
                            module.exports.prototype = originalClass.prototype;
                        }
                    } catch (_) {}

                    return result;
                };
            }
        }

        // ラップしたモジュールファクトリを含むチャンクを webpack の webpackJsonpCallback に渡す
        return originalPush(chunk);
    };

    // ===========================================
    // セットアップ完了待機
    // ===========================================

    // タイムアウト (15 秒)
    const timeoutId = setTimeout(() => {
        console.error('[zendriver_setup] Setup timeout.');
        console.error('[zendriver_setup] Collected operations:', Object.keys(operationInfoMap));
        console.error('[zendriver_setup] apiClient captured:', apiClientInstance !== null);
        rejectSetup(new Error('zendriver_setup: collection timeout'));
    }, 15 * 1000);

    // operationInfo と apiClient が全て揃うまで待機
    try {
        await setupCompletePromise;
    } finally {
        clearTimeout(timeoutId);
        // セットアップ完了後、元の push に戻す (遅延ロードされるチャンクに影響を与えないため)
        chunkArray.push = originalPush;
    }

    console.log('[zendriver_setup] operationInfoMap:', operationInfoMap);
    console.log('[zendriver_setup] apiClient:', apiClientInstance);

    // ===========================================
    // API クライアントのラッパーを window オブジェクトに公開する
    // ===========================================
    // このラッパーは Python 側 (TwitterScrapeBrowser) から呼び出される
    // apiClient.graphQL() を呼び出すことで、X-Client-Transaction-ID やその他のヘッダーが、
    // Twitter Web App の内部実装により自動付与される
    // ただし apiClient.graphQL() の戻り値はレスポンスの data のみを返すため、
    // XHR をフックして生のレスポンス (ステータスコード、ヘッダー等) を別途取得する

    window.__invokeGraphQLAPI = async (operationName, requestPayload, additionalFlags = null) => {
        // オリジナルの XMLHttpRequest を保存
        const OriginalXHR = window.XMLHttpRequest;
        // HTTP リクエストのフックで取得する API レスポンスを格納するオブジェクト
        const responseData = {
            parsedResponse: null,
            responseText: null,
            statusCode: null,
            headers: null,
            requestError: null,
        };
        // HTTP リクエストをフックして API レスポンスを取得する
        window.XMLHttpRequest = function() {
            const xhr = new OriginalXHR();
            const originalOpen = xhr.open.bind(xhr);
            const originalSend = xhr.send.bind(xhr);
            xhr.open = function(method, url, ...args) {
                // GraphQL API のエンドポイントかどうかを判定
                if (url && url.includes('/graphql/')) {
                    // onreadystatechange をフック
                    xhr.addEventListener('readystatechange', function() {
                        if (xhr.readyState === 4) {
                            responseData.statusCode = xhr.status;
                            responseData.responseText = xhr.responseText;
                            responseData.headers = {};
                            // レスポンスヘッダーを取得
                            const headerString = xhr.getAllResponseHeaders();
                            if (headerString) {
                                const headerPairs = headerString.trim().split('\r\n');
                                for (const headerPair of headerPairs) {
                                    const [key, value] = headerPair.split(': ');
                                    if (key && value) {
                                        responseData.headers[key.toLowerCase()] = value;
                                    }
                                }
                            }
                            // レスポンスをパース
                            try {
                                if (responseData.responseText) {
                                    responseData.parsedResponse = JSON.parse(responseData.responseText);
                                }
                            } catch (e) {
                                // JSON パースに失敗した場合は responseText をそのまま保持
                                responseData.parsedResponse = null;
                            }
                        }
                    });
                    // onerror をフック
                    xhr.addEventListener('error', function() {
                        responseData.requestError = 'Request failed';
                    });
                    // ontimeout をフック
                    xhr.addEventListener('timeout', function() {
                        responseData.requestError = 'Request timeout';
                    });
                }
                return originalOpen(method, url, ...args);
            };
            xhr.send = function(...args) {
                return originalSend(...args);
            };
            return xhr;
        };
        // XMLHttpRequest のプロトタイプをコピー
        window.XMLHttpRequest.prototype = OriginalXHR.prototype;
        try {
            // operationName から operationInfo を取得
            const operationInfo = operationInfoMap[operationName];
            // HTTP リクエストを実行
            // X-Client-Transaction-ID や各ヘッダーの付与はすべて内部で行われる
            // XHR フックで生のレスポンスを取得するため、戻り値は使用しない
            if (additionalFlags) {
                // 第三引数はおそらくサーバーからエラーが返された際に致命的なエラーかをチェックする関数
                await apiClientInstance.graphQL(operationInfo, requestPayload, () => false, additionalFlags);
            } else {
                await apiClientInstance.graphQL(operationInfo, requestPayload);
            }
            // XMLHttpRequest を元に戻す
            window.XMLHttpRequest = OriginalXHR;
            // API レスポンスを返す
            return {
                parsedResponse: responseData.parsedResponse,
                responseText: responseData.responseText,
                statusCode: responseData.statusCode,
                headers: responseData.headers,
                requestError: responseData.requestError,
            };
        } catch (error) {
            // XMLHttpRequest を元に戻す
            window.XMLHttpRequest = OriginalXHR;
            // エラーが発生した場合、取得できたレスポンスがあればそれを含めて返す
            return {
                parsedResponse: responseData.parsedResponse,
                responseText: responseData.responseText,
                statusCode: responseData.statusCode,
                headers: responseData.headers,
                requestError: responseData.requestError,
            };
        }
    }

    return true;
})();
