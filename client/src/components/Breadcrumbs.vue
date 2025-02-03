<template>
    <div class="breadcrumbs">
        <router-link v-for="(crumb, index) in crumbs" :key="index"
            :to="crumb.path"
            class="breadcrumbs__item"
            :class="{'breadcrumbs__item--disabled': crumb.disabled}"
            :event="crumb.disabled ? '' : 'click'">
            <span class="breadcrumbs__item-text">{{crumb.name}}</span>
            <Icon v-if="index < crumbs.length - 1" icon="fluent:chevron-right-12-regular" width="16px" class="breadcrumbs__item-separator" />
        </router-link>
    </div>
</template>
<script lang="ts" setup>


// Props
defineProps<{
    crumbs: {
        name: string;
        path: string;
        disabled?: boolean;
    }[];
}>();

</script>
<style lang="scss" scoped>

.breadcrumbs {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 13px;
    @include smartphone-vertical {
        display: none;
    }

    &__item {
        display: flex;
        align-items: center;
        color: rgb(var(--v-theme-text-darken-1));
        text-decoration: none;

        &:not(&--disabled):hover {
            text-decoration: underline;
        }

        &--disabled {
            color: #b8aead;
            cursor: default;
            pointer-events: none;
        }

        &-separator {
            color: #b8aead;
            margin-left: 2px;
            margin-right: 4px;
        }
    }
}

</style>