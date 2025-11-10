window.__invokeGraphQLAPISetupPromise = (async () => {

    // 以下の実装を強く参考にした (thanks to @fa0311 !!)
    // ref: https://gist.github.com/fa0311/f36b00d36d6c4cf9e73c0dd5aefe3516

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

    // GraphQL API の operationInfo を収集し、キー: operationName, 値: operationInfo の Map を作る
    const operationInfoMap = await new Promise((resolve) => {
        const collectedOperationNames = new Set();
        const operationInfoMap = {};
        // オリジナルの Function.prototype.call を保存
        const originalCall = Function.prototype.call;
        // Function.prototype.call を上書きする
        Function.prototype.call = function (thisArg, ...args) {
            const module = args[0];
            const ret = originalCall.apply(this, [thisArg, ...args]);
            try {
                const exp = module.exports;
                if (exp.operationName) {
                    operationInfoMap[exp.operationName] = exp;
                    collectedOperationNames.add(exp.operationName);
                    // 必要な operationInfo が全て揃ったかチェック
                    const isAllCollected = Array.from(requiredOperationNames).every(
                        name => collectedOperationNames.has(name)
                    );
                    if (isAllCollected) {
                        // Function.prototype.call を元に戻す
                        Function.prototype.call = originalCall;
                        resolve(operationInfoMap);
                    }
                }
            } catch (_) {}
            return ret;
        };
    });
    console.log("operationInfoMap:", operationInfoMap);

    // Twitter Web App が内部で使用している API クライアント実装のオブジェクトを収集
    const apiClient = await new Promise((resolve) => {
        // オリジナルの Function.prototype.apply を保存
        const __origApply = Function.prototype.apply;
        // Function.prototype.apply を上書きする
        Function.prototype.apply = function (thisArg, argsArray) {
            if (thisArg && typeof thisArg === 'object' && thisArg.dispatch === this) {
                // Function.prototype.apply を元に戻す
                Function.prototype.apply = __origApply;
                resolve(thisArg);
            }
            return __origApply.call(this, thisArg, argsArray);
        };
    });
    console.log("apiClient:", apiClient);

    // API クライアントのラッパーを作成し、これを window オブジェクトに公開する
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
            const operationInfo = operationInfoMap[operationName]
            // HTTP リクエストを実行
            // X-Client-Transaction-ID や各ヘッダーの付与はすべて内部で行われる
            // XHR フックで生のレスポンスを取得するため、戻り値は使用しない
            if (additionalFlags) {
                // 第三引数はおそらくサーバーからエラーが返された際に致命的なエラーかをチェックする関数
                await apiClient.graphQL(operationInfo, requestPayload, () => false, additionalFlags);
            } else {
                await apiClient.graphQL(operationInfo, requestPayload);
            }
            // XMLHttpRequest を元に戻す
            window.XMLHttpRequest = OriginalXHR;
            // API レスポンスを返す
            return {
                parsedResponse: responseData.parsedResponse,
                responseText: responseData.responseText,
                statusCode: responseData.statusCode,
                headers: responseData.headers,
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
