import{d as p,m as A,u as f,_ as v,k as b,h as _,a as s,b as t,w as g,r as D,c as d,l as o,V as c,g as C,F as E,o as l,R as B}from"./index-B7OgWKtM.js";import{V,a as w}from"./VCard-CZrRuC1N.js";import{V as h}from"./ssrBoot-CgU2lsL7.js";import{V as r}from"./VSwitch-C4l78BkV.js";import{c as F}from"./VTextField-Cn4WKwf3.js";import{d as y}from"./VSelect-9qvNrm53.js";import{V as S}from"./VDialog-B5uyaSNw.js";const k=p({name:"CommentMuteSettings",props:{modelValue:{type:Boolean,required:!0}},emits:{"update:modelValue":e=>!0},data(){return{comment_mute_settings_modal:!1,muted_comment_keyword_match_type:[{title:"部分一致",value:"partial"},{title:"前方一致",value:"forward"},{title:"後方一致",value:"backward"},{title:"完全一致",value:"exact"},{title:"正規表現",value:"regex"}]}},computed:{...A(f)},watch:{modelValue(){this.comment_mute_settings_modal=this.modelValue},comment_mute_settings_modal(){this.$emit("update:modelValue",this.comment_mute_settings_modal)}}}),U={class:"px-5 pb-6"},$={class:"text-subtitle-1 d-flex align-center font-weight-bold mt-4"},M={class:"settings__item settings__item--switch"},Z={class:"settings__item settings__item--switch"},x={class:"settings__item settings__item--switch"},j={class:"settings__item settings__item--switch"},z={class:"settings__item settings__item--switch"},I={class:"settings__item settings__item--switch"},H={class:"text-subtitle-1 d-flex align-center font-weight-bold mt-4"},L={class:"muted-comment-items"},N=["onClick"],T={class:"text-subtitle-1 d-flex align-center font-weight-bold mt-4"},O={class:"muted-comment-items"},R=["onClick"];function q(e,u,G,J,K,P){const n=D("Icon");return l(),b(S,{"max-width":"770",transition:"slide-y-transition",modelValue:e.comment_mute_settings_modal,"onUpdate:modelValue":u[9]||(u[9]=i=>e.comment_mute_settings_modal=i)},{default:_(()=>[s(w,{class:"comment-mute-settings"},{default:_(()=>[s(V,{class:"px-5 pt-6 pb-3 d-flex align-center font-weight-bold",style:{height:"60px"}},{default:_(()=>[s(n,{icon:"heroicons-solid:filter",height:"26px"}),u[10]||(u[10]=t("span",{class:"ml-3"},"コメントのミュート設定",-1)),s(h),g((l(),d("div",{class:"d-flex align-center rounded-circle cursor-pointer px-2 py-2",onClick:u[0]||(u[0]=i=>e.comment_mute_settings_modal=!1)},[s(n,{icon:"fluent:dismiss-12-filled",width:"23px",height:"23px"})])),[[B]])]),_:1}),t("div",U,[t("div",$,[s(n,{icon:"fa-solid:sliders-h",width:"24px",height:"20px"}),u[11]||(u[11]=t("span",{class:"ml-2"},"クイック設定",-1))]),t("div",M,[u[12]||(u[12]=t("label",{class:"settings__item-heading",for:"mute_vulgar_comments"}," 露骨な表現を含むコメントをミュートする ",-1)),u[13]||(u[13]=t("label",{class:"settings__item-label",for:"mute_vulgar_comments"},[o(" 性的な単語などの露骨・下品な表現を含むコメントを、一括でミュートするかを設定します。"),t("br")],-1)),s(r,{class:"settings__item-switch",color:"primary",id:"mute_vulgar_comments","hide-details":"",modelValue:e.settingsStore.settings.mute_vulgar_comments,"onUpdate:modelValue":u[1]||(u[1]=i=>e.settingsStore.settings.mute_vulgar_comments=i)},null,8,["modelValue"])]),t("div",Z,[u[14]||(u[14]=t("label",{class:"settings__item-heading",for:"mute_abusive_discriminatory_prejudiced_comments"}," ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする ",-1)),u[15]||(u[15]=t("label",{class:"settings__item-label",for:"mute_abusive_discriminatory_prejudiced_comments"},[o(" 『死ね』『殺す』などのネガティブな表現、特定の国や人々への差別的な表現、政治的に偏った表現を含むコメントを、一括でミュートするかを設定します。"),t("br")],-1)),s(r,{class:"settings__item-switch",color:"primary",id:"mute_abusive_discriminatory_prejudiced_comments","hide-details":"",modelValue:e.settingsStore.settings.mute_abusive_discriminatory_prejudiced_comments,"onUpdate:modelValue":u[2]||(u[2]=i=>e.settingsStore.settings.mute_abusive_discriminatory_prejudiced_comments=i)},null,8,["modelValue"])]),t("div",x,[u[16]||(u[16]=t("label",{class:"settings__item-heading",for:"mute_big_size_comments"}," 文字サイズが大きいコメントをミュートする ",-1)),u[17]||(u[17]=t("label",{class:"settings__item-label",for:"mute_big_size_comments"},[o(" 通常より大きい文字サイズで表示されるコメントを、一括でミュートするかを設定します。"),t("br"),o(" 文字サイズが大きいコメントには迷惑なコメントが多いです。基本的にはオンにしておくのがおすすめです。"),t("br")],-1)),s(r,{class:"settings__item-switch",color:"primary",id:"mute_big_size_comments","hide-details":"",modelValue:e.settingsStore.settings.mute_big_size_comments,"onUpdate:modelValue":u[3]||(u[3]=i=>e.settingsStore.settings.mute_big_size_comments=i)},null,8,["modelValue"])]),t("div",j,[u[18]||(u[18]=t("label",{class:"settings__item-heading",for:"mute_fixed_comments"}," 映像の上下に固定表示されるコメントをミュートする ",-1)),u[19]||(u[19]=t("label",{class:"settings__item-label",for:"mute_fixed_comments"},[o(" 映像の上下に固定された状態で表示されるコメントを、一括でミュートするかを設定します。"),t("br"),o(" 固定表示されるコメントが煩わしい方におすすめです。"),t("br")],-1)),s(r,{class:"settings__item-switch",color:"primary",id:"mute_fixed_comments","hide-details":"",modelValue:e.settingsStore.settings.mute_fixed_comments,"onUpdate:modelValue":u[4]||(u[4]=i=>e.settingsStore.settings.mute_fixed_comments=i)},null,8,["modelValue"])]),t("div",z,[u[20]||(u[20]=t("label",{class:"settings__item-heading",for:"mute_colored_comments"}," 色付きのコメントをミュートする ",-1)),u[21]||(u[21]=t("label",{class:"settings__item-label",for:"mute_colored_comments"},[o(" 白以外の色で表示される色付きのコメントを、一括でミュートするかを設定します。"),t("br"),o(" この設定をオンにしておくと、目立つ色のコメントを一掃できます。"),t("br")],-1)),s(r,{class:"settings__item-switch",color:"primary",id:"mute_colored_comments","hide-details":"",modelValue:e.settingsStore.settings.mute_colored_comments,"onUpdate:modelValue":u[5]||(u[5]=i=>e.settingsStore.settings.mute_colored_comments=i)},null,8,["modelValue"])]),t("div",I,[u[22]||(u[22]=t("label",{class:"settings__item-heading",for:"mute_consecutive_same_characters_comments"}," 8文字以上同じ文字が連続しているコメントをミュートする ",-1)),u[23]||(u[23]=t("label",{class:"settings__item-label",for:"mute_consecutive_same_characters_comments"},[o(" 『wwwwwwwwwww』『あばばばばばばばばば』など、8文字以上同じ文字が連続しているコメントを、一括でミュートするかを設定します。"),t("br"),o(" しばしばあるテンプレコメントが煩わしい方におすすめです。"),t("br")],-1)),s(r,{class:"settings__item-switch",color:"primary",id:"mute_consecutive_same_characters_comments","hide-details":"",modelValue:e.settingsStore.settings.mute_consecutive_same_characters_comments,"onUpdate:modelValue":u[6]||(u[6]=i=>e.settingsStore.settings.mute_consecutive_same_characters_comments=i)},null,8,["modelValue"])]),t("div",H,[s(n,{icon:"fluent:comment-dismiss-20-filled",width:"24px"}),u[25]||(u[25]=t("span",{class:"ml-2 mr-2"},"ミュート済みのキーワード",-1)),s(c,{class:"ml-auto",color:"background-lighten-1",variant:"flat",onClick:u[7]||(u[7]=i=>e.settingsStore.settings.muted_comment_keywords.unshift({match:"partial",pattern:""}))},{default:_(()=>[s(n,{icon:"fluent:add-12-filled",height:"17px"}),u[24]||(u[24]=t("span",{class:"ml-1"},"追加",-1))]),_:1})]),t("div",L,[(l(!0),d(E,null,C(e.settingsStore.settings.muted_comment_keywords,(i,m)=>(l(),d("div",{class:"muted-comment-item",key:m},[s(F,{type:"search",class:"muted-comment-item__input",color:"primary",density:"compact",variant:"outlined","hide-details":"",placeholder:"ミュートするキーワードを入力",modelValue:e.settingsStore.settings.muted_comment_keywords[m].pattern,"onUpdate:modelValue":a=>e.settingsStore.settings.muted_comment_keywords[m].pattern=a},null,8,["modelValue","onUpdate:modelValue"]),s(y,{class:"muted-comment-item__match-type",color:"primary",density:"compact",variant:"outlined","hide-details":"",items:e.muted_comment_keyword_match_type,modelValue:e.settingsStore.settings.muted_comment_keywords[m].match,"onUpdate:modelValue":a=>e.settingsStore.settings.muted_comment_keywords[m].match=a},null,8,["items","modelValue","onUpdate:modelValue"]),g((l(),d("button",{class:"muted-comment-item__delete-button",onClick:a=>e.settingsStore.settings.muted_comment_keywords.splice(e.settingsStore.settings.muted_comment_keywords.indexOf(i),1)},u[26]||(u[26]=[t("svg",{class:"iconify iconify--fluent",width:"20px",height:"20px",viewBox:"0 0 16 16"},[t("path",{fill:"currentColor",d:"M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"})],-1)]),8,N)),[[B]])]))),128))]),t("div",T,[s(n,{icon:"fluent:person-prohibited-20-filled",width:"24px"}),u[28]||(u[28]=t("span",{class:"ml-2 mr-2"},"ミュート済みのニコニコユーザー ID",-1)),s(c,{class:"ml-auto",color:"background-lighten-1",variant:"flat",onClick:u[8]||(u[8]=i=>e.settingsStore.settings.muted_niconico_user_ids.unshift(""))},{default:_(()=>[s(n,{icon:"fluent:add-12-filled",height:"17px"}),u[27]||(u[27]=t("span",{class:"ml-1"},"追加",-1))]),_:1})]),t("div",O,[(l(!0),d(E,null,C(e.settingsStore.settings.muted_niconico_user_ids,(i,m)=>(l(),d("div",{class:"muted-comment-item",key:m},[s(F,{type:"search",class:"muted-comment-item__input",color:"primary",density:"compact",variant:"outlined","hide-details":"",placeholder:"ミュートするニコニコユーザー ID を入力",modelValue:e.settingsStore.settings.muted_niconico_user_ids[m],"onUpdate:modelValue":a=>e.settingsStore.settings.muted_niconico_user_ids[m]=a},null,8,["modelValue","onUpdate:modelValue"]),g((l(),d("button",{class:"muted-comment-item__delete-button",onClick:a=>e.settingsStore.settings.muted_niconico_user_ids.splice(e.settingsStore.settings.muted_niconico_user_ids.indexOf(i),1)},u[29]||(u[29]=[t("svg",{class:"iconify iconify--fluent",width:"20px",height:"20px",viewBox:"0 0 16 16"},[t("path",{fill:"currentColor",d:"M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"})],-1)]),8,R)),[[B]])]))),128))])])]),_:1})]),_:1},8,["modelValue"])}const su=v(k,[["render",q],["__scopeId","data-v-0638398d"]]);export{su as C};
