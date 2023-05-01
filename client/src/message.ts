
import { MessageOption, MessageType } from 'vuetify-message-snackbar/src/message';


interface MessageReturnValue {
    close(): void;
    again(): void;
}

// Vue コンポーネント以外からも this.$message を使えるようにするための (強引な) ラッパー
export default {
    success(message: MessageType | MessageOption): MessageReturnValue {
        // @ts-ignore
        return window.KonomiTVVueInstance?.$message.success(message);
    },
    info(message: MessageType | MessageOption): MessageReturnValue {
        // @ts-ignore
        return window.KonomiTVVueInstance?.$message.info(message);
    },
    warning(message: MessageType | MessageOption): MessageReturnValue {
        // @ts-ignore
        return window.KonomiTVVueInstance?.$message.warning(message);
    },
    error(message: MessageType | MessageOption): MessageReturnValue {
        // @ts-ignore
        return window.KonomiTVVueInstance?.$message.error(message);
    },
    show(message: MessageType | MessageOption): MessageReturnValue {
        // @ts-ignore
        return window.KonomiTVVueInstance?.$message.show(message);
    }
};
