
import Vue from 'vue';
import { VSnackbar, VBtn, VIcon } from 'vuetify/lib';
import Vuetify from 'vuetify/lib/framework';

Vue.use(Vuetify);

// vuetify-message-snackbar を使うのに必要
Vue.component('v-snackbar', VSnackbar);
Vue.component('v-btn', VBtn);
Vue.component('v-icon', VIcon);

export default new Vuetify({
    theme: {
        dark: true,
        themes: {
            dark: {
                primary: '#E64F97',
                secondary: '#E33157',
                twitter: {
                    base: '#4F82E6',
                    lighten1: '#799FEC',
                    lighten2: '#41A5F1',
                },
                gray: '#66514C',
                black: '#110A09',
                background: {
                    base: '#1E1310',
                    lighten1: '#2F221F',
                    lighten2: '#433532',
                    lighten3: '#4c3c38',
                },
                text: {
                    base: '#FFEAEA',
                    darken1: '#D9C7C7',
                    darken2: '#8E7F7E',
                    darken3: '#786968',
                }
            }
        },
        options: {
            customProperties: true,
        },
    },
});
