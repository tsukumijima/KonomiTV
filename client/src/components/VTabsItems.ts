
import { VueConstructor } from 'vue';

import { GroupableInstance } from 'vuetify/lib/components/VItemGroup/VItemGroup';
import VTabsItems from 'vuetify/lib/components/VTabs/VTabsItems';

// VTabsItems は VItemGroup と VWindow を extend() して実装されている
export default (VTabsItems as VueConstructor).extend({
    data() {
        return {
            // 一応型定義をしておく
            items: [] as GroupableInstance[],
        }
    },
    methods: {

        // タブのデータ配列の先頭に新しい要素が追加されるとそのタブのアニメーションの向きが逆になるバグがあるので、VItemGroup 側の挙動をオーバーライドする
        // DOM 上も VNode 上も正しい順序で並んでいるが、this.items に関しては追加された順になっていてしまっていて齟齬が発生するのが原因
        // ref: https://github.com/vuetifyjs/vuetify/issues/13862
        register(item: GroupableInstance) {

            // 現在アクティブなタブの VueComponent を取得
            const activeItem = this.items[(this as any).internalIndex];

            // 要素を items に追加
            this.items.push(item);

            // this.$slots.default に VNode が、items には単に VueComponent が入っているので、事前に VNode の順番に合わせて並べ替える
            // こうすることで、追加された順ではなく元のデータ配列通りの順番になる
            this.items.sort((a, b) => {

                // VueComponent の key が一致する this.$slots.default 内の VNode を探す
                const index_a = this.$slots.default.findIndex((element) => {
                    return a.$vnode.key === element.key;
                });
                const index_b = this.$slots.default.findIndex((element) => {
                    return b.$vnode.key === element.key;
                });

                // index 順で並び替え
                return index_a - index_b;
            });

            item.$on('change', () => (this as any).onClick(item));
            if ((this as any).mandatory && !(this as any).selectedValues.length) {
                (this as any).updateMandatory();
            }

            // 追加された要素のソート後のインデックスを取得して更新する
            (this as any).updateItem(item, this.items.indexOf(item));

            // ソート後の現在アクティブなタブのインデックスを取得し直し、設定する
            // 配列の末尾以外に追加された場合はインデックスが1つずつずれてしまうため、インデックスを設定し直す必要がある
            if (activeItem !== undefined) {
                (this as any).updateInternalValue(this.items.indexOf(activeItem));
            }
        },

        unregister(item: GroupableInstance) {

            // 現在アクティブなタブの VueComponent を取得
            const activeItem = this.items[(this as any).internalIndex];

            // 継承元の unregister() の処理を呼び出す（いわゆる super() ）
            // ref: https://github.com/vuejs/vue/issues/2977
            (this.constructor as any).super.options.methods.unregister.call(this, item);

            // 配列の末尾以外から削除された場合はインデックスが1つずつずれてしまうため、インデックスを設定し直す必要がある
            if (activeItem !== undefined) {
                (this as any).updateInternalValue(this.items.indexOf(activeItem));
            }
        },

        // 最初のタブから最後のタブに遷移するとアニメーションの向きが逆になるバグがあるので、VWindow 側の挙動をオーバーライドする
        // 本来は VCarousel 用の動作だが、VTabsItems も VWindow を継承しているので、それが適用されてしまっているらしい
        // ref: https://github.com/yuwu9145/vuetify/blob/master/packages/vuetify/src/components/VWindow/VWindow.ts#L239-L252
        updateReverse(val: number, oldVal: number) {

            const itemsLength = this.items.length;
            const lastIndex = itemsLength - 1;

            if (itemsLength <= 2) return val < oldVal;

            // continuous が false の時、常に val < oldVal の結果を返す
            if (!(this as any).continuous) return val < oldVal;

            if (val === lastIndex && oldVal === 0) {
                return true;
            } else if (val === 0 && oldVal === lastIndex) {
                return false;
            } else {
                return val < oldVal;
            }
        }
    }
});
