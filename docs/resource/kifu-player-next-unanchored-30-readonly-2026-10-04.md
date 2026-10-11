# Next 30 unanchored player NULL slots (read-only)

- JSON SHA-256: `ad362d5b2c77ef048b77594ac43ee232dd1aea1e3799ecbe777d293ba35202ba`
- Captured from live TEST and PROD repeatable-read, read-only transactions.
- No writes, identity decisions, or FK approvals.
- Excluded top20 exact-anchor group, safe6 identities, and prior HOLD raw values.
- Every entry has no exact NFKC/case/punctuation-normalized catalog owner in both snapshots.

|#|Raw|PROD NULL|TEST NULL|Candidate Chinese|Source lead|Potential duplicate IDs|HOLD|
|---:|---|---:|---:|---|---|---|---|
|1|`姜勋`|433|433|姜勋|https://zh.wikipedia.org/w/index.php?search=%E5%A7%9C%E5%8B%8B|none|yes — exact SGF/person review required|
|2|`Iwamoto Kaoru`|384|384|岩本薫|https://en.wikipedia.org/wiki/Iwamoto_Kaoru|none|yes — exact SGF/person review required|
|3|`Maeda Nobuaki`|367|367|前田陸仁|https://ja.wikipedia.org/w/index.php?search=%E5%89%8D%E7%94%B0%E9%99%B8%E5%BF%8D|none|yes — exact SGF/person review required|
|4|`林彦丞`|366|366|林彦丞|https://zh.wikipedia.org/w/index.php?search=%E6%9E%97%E5%BD%A6%E4%B8%9E|none|yes — exact SGF/person review required|
|5|`王尧`|355|355|王尧|https://zh.wikipedia.org/w/index.php?search=%E7%8E%8B%E5%B0%A7+%E5%9B%B4%E6%A3%8B|none|yes — exact SGF/person review required|
|6|`Fujisawa Hosai`|354|354|藤沢朋斎|https://en.wikipedia.org/w/index.php?search=Fujisawa+Hosai|none|yes — exact SGF/person review required|
|7|`蔡竞`|350|350|蔡竞|https://zh.wikipedia.org/wiki/%E8%94%A1%E7%AB%9E|none|yes — exact SGF/person review required|
|8|`Yoshida Yoichi`|311|311|吉田陽一|https://ja.wikipedia.org/w/index.php?search=%E5%90%89%E7%94%B0%E9%99%BD%E4%B8%80+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|9|`Ito Tomoe`|301|301|伊藤友恵|https://ja.wikipedia.org/w/index.php?search=%E4%BC%8A%E8%97%A4%E6%99%BA%E6%81%B5%E5%AD%90+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|10|`杨一`|272|272|杨一|https://zh.wikipedia.org/w/index.php?search=%E6%9D%A8%E4%B8%80+%E5%9B%B4%E6%A3%8B|10215,4424|yes — exact SGF/person review required|
|11|`Okubo Ichigen`|268|268|大久保一元|https://ja.wikipedia.org/w/index.php?search=%E5%A4%A7%E4%B9%85%E4%BF%9D%E4%B8%80%E6%BA%90+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|12|`尹灿熙`|263|263|尹灿熙|https://zh.wikipedia.org/w/index.php?search=%E5%B0%B9%E7%81%BF%E7%86%99+%E5%9B%B4%E6%A3%8B|none|yes — exact SGF/person review required|
|13|`Kano Yoshinori`|256|256|加納嘉徳|https://ja.wikipedia.org/w/index.php?search=%E5%8A%A0%E7%B4%8D%E5%98%89%E5%BE%B3+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|14|`Iwata Tatsuaki`|255|255|岩田達明|https://ja.wikipedia.org/w/index.php?search=%E5%B2%A9%E7%94%B0%E9%81%94%E6%98%8E+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|15|`Sumino Tsunehiro`|252|252|角野隆博|https://ja.wikipedia.org/w/index.php?search=%E8%A7%92%E9%87%8E%E9%9A%86%E5%8D%9A+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|16|`Kodama Kunio`|242|242|児玉国雄|https://ja.wikipedia.org/w/index.php?search=%E5%85%90%E7%8E%89%E5%9B%BD%E9%9B%84+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|17|`Takemiya Masaki`|234|234|武宮正樹|https://en.wikipedia.org/wiki/Masaki_Takemiya|none|yes — exact SGF/person review required|
|18|`Takahashi Toshimitsu`|233|233|高橋俊光|https://ja.wikipedia.org/w/index.php?search=%E9%AB%98%E6%A9%8B%E4%BF%8A%E5%85%89+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|19|`Tsujii Ryotaro`|216|216|辻井良太郎|https://ja.wikipedia.org/w/index.php?search=%E8%BE%BB%E4%BA%95%E8%89%AF%E5%A4%AA%E9%83%8E+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|20|`仓桥正行`|212|212|仓桥正行|https://ja.wikipedia.org/w/index.php?search=%E5%80%89%E6%A9%8B%E6%AD%A3%E8%A1%8C+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|21|`付冲`|208|208|付冲|https://zh.wikipedia.org/w/index.php?search=%E4%BB%98%E5%86%B2+%E5%9B%B4%E6%A3%8B|none|yes — exact SGF/person review required|
|22|`Takagawa Shukaku`|206|206|高川格|https://en.wikipedia.org/wiki/Takagawa_Shukaku|none|yes — exact SGF/person review required|
|23|`Tsuchiya Shuwa`|200|200|土屋秀和|https://ja.wikipedia.org/w/index.php?search=%E5%9C%9F%E5%B1%8B%E7%A7%80%E5%92%8C+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|24|`Kobayashi Koichi`|191|191|小林光一|https://en.wikipedia.org/wiki/Koichi_Kobayashi_(Go_player)|none|yes — exact SGF/person review required|
|25|`Sakai Takeshi`|184|184|酒井猛|https://ja.wikipedia.org/w/index.php?search=%E9%85%92%E4%BA%95%E7%8C%9B+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|26|`Honinbo Shuei`|178|178|本因坊秀栄|https://en.wikipedia.org/wiki/Honinbo_Shuei|none|yes — exact SGF/person review required|
|27|`Kobayashi Reiko`|166|166|小林禮子|https://ja.wikipedia.org/w/index.php?search=%E5%B0%8F%E6%9E%97%E7%A4%BC%E5%AD%90+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|28|`Murase Yakichi`|164|164|村瀬弥吉|https://ja.wikipedia.org/w/index.php?search=%E6%9D%91%E7%80%AC%E5%BC%A5%E5%90%89+%E5%9B%B2%E7%A2%81|none|yes — exact SGF/person review required|
|29|`Sugiuchi Kazuko`|161|161|Sugiuchi Kazuko|https://en.wikipedia.org/w/index.php?search=Sugiuchi+Kazuko+Go+player|none|yes — exact SGF/person review required|
|30|`Hashimoto Shoji`|157|157|Hashimoto Shoji|https://en.wikipedia.org/w/index.php?search=Hashimoto+Shoji+Go+player|none|yes — exact SGF/person review required|

## Conservative preimage subset

The first eight rows have exact TEST and PROD album IDs, sides, full album rows, SGF content hashes, and source rows in the JSON for independent Astra review. These are captured preimages only.
