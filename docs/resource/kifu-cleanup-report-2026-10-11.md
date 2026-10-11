# 棋谱库清理 · 实际结果

2026-10-11 · 正式库快照 2026-10-11T16:47:15.915781+00:00 · 名称批次 724

TEST 与 PROD 的清理和名称入库均已实际完成并核验。正式库现存 171,272 盘，其中公开 171,013 盘；以下覆盖率由清理后的全量实际快照计算。

## 用户四项事项

| 事项 | 实际结果 |
| --- | --- |
| 1 · 删除不可识别记录 | 两库各删除1,753盘；现存171,272盘，公开171,013、隐藏250、重复9。 |
| 2 · 清理姓名与段位 | 343盘文本清理，其中2盘后续又修正了另一位棋手；80盘涉及111个段位字段。姓名和段位分开保存，原SGF与来源不改。 |
| 3 · 补齐原始棋手五语 | TEST 304个、PROD 291个原始棋手owner；实际写入名称格分别1,391、1,330。 |
| 4 · 补齐赛事原文五语 | TEST 954个原文owner、4,467格；PROD 954个原文owner、4,467格。原文owner不是独立赛事类型。 |

## 覆盖率

| 口径 | 完成 / 实际分母 | 比例 |
| --- | --- | --- |
| 实体宽口径 · fixedwide | 155,499 / 171,272 | 90.79% |
| 真实五语言卡片 · strictcomplete | 171,013 / 171,272 | 99.85% |
| 公开实际完整卡片 | 171,013 / 171,013 | 100.00% |
| 规范棋手五语 · P5 | 3,663 / 3,689 | 99.30% |
| 规范赛事类型五语 · E5 | 84 / 85 | 98.82% |

公开卡片仍缺 0 盘。

规范赛事类型分母使用实际canonical总数；赛事原文owner单列，不把标题数量称为独立赛事数量。

实体宽口径：有直接event_id时，黑白双方canonical棋手与canonical赛事名称须五语合格；没有直接event_id时，按严格卡片完整计入。

真实五语言卡片按cn/tw/jp/ko/en的双方姓名和具体赛事显示全部获得原生读取资格统计；可使用合格raw-name，因此可高于实体宽口径。

公开完整卡片由public_visible减去missing_cards中public=true的数量计算。

生成首译属于显示资格；上述比例不是全库语义正确率，也不等于全库人工逐卡检查。

零棋局实体指完整清理后inventory中没有直接canonical ID关联；仍保留在P5/E5分母中。

正式库吴清源杯已存五语显示值；其中简体、繁体、日文、英文为缺少研究证据记录的旧审核种子行，因此不计入严格规范赛事五语资格。该赛事没有直接关联棋局，本轮保留其现值及来源。

## 姓名与段位清理样例

| 清理前 | 姓名 | 原文段位片段 | 简体 | 繁体 | 日本語 | 한국어 | English |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 彭景华五品 | 彭景华 | 五品 | 彭景华 | 彭景華 | 彭景華 | 펑징화 | Peng Jinghua |
| 周俊勋六品 | 周俊勋 | 六品 | 周俊勋 | 周俊勳 | 周俊勲 | 저우쥔쉰 | Chou Chun-hsun |
| 崔珪昞]BR[九段 | 崔珪昞 | 九段 | 崔珪昞 | 崔珪昞 | 崔珪昞 | 최규병 | Choi Kyubyeong |

样例取自实际清理决策的精简字段。BR属于黑方段位，WR属于白方段位；相邻姓名不决定段位归属。保留原值，不展示SGF全文。

## 未覆盖但零直接关联棋局的规范实体

| 实体 | ID | 名称 | 缺少语言 | 直接关联槽位 |
| --- | --- | --- | --- | --- |
| 棋手 | 133 | 慧领柳承熙 | cn, tw, jp, ko, en | 0 |
| 棋手 | 134 | 尹罗恩胤瑞 | cn, tw, jp, ko, en | 0 |
| 棋手 | 236 | Previous | cn, tw, jp, ko, en | 0 |
| 棋手 | 317 | 黑嘉嘉民生最強隊 | cn, tw, jp, ko, en | 0 |
| 棋手 | 426 | 交流戦、予選決勝は | cn, tw, jp, ko, en | 0 |
| 棋手 | 525 | 注目局を中継 | cn, tw, jp, ko, en | 0 |
| 棋手 | 588 | 芝野九段一力九段井山九段許九段福岡 | cn, tw, jp, ko, en | 0 |
| 棋手 | 639 | 芝野九段一力九段井山九段福岡七段出場 | cn, tw, jp, ko, en | 0 |
| 棋手 | 731 | 向井千瑛フマキラー杯 | cn, tw, jp, ko, en | 0 |
| 棋手 | 778 | test | cn, tw, jp, ko, en | 0 |
| 棋手 | 781 | 执白 | cn, tw, jp, ko, en | 0 |
| 棋手 | 782 | 执黑 | cn, tw, jp, ko, en | 0 |
| 棋手 | 797 | 测试123 | cn, tw, jp, ko, en | 0 |
| 棋手 | 798 | 19 | cn, tw, jp, ko, en | 0 |
| 棋手 | 823 | KataGoAI | cn, tw, jp, ko, en | 0 |
| 棋手 | 824 | KataGo | cn, tw, jp, ko, en | 0 |
| 棋手 | 825 | KaTaGoAI | cn, tw, jp, ko, en | 0 |
| 棋手 | 826 | Katago | cn, tw, jp, ko, en | 0 |
| 棋手 | 830 | 許九段-余九段の勝者 | cn, tw, jp, ko, en | 0 |
| 棋手 | 831 | 史冰晗侯靖哲 | cn, tw, jp, ko, en | 0 |
| 棋手 | 832 | 周叶蕾周叶军 | cn, tw, jp, ko, en | 0 |
| 棋手 | 833 | hei | cn, tw, jp, ko, en | 0 |
| 棋手 | 873 | 连笑战鹰 | cn, tw, jp, ko, en | 0 |
| 棋手 | 874 | 陈玉侬吴依铭 | cn, tw, jp, ko, en | 0 |
| 棋手 | 4402 | 寮犳枃涓 | cn, tw, jp, ko, en | 0 |
| 棋手 | 6245 | 鐜嬬厹杈 | cn, tw, jp, ko, en | 0 |
| 赛事类型 | 1 | 吴清源杯 | cn, tw, jp, en | 0 |

以上实体保留在P5/E5总分母中，不将总实体覆盖率写成100%。

## 其他规范实体缺口

没有仍直接关联棋局的未覆盖规范实体。

## 已发布版本与实际依据

已推送并部署的应用源码：a53f20678d099ae7304e425a0b944802a7890186；父仓库已发布提交：b7212f7530ca849da207541b6d19a170b4ac5f29（主窗确认）。

| 实际依据 | 文件 | SHA-256 |
| --- | --- | --- |
| 清理汇总 | cleanup-count-summary.json | f9704620c792455e823245e87d665fc380e2489a6d77cf67bd8351bde255d728 |
| 常昊修复独立审核 | independent-astra-changhao-review.json | dee1aa2d04eaad1b55abdaf4803e1f6701f3440e50f00ce852f05b3653a6165f |
| TEST cleanup 修改前快照 | TEST-cleanup-backup-plan.json.gz | e17efffb2a5a3a3eb78b9e9593890b5297b09b40b74b7cd697c60a086c216d80 |
| TEST cleanup apply | TEST-cleanup-apply.json | f2a9b02de1c4f48631e6d7c4885efbe8071172ef0176013ee8bcf23a99d55266 |
| TEST final-text 修改前快照 | TEST-final-text-backup.json.gz | 1c3870cc4ef8004ed6da6eea05ddee787fa46ef8134ed2eddfed5503926ccf3d |
| TEST final-text apply | TEST-final-text-apply.json | e621af2aa090d7e77b8eebd0396078b6479ed8db95d5c49a6cc0f620c4043119 |
| TEST 常昊 请求 | TEST-changhao-request.json | b582ae75247e42e0a09576ee3f9b6b8dd3c6f1e0134de366b388a837d9f4f15f |
| TEST 常昊 修改前快照 | TEST-changhao-backup.json.gz | cb14ac77743809d8099554c47efac03a10fff6ccfae538b88d0bfea6fa500f3c |
| TEST 常昊 dry-run | TEST-changhao-dry.json | 8596d5ac52b5e0f1fdd33d0021502d69962fd57b800826b0f0c28641fe8a531e |
| TEST 常昊 apply | TEST-changhao-apply.json | 2587032e7d8df261d896b26b6bc66b6bf0182a2d196692116063824670f71cf5 |
| TEST native complete | TEST-complete.json | 1443de676bad53917beaf2a2685245b9f65bb397259ccd1dbcf9e88121723e65 |
| TEST native dry-run | 001-dry-run-receipt.json | b02a02b9c5b4b6bf9da3c640a3ceeaac4dc253dce60744bfc5c0fa5b92da9d45 |
| TEST native apply | 001-apply-receipt.json | 9c5375906e75eefb4e27286305cb3f09f002388fdff168c5625d03fa32474c50 |
| TEST native verify | 001-verify-receipt.json | 2f649c1c601ecfb200c59c6d082bbf3057f19f44a658fba35b4617b78a91db4d |
| TEST native dry-run | 002-dry-run-receipt.json | dd92491b0ac125b033c7b14865b7ab31ab9b2785dcf2f6cb3f0a03e14c34b944 |
| TEST native apply | 002-apply-receipt.json | 6093d577aef35143fcd5b232b42cd5a4019b7fce3662c93a928c978157004849 |
| TEST native verify | 002-verify-receipt.json | abf6910dcad0845f0965e62e816198fe3db078b53b748c5408c93a9d3d367fee |
| TEST native dry-run | 003-dry-run-receipt.json | 7a29218bffbc85938366e9884887d4f9b47f53dc98d5874e5b44010bdef301da |
| TEST native apply | 003-apply-receipt.json | 3473bed6c81c80acef20110c5b1b5d8dc17411218661835e61e766a8f49cc332 |
| TEST native verify | 003-verify-receipt.json | 70cf8412c9034b2b2d895e89a3e0e33e11af651d174229c191a654f8a9ee864c |
| TEST native complete | TEST-complete.json | 879b2af27d95f302a4ed8095ae89aaee5f53e7cdbdd0aa3c025ce9cb13a699a8 |
| TEST native dry-run | 001-dry-run-receipt.json | 4edbfcd7ea776e60c3c88c1ff98d1c4dc04ffc7dcc4c100b8d4f02630027054a |
| TEST native apply | 001-apply-receipt.json | 72bb4d590507dc501ee04e83e2a99a21f61ded65c9f55cebfa9878a7032fd1ac |
| TEST native verify | 001-verify-receipt.json | b1c3d61835f723d7bbaf969947ca6c65369f0420c1026cb4671508c04b23d9e5 |
| PROD cleanup 修改前快照 | PROD-cleanup-backup-plan.json.gz | 2d2e213dd2bf4637208a71952d8f3ef2d29f6715e66759383286b293a7fdce97 |
| PROD cleanup apply | PROD-cleanup-apply.json | 57a10d0b30a485fcfd5b40e12e52c27e861b4acbe78fcd5ad23a54c2691829b8 |
| PROD final-text 修改前快照 | PROD-final-text-backup.json.gz | 74d85e229b1ef27e1bdc465e25ea5d7ad3fe683a94ab1b4e7f77d0f019671208 |
| PROD final-text apply | PROD-final-text-apply.json | 06724511843211c3821c993f6ef9135ee0a9b0e05a931b132a4c934b981f60c4 |
| PROD 常昊 请求 | PROD-changhao-request.json | ed8c1133d0397b53e48f7b65233f100f6b820212e02bc4b4ea691a65d575a14f |
| PROD 常昊 修改前快照 | PROD-changhao-backup.json.gz | f84c985b08629f7aa433dd19414973369dd31f86c54aa3057760cf60ea81cb43 |
| PROD 常昊 dry-run | PROD-changhao-dry.json | f88f3576d3f04bebe2830d9925dd9cc009ba39068c5b1188c47202342f7bcba9 |
| PROD 常昊 apply | PROD-changhao-apply.json | ca30d4c1d2e3e52f4c9e37f85b90c749e044c5b2d471406da95520a2cb3acf81 |
| PROD native complete | PROD-complete.json | 07b5977dd9495b13afb34206dd4f1edc1f13eb99c07376793e2f3795b6f1af53 |
| PROD native dry-run | 001-dry-run-receipt.json | ac82fd051092be99c9ac526fc971e36ef32ae628ee3188dba7063f128c88ef6f |
| PROD native apply | 001-apply-receipt.json | 4c6e52697a246284e4d44430f5622b9f6dc1d9024789354bf1959295d1031998 |
| PROD native verify | 001-verify-receipt.json | 39efaaa84b88238867fcd45672e1c447980088bdbef9879e95ca6d1d26eac1dc |
| PROD native dry-run | 002-dry-run-receipt.json | 47fab83c7415d022185a3bfe846c03937ebc28818ec2c337b0c01e7211e79a19 |
| PROD native apply | 002-apply-receipt.json | fef8e811dc660fd8714630c3b7dda4746b3823db7cf32812f35323f8fc8ab4e6 |
| PROD native verify | 002-verify-receipt.json | 6cf595d401d4f61f8a7ea360f65ff8084ea33b10387eb79521524619f1a523f2 |
| PROD native dry-run | 003-dry-run-receipt.json | 3c9445c82afec53c0a5835f0eeec91c7cb2671444c4cdd66f862b7f548e93612 |
| PROD native apply | 003-apply-receipt.json | d4098c2093c3be6d543c067ad8305d9d7dae92332a4270c4d3dbada8d58534d2 |
| PROD native verify | 003-verify-receipt.json | 5fc4fdfcf03c8bb47296a11c32c9612d75d57433876fd899498369082f99bf41 |
| PROD native complete | PROD-complete.json | 8931aa3b78a6be7399db43c98dda29004d8af050b40ef01d2d514a5f5274e206 |
| PROD native dry-run | 001-dry-run-receipt.json | 9dab44c7b95efbd2ef56998eadbdc6dcd7dd87723c4b17e7fe050f09852e510a |
| PROD native apply | 001-apply-receipt.json | d39e0c8163eaf3a0dd8c58872b16c60d10cff3460b127456c48d13dd2bd59bee |
| PROD native verify | 001-verify-receipt.json | ad1c0bc6a7234cfcded93010806ed362b9febde4f06d57706db67a054c2d654f |
| PROD 清理后全量统计 | PROD-metrics-after.json | 52a39a2c84a442b24784648f907b171fa3294186f0e0aef6a327c4ee921b1490 |
| TEST 清理后全量统计 | TEST-metrics-after.json | fc2a1db6573905995dc053d2abe0f4f2a75e3c6b6e2608c1bb265429acea0556 |
| 零直接关联实体统计依据 | PROD-native-context-v5.json.gz | bb2b98f0f0fdd7880067a85bec1fd393a1e22af0e791a5c0b4d893d161073bae |
| 吴清源杯五语现值与旧证据缺口 | PROD-wu-cup-current.json | a263d1b64781273fe87398aaaeb8822601030936f052b52b95966374eeac8210 |
| 棋手清理样例依据 | player-cleaning-decisions.json | 830c56a9723627dbb90840957a2105754cde70e9346a1fa44d73994865e7f22b |
| TEST 云端发布 | TEST-deployment.json | 087b9ea219631aadd025fbd33d5b48f24ebf7d9acc3c6ca56a369c0332467212 |
| PROD 云端发布 | PROD-deployment.json | 533e365f37266de997ab8a1437a117779b4efe56c30d7f3925d8284d459669e3 |
