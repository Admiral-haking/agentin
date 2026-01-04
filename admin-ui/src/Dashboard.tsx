import { Box, Button, Card, CardContent, Chip, Grid, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';
import { useDataProvider, usePermissions } from 'react-admin';
import { useEffect, useState } from 'react';
import { fetchJson } from './utils/api';

const productsEnabled = (import.meta.env.VITE_PRODUCTS_ENABLED || 'false') === 'true';
const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

export const Dashboard = () => {
  const { permissions } = usePermissions();
  const dataProvider = useDataProvider();
  const [syncRun, setSyncRun] = useState<any | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  useEffect(() => {
    if (!productsEnabled) return;
    setSyncLoading(true);
    dataProvider
      .getList('product-sync-runs', {
        pagination: { page: 1, perPage: 1 },
        sort: { field: 'started_at', order: 'DESC' },
        filter: {},
      })
      .then(result => {
        setSyncRun(result.data?.[0] || null);
      })
      .catch(() => setSyncRun(null))
      .finally(() => setSyncLoading(false));
  }, [dataProvider]);

  const handleSync = async () => {
    setSyncError(null);
    try {
      await fetchJson(`${API_URL}/admin/products/sync`, { method: 'POST' }, 'شروع همگام‌سازی ناموفق بود.');
      setSyncLoading(true);
      const result = await dataProvider.getList('product-sync-runs', {
        pagination: { page: 1, perPage: 1 },
        sort: { field: 'started_at', order: 'DESC' },
        filter: {},
      });
      setSyncRun(result.data?.[0] || null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'شروع همگام‌سازی ناموفق بود.';
      setSyncError(message);
    } finally {
      setSyncLoading(false);
    }
  };

  const syncStatusLabel = syncRun?.status || (syncLoading ? 'running' : 'unknown');
  const syncStatusColor =
    syncStatusLabel === 'success'
      ? 'success'
      : syncStatusLabel === 'failed'
        ? 'error'
        : 'warning';

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

        {productsEnabled && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6">همگام‌سازی محصولات</Typography>
                    <Chip
                      label={syncStatusLabel}
                      size="small"
                      color={syncStatusColor}
                    />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    آخرین وضعیت همگام‌سازی کاتالوگ با وب‌سایت و توروب.
                  </Typography>
                  {syncRun ? (
                    <Typography variant="body2" color="text.secondary">
                      آخرین اجرا: {syncRun.started_at || '-'} | جدید: {syncRun.created_count ?? 0} | آپدیت: {syncRun.updated_count ?? 0}
                    </Typography>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      هنوز گزارشی ثبت نشده است.
                    </Typography>
                  )}
                  {syncError && (
                    <Typography variant="body2" color="error">
                      {syncError}
                    </Typography>
                  )}
                  <Stack direction="row" spacing={1}>
                    <Button
                      onClick={handleSync}
                      variant="contained"
                      color="primary"
                      disabled={syncLoading}
                    >
                      شروع همگام‌سازی
                    </Button>
                    <Button component={Link} to="/product-sync-runs" variant="outlined">
                      مشاهده گزارش‌ها
                    </Button>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        )}

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
