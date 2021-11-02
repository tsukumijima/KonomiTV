<script lang="ts">

import VTabsItems from 'vuetify/lib/components/VTabs/VTabsItems';

export default VTabsItems.extend({
    methods: {
        // 最初のタブから最後のタブに遷移するとアニメーションの向きが逆になるバグがあるので、VWindow 側の挙動をオーバーライドする
        // 本来は VCarousel 用の動作だが、VTabsItems も VWindow を継承しているので、それが適用されてしまっているらしい
        // ref: https://github.com/yuwu9145/vuetify/blob/master/packages/vuetify/src/components/VWindow/VWindow.ts#L239-L252
        updateReverse (val: number, oldVal: number) {
            const itemsLength = (this as any).items.length
            const lastIndex = itemsLength - 1

            if (itemsLength <= 2) return val < oldVal;

            // continuous が false の時、常に val < oldVal の結果を返す
            if (!(this as any).continuous) return val < oldVal;

            if (val === lastIndex && oldVal === 0) {
                return true
            } else if (val === 0 && oldVal === lastIndex) {
                return false
            } else {
                return val < oldVal
            }
        },
    }
});

</script>