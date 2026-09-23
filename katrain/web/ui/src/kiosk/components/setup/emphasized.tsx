import { Fragment, type ReactNode } from 'react';

/**
 * 把一条**整句**译文里的 `<b>…</b>` 渲染成 `<b>` 节点,其余原样当文本。
 *
 * ## 为什么不继续拆成一段一个 key
 *
 * 屏 02 那句话原来是五个 key(`setup:note_r2_a`…`_d` + `note_h`)由 JSX 拼起来,
 * 屏 04 是十个。**拼接顺序写死在代码里,而各语种的语序不一样** —— 德语的动词、
 * 日语的助词、俄语的格位都要求把强调那一块放在与中文不同的位置上,译者拿到的却是
 * 「这几项」「开局后都不能改」「,中途换等于…」这样的碎片,**语法上没有位置**
 * 让他把顺序调过来。结果只能逐段硬译,读起来像机器翻的。
 *
 * 改成一句一个 key 之后,译者拿到的是完整句子,`<b>` 想放哪儿放哪儿。
 *
 * ## 为什么不用 `dangerouslySetInnerHTML`
 *
 * 这里只认 `<b>` 和 `</b>` 两个标记,**别的一律当字面文本**(包括译文里可能出现的
 * `<`、`&`)。走 innerHTML 的话,整条译文就成了一个 HTML 注入面 —— 译文是从
 * `/api/translations` 下发的,不是编译期常量。
 *
 * 标记不配对时(只有开标签、或只有闭标签)**不报错、不吞字**:多余的标记按普通文本
 * 渲染出来。屏上看得见「<b>」很难看,但比整句消失强 —— 译文出错不该让一屏空掉。
 */
export function emphasized(text: string): ReactNode {
  const parts = text.split(/(<b>|<\/b>)/g);
  const out: ReactNode[] = [];
  let bold = false;
  let buf = '';
  const flush = () => {
    if (!buf) return;
    out.push(bold ? <b key={out.length}>{buf}</b> : <Fragment key={out.length}>{buf}</Fragment>);
    buf = '';
  };
  for (const part of parts) {
    if (part === '<b>') {
      if (bold) { buf += part; continue; }   // 已经在粗里:当字面文本
      flush(); bold = true;
    } else if (part === '</b>') {
      if (!bold) { buf += part; continue; }  // 没开过:当字面文本
      flush(); bold = false;
    } else {
      buf += part;
    }
  }
  flush();
  return out;
}
