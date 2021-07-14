
import re


class LiveStreamID:

    @staticmethod
    def buildLiveStreamID(network_id:int, service_id:int, quality:str) -> str:
        """ライブストリーム ID を組み立てる

        Args:
            netword_id (int): ネットワーク ID (NID)
            service_id (int): サービス ID (SID)
            quality (str): 映像の品質 (1080p ~ 360p)

        Returns:
            str: ライブストリーム ID
        """

        return f'Live_NID{str(network_id)}-SID{str(service_id)}_{quality}'


    @staticmethod
    def parseLiveStreamID(livestream_id:str) -> tuple:
        """ライブストリーム ID から NID・SID・映像の品質 をタプルで返す

        Args:
            livestream_id (str): [description]

        Returns:
            tuple: [description]
        """

        match = re.match(r'^Live_NID([0-9]+)-SID([0-9]+)_([0-9]+p)$', livestream_id)

        return int(match.group(1)), int(match.group(2)), match.group(3)
