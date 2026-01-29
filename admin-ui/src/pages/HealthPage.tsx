import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  Stack,
  Typography,
} from '@mui/material';
import { Title } from 'react-admin';
import { fetchJson } from '../utils/api';
import { InlineAlert } from '../components/InlineAlert';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type HealthReport = {
  window_hours: number;
  errors_last_window: number;
  send_errors_last_window: number;
  llm_errors_last_window: number;
  llm_latency_avg_ms?: number | null;
  pending_actions: number;
  last_error?: {
    id: number;
    event_type: string;
    message?: string | null;
    created_at?: string | null;
  } | null;
  last_product_sync?: {
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    created_count?: number | null;
    updated_count?: number | null;
    unchanged_count?: number | null;
    error_count?: number | null;
  } | null;
};

const formatTime = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' });
};

export const HealthPage = () => {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJson(
        `${API_URL}/admin/health/report?window_hours=24`,
        {},
        'گزارش سلامت دریافت نشد.'
      );
      setReport(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'گزارش سلامت دریافت نشد.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, []);

  const syncStatusColor =
    report?.last_product_sync?.status === 'success'
      ? 'success'
      : report?.last_product_sync?.status === 'failed'
        ? 'error'
        : 'warning';

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="سلامت سیستم" />
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">سلامت سیستم</Typography>
        <Typography variant="body1" color="text.secondary">
          وضعیت سرویس، خطاها و همگام‌سازی‌ها را در ۲۴ ساعت گذشته پایش کنید.
        </Typography>
        <Button variant="outlined" onClick={loadReport} disabled={loading}>
          بروزرسانی گزارش
        </Button>
      </Stack>

      {error && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <InlineAlert title="خطای گزارش سلامت" message={error} />
          </CardContent>
        </Card>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography variant="h6">خطاها</Typography>
                <Typography variant="body2" color="text.secondary">
                  کل خطاها: {report?.errors_last_window ?? '-'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  خطای ارسال: {report?.send_errors_last_window ?? '-'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  خطای LLM: {report?.llm_errors_last_window ?? '-'}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography variant="h6">عملکرد هوش</Typography>
                <Typography variant="body2" color="text.secondary">
                  میانگین تاخیر LLM: {report?.llm_latency_avg_ms ?? '-'} ms
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  تاییدیه‌های در انتظار: {report?.pending_actions ?? '-'}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography variant="h6">همگام‌سازی محصولات</Typography>
                <Chip
                  label={report?.last_product_sync?.status || 'unknown'}
                  color={syncStatusColor}
                  size="small"
                />
                <Typography variant="body2" color="text.secondary">
                  آخرین اجرا: {formatTime(report?.last_product_sync?.started_at)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  جدید: {report?.last_product_sync?.created_count ?? 0} | آپدیت:{' '}
                  {report?.last_product_sync?.updated_count ?? 0}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Stack spacing={1}>
                <Typography variant="h6">آخرین خطا</Typography>
                <Divider />
                {report?.last_error ? (
                  <Stack spacing={0.5}>
                    <Typography variant="body2">
                      {report.last_error.event_type} #{report.last_error.id}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {report.last_error.message || 'بدون پیام'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatTime(report.last_error.created_at)}
                    </Typography>
                  </Stack>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    خطایی ثبت نشده است.
                  </Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
