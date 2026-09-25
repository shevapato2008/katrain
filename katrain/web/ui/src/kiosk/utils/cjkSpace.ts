/**
 * 中西文之间补一个空格(CJK 与拉丁字母/数字相邻时)。设计源字面就是 `登录 OGS`(有空格),
 * 不是 `登录OGS`——这条规则对**所有**拉丁字母平台名都成立,不是只有 OGS 一家。
 *
 * 不把空格写进译文里:`登录{name}` 这条模板要给 11 个语种共用,而「中西文间加空格」只在
 * 中文语境下成立(纯英文句子里插个多余空格是错的);写进 `.po` 意味着每个语种各自记一遍、
 * 非中文语种还会记错。放翻译表之外、只在拼出的字符串上跑一遍,才不用逐语种维护。
 */
const CJK = '\\u4e00-\\u9fff\\u3400-\\u4dbf';
const LATIN_DIGIT = 'A-Za-z0-9';

const CJK_THEN_LATIN = new RegExp(`([${CJK}])([${LATIN_DIGIT}])`, 'g');
const LATIN_THEN_CJK = new RegExp(`([${LATIN_DIGIT}])([${CJK}])`, 'g');

export const spaceCjkLatin = (s: string): string =>
  s.replace(CJK_THEN_LATIN, '$1 $2').replace(LATIN_THEN_CJK, '$1 $2');
