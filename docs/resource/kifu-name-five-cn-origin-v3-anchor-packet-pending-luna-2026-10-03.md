# 五名中文原名的完整 v3 来源锚点包（pending）

受保护包：~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-v3-anchor-packet-luna/。producer-only；未自审、未连接数据库或克隆、未写库、未改代码。

范围按冻结库存中的精确 (album_id, side, raw) 三元组，共 **4,358**：唐韦星 858、杨鼎新 864、檀啸 911、胡耀宇 868、连笑 857。包含5条 anchor_format=3 完整待审记录；每条保留 CWA official roster、同 ID/生日 GoRatings zh bridge、同 ID/生日 GoRatings en published reading 三条原始来源及正文 hash。与已有独立五主语言审查的25个 exact 候选格建立引用；逐格来源正文已随包保留。

分词提案为 Tang Weixing→tang | wei-xing、Yang Dingxin→yang | ding-xin、Tan Xiao→tan | xiao、Hu Yaoyu→hu | yao-yu、Lian Xiao→lian | xiao。六个次语言批次共30格：de/es/fr/tr 复用原已签规则；ru/ua 规则仅对缺失的 tan、hu、lian 提交新增表项，并复用其余9个在119 token独立评审中已PASS的表项。10个俄/乌候选分别为 Тан Вэйсин、Ян Динсинь、Тань Сяо、Ху Яоюй、Лянь Сяо，以及 Тан Вейсін、Ян Дінсінь、Тань Сяо、Ху Яоюй、Лянь Сяо；全部待审，未扩展其他音节。

离线 structural check 确认 scope 计数、3-source identity/name/DOB/reading 关系、25个主五语正文 hash 和有限候选引用均匹配。validation.producer.pending.json 记录全 bundle **not ready**：5个raw anchors、两条新规则和六个批次都尚无独立签署，也未绑定目标前像/approved-name snapshot。该状态是待审核材料包，不是写入许可。

Protected manifest.pending.json SHA-256: 51fad4bc71b5f7d7c9747130fc9ac4d92976f815076f9ad46dfc272a5e45fb6b。
