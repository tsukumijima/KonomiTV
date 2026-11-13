
import { toRaw } from 'vue';

import { IChannel } from '@/services/Channels';
import { IProgram } from '@/services/Programs';
import { IRecordSettings, IRecordSettingsDefault, IReservation } from '@/services/Reservations';


/**
 * 録画予約周りのユーティリティ
 */
export class ReservationUtils {

    /**
     * 録画予約のない番組を、録画予約と同じ部品で表示するための仮の録画予約データを作成する
     * 仮の録画予約データの id は -1 で、録画予約の部品はこの値から録画予約のない番組だと判別する
     * @param program 番組情報
     * @param channel 番組のチャンネル情報 (チャンネル情報を取得できていない場合は null)
     * @param record_settings 録画設定の既定値 (取得できていない場合は null)
     * @returns 仮の録画予約データ
     */
    static createUnreservedReservation(
        program: IProgram,
        channel: IChannel | null,
        record_settings: IRecordSettings | null,
    ): IReservation {

        // チャンネル情報を取得できていない場合は、番組情報から最低限のチャンネル情報を組み立てる
        const fallbackChannel: IChannel = {
            id: program.channel_id,
            display_channel_id: program.channel_id,
            network_id: program.network_id,
            service_id: program.service_id,
            transport_stream_id: null,
            remocon_id: 0,
            channel_number: '---',
            type: 'GR',
            name: program.channel_id,
            terrestrial_regions: null,
            jikkyo_force: null,
            is_subchannel: false,
            is_radiochannel: false,
            is_watchable: true,
        };

        return {
            id: -1,
            channel: channel ?? fallbackChannel,
            program,
            is_recording_in_progress: false,
            recording_availability: 'Full',
            comment: '',
            scheduled_recording_file_name: '',
            estimated_recording_file_size: 0,
            // 録画予約ごとに録画設定を変更できるよう、既定値を複製して持たせる
            record_settings: structuredClone(toRaw(record_settings ?? IRecordSettingsDefault)),
        };
    }
}
