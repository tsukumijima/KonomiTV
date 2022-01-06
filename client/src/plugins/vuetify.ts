
import Vue from 'vue';
import Vuetify from 'vuetify/lib/framework';

Vue.use(Vuetify);

export default new Vuetify({
    theme: {
        dark: true,
        themes: {
            dark: {
                primary: '#E64F97',
                secondary: '#E64F97',
                twitter: '#4F82E6',
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
