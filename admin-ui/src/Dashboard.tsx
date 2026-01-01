import { Box, Button, Card, CardContent, Chip, Grid, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';
import { usePermissions } from 'react-admin';

export const Dashboard = () => {
  const { permissions } = usePermissions();

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">مرکز کنترل</Typography>
        <Typography variant="body1" color="text.secondary">
          گفتگوها را پایش کنید، دانش را به‌روز نگه دارید و حالت پاسخ هوش مصنوعی را تنظیم کنید.
        </Typography>
      </Stack>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">این‌باکس زنده</Typography>
                  <Chip label="لحظه‌ای" size="small" color="primary" />
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  گفتگوهای فعال و پیام‌های ورودی را یکجا ببینید.
                </Typography>
                <Stack direction="row" spacing={1}>
                  <Button component={Link} to="/conversations" variant="contained" color="primary">
                    مشاهده گفتگوها
                  </Button>
                  <Button component={Link} to="/messages" variant="outlined" color="primary">
                    مشاهده پیام‌ها
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">پایگاه دانش</Typography>
                  <Chip label="رشد" size="small" sx={{ bgcolor: 'rgba(255,138,91,0.18)', color: '#a34727' }} />
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  سوالات متداول، کمپین‌ها و محصولات را با آخرین پیشنهادها هم‌راستا کنید.
                </Typography>
                <Stack direction="row" spacing={1}>
                  <Button component={Link} to="/faqs" variant="contained" color="secondary">
                    مدیریت سوالات
                  </Button>
                  <Button component={Link} to="/campaigns" variant="outlined" color="secondary">
                    کمپین‌ها
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">حالت‌های پاسخ هوش</Typography>
                  <Chip label="۳ حالت" size="small" color="primary" />
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  بسته به لحن و بار کاری، یکی از حالت‌های هیبرید، OpenAI یا DeepSeek را انتخاب کنید.
                </Typography>
                {permissions === 'admin' ? (
                  <Button component={Link} to="/settings" variant="contained" color="primary">
                    تنظیم حالت هوش
                  </Button>
                ) : (
                  <Typography variant="caption" color="text.secondary">
                    فقط ادمین می‌تواند تنظیمات هوش را تغییر دهد.
                  </Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">عیب‌یابی</Typography>
                  <Chip label="لاگ‌ها" size="small" sx={{ bgcolor: 'rgba(15,139,141,0.16)', color: '#0a6e70' }} />
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  ارسال‌ها، وبهوک‌ها و رویدادهای سلامت سیستم را بررسی کنید.
                </Typography>
                <Button component={Link} to="/logs" variant="outlined" color="primary">
                  مشاهده لاگ‌ها
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">دستیار هوشمند</Typography>
                  <Chip label="همراه عملیات" size="small" color="secondary" />
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  تصمیم‌ها و کارها را به برنامه اقدام تبدیل کنید.
                </Typography>
                <Button component={Link} to="/assistant" variant="contained" color="primary">
                  ورود به دستیار
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
