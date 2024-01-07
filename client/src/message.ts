
import { useSnackbarsStore } from '@/stores/SnackbarsStore';


export default {
    success(message: string, timeout?: number): void {
        useSnackbarsStore().show('success', message, timeout);
    },
    info(message: string, timeout?: number): void {
        useSnackbarsStore().show('info', message, timeout);
    },
    warning(message: string, timeout?: number): void {
        useSnackbarsStore().show('warning', message, timeout);
    },
    error(message: string, timeout?: number): void {
        useSnackbarsStore().show('error', message, timeout);
    },
    show(message: string, timeout?: number): void {
        useSnackbarsStore().show('default', message, timeout);
    }
};
