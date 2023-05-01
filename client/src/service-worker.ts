/* eslint-disable no-console */

import { register } from 'register-service-worker';

import Message from '@/message';
import Utils from '@/utils';


if (process.env.NODE_ENV === 'production') {
    register(`${process.env.BASE_URL}service-worker.js`, {
        ready() {
            console.log(
                'App is being served from cache by a service worker.\n' +
                'For more details, visit https://goo.gl/AFskqB'
            );
        },
        registered() {
            console.log('Service worker has been registered.');
        },
        cached() {
            console.log('Content has been cached for offline use.');
        },
        updatefound() {
            console.log('New content is downloading.');
        },
        updated(registration: ServiceWorkerRegistration) {
            console.log('New content is available; please refresh.');
            Message.show({
                message: 'クライアントが新しいバージョンに更新されました。5秒後にリロードします。',
                timeout: 10000,  // リロードするまで表示し続ける
            });
            // PWA (Service Worker) を更新する
            registration.waiting.postMessage({type: 'SKIP_WAITING'});
            registration.waiting.addEventListener('statechange', async (event) => {
                if ((event.target as ServiceWorker).state === 'activated') {
                    await Utils.sleep(4);  // activated になるまで少し時間がかかるので、1秒減らして4秒待つ
                    location.reload(true);
                }
            });
        },
        offline() {
            console.log('No internet connection found. App is running in offline mode.');
        },
        error(error) {
            console.error('Error during service worker registration:', error);
        }
    });
}
