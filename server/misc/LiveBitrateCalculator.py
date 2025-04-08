#!/usr/bin/env python3

# Usage: poetry run python -m misc.LiveBitrateCalculator

import time
from concurrent.futures import ThreadPoolExecutor

import requests
import typer


app = typer.Typer()

@app.command()
def main():

    BASE_API_URL = 'https://my.local.konomi.tv:7000/api/streams/live/gr011/{}/mpegts'
    DURATION = 10 * 60  # 10 minutes in seconds
    BUFFER_SIZE = 1024
    QUALITIES = ['240p', '360p', '480p', '540p', '720p', '810p', '1080p', '1080p-60fps']

    def get_stream_data(quality: str, codec: str = '') -> tuple[str, str, float, float]:
        start_time = time.time()
        total_data_received = 0
        api_url = BASE_API_URL.format(f'{quality}{codec}')

        print(f'Getting data for {quality}{codec} stream...')
        with requests.get(api_url, stream=True) as response:
            for chunk in response.iter_content(chunk_size=BUFFER_SIZE):
                total_data_received += len(chunk)
                elapsed_time = time.time() - start_time

                if elapsed_time >= DURATION:
                    break

        one_hour_data_usage = (total_data_received * 6) / 1e9  # in GB
        average_bitrate = (one_hour_data_usage * 8 * 1e3) / 3600  # in Mbps

        return quality, codec, one_hour_data_usage, average_bitrate

    def print_results(results: list[tuple[str, str, float, float]], codec: str = '') -> None:
        if codec == '':
            real_codec = 'H.264/AVC'
        else:
            real_codec = 'H.265/HEVC'
        print(f'{"-" * 30}\nResults for {real_codec} streams\n{"-" * 30}')
        for quality, _, data_usage, bitrate in results:
            print(f'{quality}{codec}:')
            print(f'  1時間あたりのデータ量: {data_usage:.2f} GB/h')
            print(f'  平均ビットレート: {bitrate:.1f} Mbps')

    with ThreadPoolExecutor() as executor:
        # H.264 streams
        h264_results = list(executor.map(get_stream_data, QUALITIES, [''] * len(QUALITIES)))

        # HEVC streams
        hevc_results = list(executor.map(get_stream_data, QUALITIES, ['-hevc'] * len(QUALITIES)))

    print_results(h264_results)
    print_results(hevc_results, codec='-hevc')


if __name__ == '__main__':
    app()
