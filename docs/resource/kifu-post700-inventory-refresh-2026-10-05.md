# Post700 库存与pending重绑（2026-10-05）

root两库700槽apply/verify完成后，分别只读捕获一次format4。173025局不变，690行700个棋手FK变化；逆置这些槽恢复post1117原base SHA，其他hash列/source链接、selection supplement和定向690局SGF SHA全部通过。无重复全库扫描。

| 环境 | 实际库存SHA |
|---|---|
| TEST | `ddd321f79379e3d4d171ee0cb1365bd2b0b723f9423534b70e8920d0435ce39f` |
| PROD | `3270cd885e9c8a8830be2f5c7639f7b313671808289d1744b679bf5ec1290cb0` |

目录：`/tmp/kifu-post700-inventory-20261005/`。两份库存已上传到TEST/PROD两台主机同名目录，并逐文件SHA验证。AG/AH/AI/AJ均producer封存且无apply receipt后才重绑；只改变bundle顶层inventory SHA，候选、owner/member、研究证据及catalog SHA原样。每份25pending、0missing、errors/write_errors为空；附带库存、metadata和summary同步，新旧bundle见归档及manifest。已批准历史包未动；本任务不签署、不写数据库。

| 包 | 环境 | 新pending canonical SHA |
|---|---|---|
| AG | TEST | `397d9369e71dbecf5632bbd36ae89a923f41aafc000ef0713bd23d1d52b9493b` |
| AG | PROD | `ea73247146f714ab2d1c3a5e1d4067923ee1063fd18e9e41e69bff3897c11434` |
| AH | TEST | `02e83a3020126bb5f2646a2f275a4bc8689016260f07ce91434eb6776fc8bc23` |
| AH | PROD | `b3eca2d686016dc3e9785da55fd49c7874fef8013f0e644219a1152351f3050e` |
| AI | TEST | `93cb28a7d7890cbc51e87092fa290fced68e090059d852026c26c47f5baa57c5` |
| AI | PROD | `722b06fd9fee66af8a3a3554c997084031503bc7819743eba630211d1cd61bdd` |
| AJ | TEST | `7b544b58e54a81fbd9bd696573a28bb3e08c5d7ab69595768f67bda83112eaec` |
| AJ | PROD | `b7d6a004d29e27210122fa89ae1908faf0beddfd29b3c440d6d72484540402e7` |
