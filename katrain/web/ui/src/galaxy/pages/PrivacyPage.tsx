import { Box, Container, Typography } from '@mui/material';
import { PRIVACY_CONTENT, PRIVACY_TITLE } from '../../legal/privacy';

/** 公开政策页：**不挂在 MainLayout 下**。它是从登录框外链打开的，此时用户按定义还没登录，
 *  不该把整套导航壳（顶栏/底栏/侧栏）套在一份法律文本外面。
 *
 *  标题与正文都是中文字面量、不走 i18n：法律文本不做机器翻译。
 *  ⇒ 外语用户打开这一页看到的是中文，这是**已知取舍**不是漏做，记在 plan.md 收尾里等排期。 */
const PrivacyPage = () => (
  <Box data-testid="privacy-page" sx={{ minHeight: '100%', overflowY: 'auto', bgcolor: 'background.default' }}>
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h5" component="h1" sx={{ mb: 3 }}>{PRIVACY_TITLE}</Typography>
      {/* 正文是一整段带换行的纯文本，用 pre-wrap 保形，不做 Markdown 解析 */}
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9 }}>
        {PRIVACY_CONTENT}
      </Typography>
    </Container>
  </Box>
);

export default PrivacyPage;
