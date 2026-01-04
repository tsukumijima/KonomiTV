import { registerPlugin } from '@capacitor/core';
const App = registerPlugin('App', {
    web: () => import('./web').then((m) => new m.AppWeb()),
});
export * from './definitions';
export { App };
//# sourceMappingURL=index.js.map