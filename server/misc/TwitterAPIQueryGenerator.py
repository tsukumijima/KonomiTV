#!/usr/bin/env python3

# Usage: poetry run python -m misc.TwitterAPIQueryGenerator

import json
import re
import sys
import urllib.parse

from rich import print
from rich.rule import Rule


def main():

    print(Rule(characters='='))
    print('Chrome DevTools の Network タブで「fetch としてコピー」したコードを貼り付けてください。')
    print('2回 Enter を押すと続行します。')
    print(Rule(characters='='))
    fetch_code = ''
    while True:
        line = sys.stdin.readline()
        if line == '\n':
            break
        fetch_code += line
    fetch_code = fetch_code.strip()
    print(Rule(characters='='))

    # query_idとendpointを抽出
    query_id_match = re.search(r'/i/api/graphql/([^/]+)/([^"?]+)', fetch_code)
    if not query_id_match:
        print('query_id と endpoint の抽出に失敗しました。')
        print(Rule(characters='='))
        return
    query_id = query_id_match.group(1)
    endpoint = query_id_match.group(2)

    # リクエストメソッドを判定
    method_match = re.search(r'"method"\s*:\s*"(GET|POST)"', fetch_code)
    if not method_match:
        print('リクエストメソッドの判定に失敗しました。')
        print(Rule(characters='='))
        return
    method = method_match.group(1)

    if method == 'POST':
        # POST リクエストの場合、fetch() コードの第二引数にある {} で囲まれたオブジェクトを正規表現で抽出したものを JSON としてパース
        body_match = re.search(r'"body"\s*:\s*"({.*})"', fetch_code, re.DOTALL)
        if not body_match:
            print('body の抽出に失敗しました。')
            print(Rule(characters='='))
            return
        body_json_str = body_match.group(1).replace('\\', '')
        body_json = json.loads(body_json_str)
        features = body_json.get('features', None)
    else:
        # GET リクエストの場合、まず URL を抽出
        url_match = re.search(r'"(https?://[^"]+)"', fetch_code)
        if not url_match:
            print('URL の抽出に失敗しました。')
            print(Rule(characters='='))
            return
        url = url_match.group(1)

        # URL をパースして query string を取得
        parsed_url = urllib.parse.urlparse(url)
        query_string = parsed_url.query

        # query string を dict 形式にパース
        query_dict = urllib.parse.parse_qs(query_string)

        # features を取得
        features_json_str = query_dict.get('features', [None])[0]
        if features_json_str is None:
            features = None
        else:
            try:
                features = json.loads(features_json_str)
            except json.JSONDecodeError:
                print('features の JSON パースに失敗しました。features は None として続行します。')
                features = None

    # features を JSON としてフォーマットした後、Python の dict として正しい形式に変換
    # " を ' に置換し、true/false を True/False に置換
    features = json.dumps(features, indent=4, ensure_ascii=False)
    features = features.replace('"', '\'')
    features = features.replace('true', 'True')
    features = features.replace('false', 'False')
    # 最後にケツカンマがないので追加
    features = features.replace('e\n}', 'e,\n}')
    # インデントを追加
    features = features.replace('\n', '\n            ')
    # null を None に変更
    features = features.replace('null', 'None')

    # 生成するコードをフォーマット
    print('以下のコードを TwitterGraphQLAPI.py にコピペしてください。')
    print(Rule(characters='='))
    generated_code = f"""
        '{endpoint}': schemas.TwitterGraphQLAPIEndpointInfo(
            method = '{method}',
            query_id = '{query_id}',
            endpoint = '{endpoint}',
            features = {features},
        ),
    """
    print(generated_code)
    print(Rule(characters='='))


if __name__ == '__main__':
    main()
